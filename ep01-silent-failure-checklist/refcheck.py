#!/usr/bin/env python3
"""refcheck: refuse to start when your game data points at things that don't exist.

Data-driven games fail quietly. A card says its kind is "Shop", the code only knows
"Store", and the recipe that needs a Shop is never possible. Nothing crashes. This
script checks every reference in your data tables against what really exists, lists
every problem it finds (not just the first), and exits non-zero so a server, a build
or CI can refuse to go on.

    python refcheck.py spec.json

The spec is a small JSON file: which tables to load (CSV, TSV or JSON), which names
exist (lists, other columns, or enums read straight out of your source code), and
which checks to run. See demo/refcheck/spec.json and the README for every option.

Exit codes: 0 = all checks pass, 1 = data problems found, 2 = the spec itself is broken.
Standard library only, Python 3.9+.
"""
import argparse
import csv
import json
import os
import re
import sys

__version__ = "1.0.0"


class SpecError(Exception):
    """The spec is wrong (missing file, unknown column...). Always loud, never skipped."""


# ---------------------------------------------------------------- loading

def load_table(base, name, src):
    """Return (rows, columns). rows = [(location, dict)]."""
    if isinstance(src, str):
        src = {"file": src}
    if "file" not in src:
        raise SpecError(f'table "{name}": needs a "file"')
    rel = src["file"]
    path = os.path.join(base, rel)
    if not os.path.isfile(path):
        raise SpecError(f'table "{name}": file not found: {rel}')
    fmt = src.get("format") or os.path.splitext(rel)[1].lower().lstrip(".")
    if fmt in ("csv", "tsv", "txt"):
        delim = src.get("delimiter", "\t" if fmt == "tsv" else ",")
        with open(path, newline="", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f, delimiter=delim)
            rows = [(f"{rel}:{reader.line_num}", row) for row in reader]
            columns = set(reader.fieldnames or [])
        return rows, columns
    if fmt == "json":
        with open(path, encoding="utf-8-sig") as f:
            data = json.load(f)
        for part in (src.get("key") or "").split(".") if src.get("key") else []:
            if not isinstance(data, dict) or part not in data:
                raise SpecError(f'table "{name}": key "{src["key"]}" not found in {rel}')
            data = data[part]
        if isinstance(data, dict):
            # {"id1": {...}, "id2": {...}} -> rows with the key in "_key"
            data = [dict(v, _key=k) if isinstance(v, dict) else {"_key": k, "_value": v}
                    for k, v in data.items()]
        if not isinstance(data, list):
            raise SpecError(f'table "{name}": {rel} must hold a list of objects (use "key" to point at it)')
        rows, columns = [], set()
        for i, obj in enumerate(data):
            if not isinstance(obj, dict):
                raise SpecError(f'table "{name}": {rel}[{i}] is not an object')
            rows.append((f"{rel}[{i}]", obj))
            columns.update(obj)
        return rows, columns
    raise SpecError(f'table "{name}": unknown format "{fmt}" (use csv, tsv or json; export spreadsheets to CSV)')


def load_enum(base, name, src):
    """An enum is a list, or names read out of a source file."""
    if isinstance(src, list):
        return {str(v) for v in src}
    if not isinstance(src, dict) or "file" not in src:
        raise SpecError(f'enum "{name}": use a list, or {{"file": ..., "after": ..., "until": ..., "pattern": ...}}')
    path = os.path.join(base, src["file"])
    if not os.path.isfile(path):
        raise SpecError(f'enum "{name}": file not found: {src["file"]}')
    text = open(path, encoding="utf-8-sig").read()
    if src.get("after"):
        i = text.find(src["after"])
        if i < 0:
            raise SpecError(f'enum "{name}": "{src["after"]}" not found in {src["file"]}')
        text = text[i + len(src["after"]):]
    if src.get("until"):
        j = text.find(src["until"])
        text = text[:j] if j >= 0 else text
    text = re.sub(r"//[^\n]*|#[^\n]*|/\*.*?\*/", "", text, flags=re.S)  # drop comments
    # Default: the identifier that starts each item (after "{", "," or a line break), so values,
    # constructor arguments and attributes ("Place = 2", "PLACE(\"p\")", "Place(u32)") are skipped.
    pattern = src.get("pattern")
    if not pattern:
        pattern = r"(?:^|[{,])[ \t]*([A-Za-z_][A-Za-z0-9_]*)"
        inner = re.compile(r"\([^()]*\)|\[[^\[\]]*\]|\{[^{}]*\}|\"[^\"\n]*\"|'[^'\n]*'")
        while inner.search(text):   # drop attributes, arguments, payloads and strings, innermost first
            text = inner.sub(" ", text)
    names = {m if isinstance(m, str) else m[0] for m in re.findall(pattern, text, re.M)}
    names.discard("")
    if not names:
        raise SpecError(f'enum "{name}": no names found in {src["file"]} (check "after", "until" and "pattern")')
    return names


# ---------------------------------------------------------------- values

def cell_values(cell, check):
    """All values a cell contributes: lists are flattened, then split / extract apply."""
    if cell is None:
        return []
    items = cell if isinstance(cell, list) else [cell]
    out = []
    for item in items:
        if item is None:
            continue
        s = str(item).strip() if not isinstance(item, bool) else str(item).lower()
        if s == "":
            continue
        parts = [p.strip() for p in s.split(check["split"])] if check.get("split") else [s]
        for p in parts:
            if not p:
                continue
            if check.get("extract"):
                for m in re.findall(check["extract"], p):
                    out.append(m if isinstance(m, str) else m[0])
            else:
                out.append(p)
    return out


class Data:
    def __init__(self, spec, base):
        self.base = base
        self.tables = {n: load_table(base, n, s) for n, s in (spec.get("tables") or {}).items()}
        self.enums = {n: load_enum(base, n, s) for n, s in (spec.get("enums") or {}).items()}

    def column(self, ref):
        if "." not in ref:
            raise SpecError(f'"{ref}": write columns as table.column')
        table, col = ref.split(".", 1)
        if table not in self.tables:
            raise SpecError(f'"{ref}": no table "{table}" (tables: {", ".join(sorted(self.tables)) or "none"})')
        rows, columns = self.tables[table]
        if col not in columns:
            raise SpecError(f'"{ref}": no column "{col}" in table "{table}" (columns: {", ".join(sorted(columns))})')
        return rows, col

    def names(self, ref, split=None):
        """A set of known names: an enum, or every value in a column."""
        if ref in self.enums:
            return self.enums[ref]
        rows, col = self.column(ref)
        return {v for _, row in rows for v in cell_values(row.get(col), {"split": split})}


# ---------------------------------------------------------------- checks

def describe(check):
    if "rows" in check:
        return f'{check["rows"]} has at least {check.get("min", 1)} rows'
    col = check.get("column", "?")
    if "in" in check:
        return f'{col} values are in {check["in"]}'
    if "covers" in check:
        return f'{col} uses every value of {check["covers"]}'
    if check.get("unique"):
        return f"{col} values are unique"
    if check.get("required"):
        return f"{col} is never empty"
    return json.dumps(check)


def run_check(data, check):
    """Return a list of problem strings. Raises SpecError for a broken check."""
    if "rows" in check:
        name = check["rows"]
        if name not in data.tables:
            raise SpecError(f'rows check: no table "{name}"')
        n, low = len(data.tables[name][0]), check.get("min", 1)
        return [] if n >= low else [f"{name} has {n} rows, expected at least {low} (did the table load completely?)"]

    if "column" not in check:
        raise SpecError(f"check needs \"column\" or \"rows\": {json.dumps(check)}")
    rows, col = data.column(check["column"])
    problems, seen, inspected = [], {}, 0

    if check.get("required"):
        for loc, row in rows:
            if not cell_values(row.get(col), check):
                problems.append(f"{loc}  {col} is empty")

    if "in" in check:
        known = data.names(check["in"], check.get("in_split"))
        for loc, row in rows:
            for v in cell_values(row.get(col), check):
                inspected += 1
                if v not in known:
                    hint = close_matches(v, known)
                    if hint:
                        hint = f"   (did you mean {hint}?)"
                    elif len(known) <= 12:
                        hint = f"   (known: {', '.join(sorted(known))})"
                    problems.append(f'{loc}  {col} = "{v}"{hint}')

    if "covers" in check:
        used = {v for _, row in rows for v in cell_values(row.get(col), check)}
        inspected += len(used)
        for v in sorted(data.names(check["covers"], check.get("covers_split")) - used):
            problems.append(f'"{v}" from {check["covers"]} never appears in {check["column"]}')

    if check.get("unique"):
        for loc, row in rows:
            for v in cell_values(row.get(col), check):
                inspected += 1
                if v in seen:
                    problems.append(f'{loc}  {col} = "{v}" repeats {seen[v]}')
                else:
                    seen[v] = loc

    if ("in" in check or check.get("unique")) and inspected == 0 and not check.get("allow_empty"):
        # A check that looked at nothing passes silently. That is exactly the bug we hunt.
        problems.append(f"checked 0 values. Is the column right, or is the table empty? "
                        f'(add "allow_empty": true if this is expected)')
    return problems


def close_matches(value, known):
    import difflib
    lower = {k.lower(): k for k in known}
    if value.lower() in lower:
        return f'"{lower[value.lower()]}"'
    m = difflib.get_close_matches(value, list(known), n=2, cutoff=0.6)
    return " or ".join(f'"{x}"' for x in m)


def run(spec_path, quiet=False, out=None):
    out = out or sys.stdout
    base = os.path.dirname(os.path.abspath(spec_path))
    try:
        with open(spec_path, encoding="utf-8-sig") as f:
            spec = json.load(f)
        base = os.path.join(base, spec.get("base", ""))
        data = Data(spec, base)
        checks = spec.get("checks") or []
        if not checks:
            raise SpecError("the spec has no checks")
        results = []
        for check in checks:
            try:
                results.append((check, run_check(data, check)))
            except SpecError as e:
                raise SpecError(f"{describe(check)}: {e}") from None
    except (SpecError, json.JSONDecodeError, OSError) as e:
        print(f"refcheck: spec error: {e}", file=out)
        return 2

    failed = [(c, p) for c, p in results if p]
    total = sum(len(p) for _, p in failed)
    for check, problems in results:
        if not problems:
            if not quiet:
                print(f"ok    {describe(check)}", file=out)
            continue
        print(f"FAIL  {describe(check)}", file=out)
        if check.get("why"):
            print(f"      why: {check['why']}", file=out)
        for p in problems[:50]:
            print(f"      {p}", file=out)
        if len(problems) > 50:
            print(f"      ... and {len(problems) - 50} more", file=out)
    print(f"\nrefcheck: {len(checks)} checks, {len(failed)} failed, {total} problems", file=out)
    return 1 if failed else 0


def main(argv=None):
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description="Check that every reference in your game data points at something real.")
    ap.add_argument("spec", help="spec JSON file (paths inside it are relative to it)")
    ap.add_argument("-q", "--quiet", action="store_true", help="only print failing checks")
    ap.add_argument("--version", action="version", version=__version__)
    a = ap.parse_args(argv)
    return run(a.spec, a.quiet)


if __name__ == "__main__":
    sys.exit(main())

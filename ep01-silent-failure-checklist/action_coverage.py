#!/usr/bin/env python3
"""action_coverage: "zero errors" is not the same as "the game works".

Feed it the list of every action you designed and the event log of a bot or playtest
run. It sorts every action into one of four buckets, so you see what never happened
and why, instead of a green "0 errors":

  1 never offered            nobody ever had it on their menu        (card flow / design hole)
  2 offered, never possible  on the menu, but the gate never opened  (check the gate)
  3 possible, never chosen   could be done, nobody picked it         (fine: that's strategy)
  4 blew up                  tried, and resolution threw an error    (must fix)

It also flags two things that make any report untrustworthy:
  - actions in the log that aren't in your list (your tooling has a blind spot)
  - actions that resolved although the menu never said they were possible
    (the command path skips the rule the menu enforces)

    python action_coverage.py --actions actions.csv run1.jsonl [run2.jsonl ...]

Log format: one JSON object per line. Emit these from your game or simulator:

  {"type": "offered", "action": "run-shop", "possible": false, "reason": "needs a Store card"}
  {"type": "resolved", "action": "odd-jobs", "outcome": "success"}      # or "failure", "error"

A whole menu can be one line: {"type": "menu", "options": [{"action": ..., "possible": ...}, ...]}.
Other lines and fields are ignored, so you can log into the same file you already have.

Exit codes: 0 = clean, 1 = errors, unknown actions or gate bypasses found (with --strict,
buckets 1 and 2 count too), 2 = bad input. Standard library only, Python 3.9+.
"""
import argparse
import collections
import csv
import io
import json
import os
import sys

__version__ = "1.0.0"

BUCKETS = [
    ("blew-up", "4 blew up", "tried, and resolution threw an error. Must fix."),
    ("never-offered", "1 never offered", "nobody ever had it on their menu. Usually a card-flow or design hole."),
    ("never-possible", "2 offered, never possible", "on menus, but its gate never opened. Check why."),
    ("never-chosen", "3 possible, never chosen", "could be done, nobody picked it. Fine: that's strategy."),
    ("ran", "ran", "offered, possible, chosen and resolved."),
]


class Stat:
    __slots__ = ("offered", "possible", "resolved", "success", "failure", "error", "reasons", "first_error")

    def __init__(self):
        self.offered = self.possible = self.resolved = self.success = self.failure = self.error = 0
        self.reasons = collections.Counter()
        self.first_error = ""

    def bucket(self):
        if self.error:
            return "blew-up"
        if not self.offered:
            return "never-offered"
        if not self.possible:
            return "never-possible"
        if not self.resolved:
            return "never-chosen"
        return "ran"


def load_actions(path):
    """Action list: CSV with an "id" column (and optional "name"), or plain text, one id per line."""
    with open(path, newline="", encoding="utf-8-sig") as f:
        text = f.read()
    if path.lower().endswith(".csv"):
        reader = csv.DictReader(io.StringIO(text))
        if "id" not in (reader.fieldnames or []):
            raise ValueError(f'{path}: needs an "id" column')
        out = collections.OrderedDict()
        for row in reader:
            if (row.get("id") or "").strip():
                out[row["id"].strip()] = (row.get("name") or "").strip()
        return out
    return collections.OrderedDict((l.strip(), "") for l in text.splitlines()
                                   if l.strip() and not l.lstrip().startswith("#"))


def read_events(paths):
    for path in paths:
        f = sys.stdin if path == "-" else open(path, encoding="utf-8-sig")
        with f:
            for n, line in enumerate(f, 1):
                line = line.strip()
                if not line or line[0] != "{":
                    continue
                try:
                    yield json.loads(line)
                except json.JSONDecodeError as e:
                    raise ValueError(f"{path}:{n}: not valid JSON ({e.msg})") from None


def tally(actions, events):
    stats = collections.OrderedDict((a, Stat()) for a in actions)
    unknown = collections.Counter()
    n_events = 0

    def get(action):
        if action not in stats:
            unknown[action] += 1
            stats[action] = Stat()
        return stats[action]

    for ev in events:
        kind = ev.get("type")
        if kind == "menu":
            options = ev.get("options") or []
        elif kind == "offered":
            options = [ev]
        elif kind == "resolved":
            n_events += 1
            s = get(str(ev.get("action")))
            outcome = str(ev.get("outcome", "success")).lower()
            s.resolved += 1
            if outcome == "error":
                s.error += 1
                s.first_error = s.first_error or str(ev.get("detail") or ev.get("error") or "")
            elif outcome in ("failure", "fail", "failed"):
                s.failure += 1
            else:
                s.success += 1
            continue
        else:
            continue
        for opt in options:
            n_events += 1
            s = get(str(opt.get("action")))
            s.offered += 1
            if opt.get("possible", True):
                s.possible += 1
            elif opt.get("reason"):
                s.reasons[str(opt["reason"])] += 1
    return stats, unknown, n_events


def report(actions, stats, unknown, n_events, allow, strict, out):
    by_bucket = collections.defaultdict(list)
    for a, s in stats.items():
        if a in actions:
            by_bucket[s.bucket()].append(a)
    bypass = [a for a, s in stats.items() if a in actions and s.resolved and not s.possible]

    total_err = sum(s.error for s in stats.values())
    print(f"{n_events} events, {len(actions)} designed actions, {total_err} errors\n", file=out)
    for key, label, meaning in BUCKETS:
        print(f"  {label:<27} {len(by_bucket[key]):>4}", file=out)
    print("", file=out)

    def name(a):
        return f"{a} ({actions[a]})" if actions.get(a) else a

    for key, label, meaning in BUCKETS:
        if key == "ran" or not by_bucket[key]:
            continue
        print(f"== {label}: {meaning}", file=out)
        for a in by_bucket[key]:
            s = stats[a]
            mark = "  (allowed)" if a in allow else ""
            if key == "blew-up":
                detail = f"{s.error} errors in {s.resolved} tries. first: {s.first_error or '(no detail logged)'}"
            elif key == "never-offered":
                detail = ""
            elif key == "never-possible":
                top = s.reasons.most_common(2)
                detail = f"offered {s.offered}x; " + ("; ".join(f"{r} x{c}" for r, c in top) if top else "no reason logged")
            else:
                detail = f"possible {s.possible}x of {s.offered} offers"
            print(f"   {name(a)}{mark}" + (f"\n      {detail}" if detail else ""), file=out)
        print("", file=out)

    if bypass:
        print("== resolved, but never possible on any menu: the command path skips the gate", file=out)
        for a in bypass:
            s = stats[a]
            print(f"   {name(a)}\n      resolved {s.resolved}x, possible on 0 of {s.offered} menus", file=out)
        print("", file=out)
    if unknown:
        print("== in the log, but not in your action list: the report can't see these", file=out)
        for a, c in unknown.most_common():
            print(f"   {a}  ({c} events)", file=out)
        print("", file=out)

    def n(count, word):
        return f"{count} {word}" + ("" if count == 1 else "s")

    fail = []
    if by_bucket["blew-up"]:
        fail.append(n(len(by_bucket["blew-up"]), "action") + " blew up")
    if bypass:
        fail.append(n(len(bypass), "gate bypass").replace("bypasss", "bypasses"))
    if unknown:
        fail.append(n(len(unknown), "unknown action"))
    if strict:
        dead = [a for a in by_bucket["never-offered"] + by_bucket["never-possible"] if a not in allow]
        if dead:
            fail.append(n(len(dead), "action") + " never offered or never possible (--strict)")
    if not n_events:
        fail.append("the log has no offered/resolved events: is it the right file?")
    print("FAIL: " + "; ".join(fail) if fail else "OK", file=out)
    return 1 if fail else 0


def write_csv(path, actions, stats):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["action", "name", "bucket", "offered", "possible", "resolved", "success", "failure", "error", "top_reason", "first_error"])
        for a, s in stats.items():
            top = s.reasons.most_common(1)
            w.writerow([a, actions.get(a, ""), s.bucket() if a in actions else "not-in-list", s.offered, s.possible,
                        s.resolved, s.success, s.failure, s.error, f"{top[0][0]} x{top[0][1]}" if top else "", s.first_error])


def main(argv=None):
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description="Sort every designed action into four buckets from a bot/playtest event log.")
    ap.add_argument("logs", nargs="+", help="JSONL event logs ('-' for stdin)")
    ap.add_argument("--actions", required=True, help="every designed action: CSV with an id column, or one id per line")
    ap.add_argument("--csv", help="also write the full table to this CSV file")
    ap.add_argument("--strict", action="store_true", help="also fail on actions that were never offered or never possible")
    ap.add_argument("--allow", action="append", default=[], help="action ids allowed to stay unused under --strict (comma-separated, repeatable)")
    ap.add_argument("--version", action="version", version=__version__)
    a = ap.parse_args(argv)
    try:
        actions = load_actions(a.actions)
        if not actions:
            raise ValueError(f"{a.actions}: no actions listed")
        for p in a.logs:
            if p != "-" and not os.path.isfile(p):
                raise ValueError(f"log not found: {p}")
        stats, unknown, n = tally(actions, read_events(a.logs))
    except (ValueError, OSError) as e:
        print(f"action_coverage: {e}", file=sys.stderr)
        return 2
    allow = {x.strip() for v in a.allow for x in v.split(",") if x.strip()}
    if a.csv:
        write_csv(a.csv, actions, stats)
    return report(actions, stats, unknown, n, allow, a.strict, sys.stdout)


if __name__ == "__main__":
    sys.exit(main())

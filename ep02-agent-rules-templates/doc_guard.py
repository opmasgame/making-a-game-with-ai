#!/usr/bin/env python3
"""doc_guard: only you can mark something DECIDED.

The rule in our CLAUDE.md is "never write a proposal as if the user approved it". A
rule in a prompt is a request. This makes it a guarantee, three ways:

  hook   Claude Code PreToolUse hook. Blocks any Edit or Write by the AI that adds,
         changes or removes a DECIDED line (or anything under a DECIDED heading)
         in your design docs, and tells the AI to keep it PROPOSED or ask you.
  diff   Lists every DECIDED line that changed since a git revision, for you to
         review before you commit, or in CI on a pull request.
  lint   Checks the other habits: a version line at the top, no "verified"
         without evidence, and a "Choices I made for you" list wherever there
         are proposals.

    python doc_guard.py hook                    # reads the hook JSON on stdin
    python doc_guard.py diff [REV] [--paths ...]
    python doc_guard.py lint [FILES_OR_DIRS ...]

Labels: **DECIDED** / **PROPOSED** and 【已定】/【提案】. Change them with --decided and
--proposed (regular expressions, repeatable). Default --paths: docs/*.md.
Set DOC_GUARD=off in your shell to turn the hook off for a session.

Exit codes: 0 = fine, 1 = problems found (diff, lint). The hook always exits 0 and
blocks through the JSON it prints, which works in every shell.
Standard library only, Python 3.9+.
"""
import argparse
import collections
import fnmatch
import json
import os
import re
import subprocess
import sys

__version__ = "1.0.0"

DEFAULT_DECIDED = [r"\bDECIDED\b", r"【已定】"]
DEFAULT_PROPOSED = [r"\bPROPOSED\b", r"【提案】"]
DEFAULT_PATHS = ["docs/*.md"]
HEADING = re.compile(r"^(#{1,6})\s")
FENCE = re.compile(r"^\s*(```|~~~)")
COMMENT = re.compile(r"<!--.*?-->", re.S)


class Labels:
    def __init__(self, decided, proposed):
        self.decided = re.compile("|".join(decided or DEFAULT_DECIDED))
        self.proposed = re.compile("|".join(proposed or DEFAULT_PROPOSED))


def norm(text):
    """Unify line endings and blank out HTML comments (keeping line numbers): notes to the AI aren't content."""
    text = (text or "").replace("\r\n", "\n").replace("\r", "\n")
    return COMMENT.sub(lambda m: "\n" * m.group(0).count("\n"), text)


def decided_lines(text, labels):
    """Every line that carries a DECIDED label, plus every line under a DECIDED heading."""
    out, section, fenced = [], None, False
    for line in norm(text).split("\n"):
        if FENCE.match(line):
            fenced = not fenced
        heading = None if fenced else HEADING.match(line)
        if heading:
            level = len(heading.group(1))
            if section is not None and level <= section:
                section = None
            if section is None and labels.decided.search(line):
                section = level
        if line.strip() and (section is not None or labels.decided.search(line)):
            out.append(line.rstrip())
    return collections.Counter(out)


def changes(before, after, labels):
    a, b = decided_lines(before, labels), decided_lines(after, labels)
    removed = list((a - b).elements())
    added = list((b - a).elements())
    return added, removed


def matches(rel, patterns):
    rel = rel.replace("\\", "/")
    return any(fnmatch.fnmatch(rel, p) or fnmatch.fnmatch(rel, "./" + p) for p in patterns)


def short(line, n=110):
    line = line.strip()
    return line if len(line) <= n else line[: n - 3] + "..."


# ---------------------------------------------------------------- hook

def text_after_edit(tool, inp, current):
    """What the file will contain if the tool call goes ahead, or None if we can't tell."""
    if tool == "Write":
        return inp.get("content", "")
    if tool in ("Edit", "MultiEdit"):
        text = norm(current)
        edits = inp.get("edits") if tool == "MultiEdit" else [inp]
        for e in edits or []:
            old, new = norm(e.get("old_string")), norm(e.get("new_string"))
            if old == "":
                if text:
                    return None
                text = new
                continue
            if old not in text:
                return None          # the edit will fail by itself
            text = text.replace(old, new) if e.get("replace_all") else text.replace(old, new, 1)
        return text
    return None


def hook(args, labels, stdin=None, stdout=None, stderr=None):
    stdin, stdout, stderr = stdin or sys.stdin, stdout or sys.stdout, stderr or sys.stderr
    if os.environ.get("DOC_GUARD", "").lower() in ("off", "0", "false"):
        return 0
    try:
        raw = stdin.buffer.read() if hasattr(stdin, "buffer") else stdin.read()
        event = json.loads(raw.decode("utf-8-sig") if isinstance(raw, bytes) else raw)   # not the console code page
    except ValueError:
        return 0                                     # not our business; never break the session
    tool, inp = event.get("tool_name", ""), event.get("tool_input") or {}
    path = inp.get("file_path")
    if tool not in ("Edit", "Write", "MultiEdit") or not path:
        return 0
    root = os.environ.get("CLAUDE_PROJECT_DIR") or event.get("cwd") or os.getcwd()
    abspath = path if os.path.isabs(path) else os.path.join(root, path)
    rel = os.path.relpath(abspath, root)
    if rel.startswith("..") or not matches(rel, args.paths):
        return 0
    current = ""
    if os.path.isfile(abspath):
        with open(abspath, encoding="utf-8", errors="replace") as f:
            current = f.read()
    after = text_after_edit(tool, inp, current)
    if after is None:
        return 0
    added, removed = changes(current, after, labels)
    if not added and not removed:
        return 0
    lines = [f"doc_guard: blocked. This edit changes what the user has DECIDED in {rel.replace(os.sep, '/')}:"]
    lines += [f"  removed: {short(l)}" for l in removed[:8]]
    lines += [f"  added:   {short(l)}" for l in added[:8]]
    if len(added) + len(removed) > 16:
        lines.append(f"  ... {len(added) + len(removed) - 16} more")
    lines.append("Only the user can add, change or remove DECIDED items. Write your suggestion as PROPOSED "
                 "next to it, or ask the user and let them make this change themselves.")
    reason = "\n".join(lines)
    # Deny through JSON on stdout with exit 0, not through exit code 2: some shells that run
    # hooks (Windows PowerShell among them) turn exit code 2 into 1, and then nothing is blocked.
    json.dump({"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny",
                                      "permissionDecisionReason": reason}}, stdout)
    print(reason, file=stderr)
    return 0


# ---------------------------------------------------------------- diff

def git(*a):
    r = subprocess.run(["git", *a], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if r.returncode != 0:
        raise SystemExit(f"doc_guard: git {' '.join(a)}: {r.stderr.decode(errors='replace').strip()}")
    return r.stdout.decode("utf-8", errors="replace")


def diff(args, labels, out=None):
    out = out or sys.stdout
    top = git("rev-parse", "--show-toplevel").strip()
    os.chdir(top)
    files = set(git("ls-tree", "-r", "--name-only", args.rev).splitlines())
    files |= set(git("ls-files", "--cached", "--others", "--exclude-standard").splitlines())
    total = 0
    for rel in sorted(f for f in files if matches(f, args.paths)):
        before = git("show", f"{args.rev}:{rel}") if subprocess.run(
            ["git", "cat-file", "-e", f"{args.rev}:{rel}"], stderr=subprocess.DEVNULL).returncode == 0 else ""
        after = ""
        if os.path.isfile(rel):
            with open(rel, encoding="utf-8", errors="replace") as f:
                after = f.read()
        added, removed = changes(before, after, labels)
        if added or removed:
            print(f"{rel}", file=out)
            for line in removed:
                print(f"  removed: {short(line, 150)}", file=out)
            for line in added:
                print(f"  added:   {short(line, 150)}", file=out)
            total += len(added) + len(removed)
    if total:
        print(f"\n{total} DECIDED lines changed since {args.rev}. Make sure each one is your call.", file=out)
        return 1
    print(f"No DECIDED lines changed since {args.rev}.", file=out)
    return 0


# ---------------------------------------------------------------- lint

VERSION_LINE = re.compile(r"(?i)\bversion\s*[:：]\s*v?\d|版本\s*[:：]\s*v?\d")
CLAIM = re.compile(r"(?i)\b(verified|validated|proven to work|confirmed working|tested and working)\b|已验证|验证通过|实测通过|已确认可用")
NEGATION = re.compile(r"(?i)\b(not|no|never|don't|doesn't|isn't|aren't|without|until|unless|unverified|before)\b|未|不|没|别|之前")
EVIDENCE = re.compile(r"(?i)https?://|`[^`]+`|\b(?=[0-9a-f]*\d)[0-9a-f]{7,40}\b|\b(evidence|log|run|commit|test)\s*[:：#]|证据\s*[:：]|日志|提交\s*[0-9a-f]")
CHOICES = re.compile(r"(?i)^#{1,6}\s.*(choices i made|made for you|替你做的选择|替你做的决定)")


def lint_text(rel, text, labels, header=True):
    problems = []
    lines = norm(text).split("\n")
    if header and not any(VERSION_LINE.search(l) for l in lines[:15]):
        problems.append((1, 'no version line near the top (e.g. "Version: v0.3. Day: 4. Status: draft")'))
    fenced = False
    for n, line in enumerate(lines, 1):
        if FENCE.match(line):
            fenced = not fenced
        if fenced:
            continue
        m = CLAIM.search(line)
        if m and not NEGATION.search(line[: m.start()]) and not EVIDENCE.search(line):
            problems.append((n, f'says "{m.group(0)}" with no evidence on the line (link a log, a commit, a test or a command)'))
        if labels.decided.search(line) and labels.proposed.search(line):
            problems.append((n, "carries both DECIDED and PROPOSED"))
    if any(labels.proposed.search(l) for l in lines) and not any(CHOICES.search(l) for l in lines):
        problems.append((len(lines), 'has PROPOSED items but no "Choices I made for you" section to review them in'))
    return problems


def lint(args, labels, out=None):
    out = out or sys.stdout
    files = []
    for p in args.files or ["docs"]:
        if os.path.isdir(p):
            for dp, dns, fns in os.walk(p):
                dns[:] = [d for d in dns if not d.startswith(".")]
                files += [os.path.join(dp, f) for f in sorted(fns) if f.lower().endswith(".md")]
        elif os.path.isfile(p):
            files.append(p)
        else:
            print(f"doc_guard: not found: {p}", file=out)
            return 2
    count = 0
    for f in files:
        with open(f, encoding="utf-8", errors="replace") as fh:
            for n, msg in lint_text(f, fh.read(), labels, header=not args.no_header):
                print(f"{f.replace(os.sep, '/')}:{n}: {msg}", file=out)
                count += 1
    print(f"doc_guard lint: {len(files)} files, {count} problems", file=out)
    return 1 if count else 0


def main(argv=None):
    for s in (sys.stdout, sys.stderr):
        if hasattr(s, "reconfigure"):
            s.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description="Only you can mark something DECIDED.")
    ap.add_argument("--decided", action="append", metavar="REGEX", help="DECIDED label pattern (repeatable)")
    ap.add_argument("--proposed", action="append", metavar="REGEX", help="PROPOSED label pattern (repeatable)")
    ap.add_argument("--version", action="version", version=__version__)
    sub = ap.add_subparsers(dest="cmd", required=True)
    h = sub.add_parser("hook", help="Claude Code PreToolUse hook (reads JSON on stdin)")
    h.add_argument("--paths", nargs="+", default=DEFAULT_PATHS, help="files to guard, relative to the project (default: docs/*.md)")
    d = sub.add_parser("diff", help="list DECIDED lines changed since a revision")
    d.add_argument("rev", nargs="?", default="HEAD")
    d.add_argument("--paths", nargs="+", default=DEFAULT_PATHS)
    l = sub.add_parser("lint", help="check version lines, unbacked 'verified', and choices lists")
    l.add_argument("files", nargs="*", help="files or folders (default: docs)")
    l.add_argument("--no-header", action="store_true", help="don't require a version line")
    a = ap.parse_args(argv)
    labels = Labels(a.decided, a.proposed)
    return {"hook": hook, "diff": diff, "lint": lint}[a.cmd](a, labels)


if __name__ == "__main__":
    sys.exit(main())

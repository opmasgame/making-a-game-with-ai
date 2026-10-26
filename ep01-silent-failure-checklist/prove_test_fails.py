#!/usr/bin/env python3
"""prove_test_fails: a test that has never failed has never proven anything.

An AI fixes a bug and says "added a test, all green". This checks that claim:

  1. run the test with the fix in place          -> must pass
  2. take the fix out (only the non-test files)  -> the test must FAIL
  3. put the fix back, run the test again        -> must pass

    python prove_test_fails.py -- pytest -q tests/test_shop.py
    python prove_test_fails.py --commit a1b2c3d -- go test ./rules/...
    python prove_test_fails.py --cmd "dotnet test --filter Shop"

Which fix? By default, your uncommitted changes; if there are none, the last commit.
Use --commit to name one. Files that look like tests (tests/, test_*.py, *_test.go,
*.test.ts, *Tests.cs ...) stay in place; everything else in the fix is taken out.
Use --tests to add your own patterns, and --dry-run to see the split first.

Your files are always put back, even on Ctrl+C. A copy is kept in
.git/prove-test-fails/ until they are; if the process is killed outright, run
`python prove_test_fails.py --restore`.

Exit codes: 0 = proven, 1 = the test still passes without the fix (it doesn't test it),
2 = the test fails even with the fix, 3 = usage or git problem.
Needs git. Standard library only, Python 3.9+.
"""
import argparse
import fnmatch
import json
import os
import re
import shutil
import subprocess
import sys
import time

__version__ = "1.0.0"

TEST_DIRS = {"test", "tests", "__tests__", "spec", "specs", "testing", "testdata", "fixtures"}
TEST_FILES = [r"^test_.*", r".*_test\.[^.]+$", r".*\.test\.[^.]+$", r".*\.spec\.[^.]+$", r".*_spec\.[^.]+$",
              r".*Tests?\.[^.]+$", r".*Spec\.[^.]+$", r"^conftest\.py$"]
TOP = "."          # repository root; set in main()
BACKUP_DIR = None  # <git dir>/prove-test-fails; set in main()
# Output that means "didn't compile / couldn't load", not "an assertion failed".
BUILD_ERROR = re.compile(r"ImportError|ModuleNotFoundError|SyntaxError|NameError: name|cannot find symbol|"
                         r"error CS\d{4}|undefined: \w|Cannot find module|is not defined|has no attribute|"
                         r"error\[E\d{4}\]|no such file or directory", re.I)


class Stop(Exception):
    def __init__(self, msg, code=3):
        super().__init__(msg)
        self.code = code


def git(*args, binary=False, check=True):
    r = subprocess.run(["git", "-C", TOP, *args], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if check and r.returncode != 0:
        raise Stop(f"git {' '.join(args)} failed: {r.stderr.decode(errors='replace').strip()}")
    return r.stdout if binary else r.stdout.decode("utf-8", errors="replace")


def is_test(path, extra):
    parts = path.replace("\\", "/").split("/")
    if any(p.lower() in TEST_DIRS for p in parts[:-1]):
        return True
    if any(re.match(p, parts[-1]) for p in TEST_FILES):
        return True
    return any(fnmatch.fnmatch(path, pat) for pat in extra)


# ---------------------------------------------------------------- which fix

def uncommitted_changes():
    """Paths changed against HEAD in the working tree, including new untracked files."""
    out = git("status", "--porcelain=v1", "-z", "--untracked-files=all")
    paths, items = [], out.split("\0")
    i = 0
    while i < len(items):
        entry = items[i]
        i += 1
        if len(entry) < 4:
            continue
        status, path = entry[:2], entry[3:]
        paths.append(path)
        if "R" in status or "C" in status:
            if "R" in status and i < len(items) and items[i]:
                paths.append(items[i])      # a rename also removed the old name
            i += 1
    return paths


def commit_changes(rev):
    out = git("diff", "--name-only", "-z", f"{rev}^", rev)
    return [p for p in out.split("\0") if p]


def content_at(rev, path):
    """File bytes at a revision, with the repo's line-ending filters applied, or None if absent."""
    if subprocess.run(["git", "-C", TOP, "cat-file", "-e", f"{rev}:{path}"], stderr=subprocess.DEVNULL).returncode != 0:
        return None
    return git("cat-file", "--filters", f"{rev}:{path}", binary=True)


def read_file(path):
    path = os.path.join(TOP, path)
    if not os.path.isfile(path):
        return None
    with open(path, "rb") as f:
        return f.read()


def write_file(path, data):
    path = os.path.join(TOP, path)
    if data is None:
        if os.path.isfile(path):
            os.remove(path)
        return
    d = os.path.dirname(path)
    if d:
        os.makedirs(d, exist_ok=True)
    with open(path, "wb") as f:
        f.write(data)


# ---------------------------------------------------------------- backup

def save_backup(paths):
    stamp = time.strftime("%Y%m%d-%H%M%S")
    root = os.path.join(BACKUP_DIR, stamp)
    os.makedirs(root, exist_ok=True)
    manifest = {}
    for i, p in enumerate(paths):
        data = read_file(p)
        if data is not None:
            with open(os.path.join(root, f"{i}.bin"), "wb") as f:
                f.write(data)
        manifest[p] = f"{i}.bin" if data is not None else None
    with open(os.path.join(root, "manifest.json"), "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=1)
    return root


def restore_backup(root):
    with open(os.path.join(root, "manifest.json"), encoding="utf-8") as f:
        manifest = json.load(f)
    for p, blob in manifest.items():
        data = None
        if blob:
            with open(os.path.join(root, blob), "rb") as f:
                data = f.read()
        write_file(p, data)
        if read_file(p) != data:
            raise Stop(f"could not restore {p}; your copy is still in {root}")
    shutil.rmtree(root, ignore_errors=True)
    try:
        os.rmdir(BACKUP_DIR)
    except OSError:
        pass
    return list(manifest)


def latest_backup():
    if not os.path.isdir(BACKUP_DIR):
        return None
    dirs = sorted(d for d in os.listdir(BACKUP_DIR) if os.path.isfile(os.path.join(BACKUP_DIR, d, "manifest.json")))
    return os.path.join(BACKUP_DIR, dirs[-1]) if dirs else None


# ---------------------------------------------------------------- running

def run_tests(cmd, shell, timeout, verbose):
    t = time.time()
    try:
        r = subprocess.run(cmd, shell=shell, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=timeout)
        code, out = r.returncode, r.stdout.decode("utf-8", errors="replace")
    except subprocess.TimeoutExpired as e:
        code, out = None, (e.stdout or b"").decode("utf-8", errors="replace") + f"\n[timed out after {timeout}s]"
    if verbose:
        print(out.rstrip())
    return code, out, time.time() - t


def tail(out, n=15):
    lines = out.rstrip().splitlines()
    return "\n".join("      | " + l for l in lines[-n:])


def step(label, code, secs, expect_pass):
    passed = code == 0
    good = passed == expect_pass
    word = "passed" if passed else ("timed out" if code is None else f"failed (exit {code})")
    print(f"  {'ok  ' if good else 'XX  '} {label:<38} {word}  [{secs:.1f}s]")
    return good


def prove(a):
    cmd, shell = (a.cmd, True) if a.cmd else (a.command, False)
    if not cmd:
        raise Stop("give the test command after --, or with --cmd \"...\"")

    if a.commit:
        rev = git("rev-parse", "--verify", f"{a.commit}^{{commit}}").strip()
        paths, base, what = commit_changes(rev), f"{rev}^", f"commit {rev[:10]}"
    else:
        paths = uncommitted_changes()
        if paths:
            rev, base, what = None, "HEAD", "your uncommitted changes"
        else:
            rev = git("rev-parse", "HEAD").strip()
            paths, base, what = commit_changes(rev), f"{rev}^", f"the last commit ({rev[:10]})"
    if rev is not None:
        dirty = git("status", "--porcelain", "--untracked-files=no").strip()
        if dirty:
            raise Stop("you have uncommitted changes; commit or stash them first, or run without --commit "
                       "to test the uncommitted changes themselves")
        if git("rev-parse", "--verify", "-q", base, check=False).strip() == "":
            raise Stop(f"{what} has no parent to compare with")

    code_files = [p for p in paths if not is_test(p, a.tests)]
    test_files = [p for p in paths if is_test(p, a.tests)]
    print(f"Fix: {what}")
    print(f"  taken out for the check ({len(code_files)}): " + (", ".join(code_files) or "-"))
    print(f"  left in place as tests  ({len(test_files)}): " + (", ".join(test_files) or "-"))
    print(f"  test command: {cmd if shell else ' '.join(cmd)}")
    if not code_files:
        raise Stop("the fix has no non-test files to take out (use --tests to adjust what counts as a test)")
    if not test_files:
        print("  note: no test files changed in this fix. Which test is meant to prove it?")
    if rev is not None:
        moved = git("diff", "--name-only", rev, "HEAD", "--", *code_files).split()
        if moved:
            raise Stop(f"these files changed after {rev[:10]}: {', '.join(moved)}. "
                       f"Check out that commit (git switch --detach {rev[:10]}) and run again")
    if a.dry_run:
        return 0
    print()

    code, out, secs = run_tests(cmd, shell, a.timeout, a.verbose)
    if not step("1. with the fix", code, secs, True):
        print(tail(out))
        print("\nNOT PROVEN: the test fails even with the fix in place.")
        return 2

    root = save_backup(code_files)
    try:
        for p in code_files:
            write_file(p, content_at(base, p))
        code, out2, secs = run_tests(cmd, shell, a.timeout, a.verbose)
        red = step("2. without the fix", code, secs, False)
    finally:
        restore_backup(root)

    code, out3, secs = run_tests(cmd, shell, a.timeout, a.verbose)
    green_again = step("3. fix put back", code, secs, True)
    print()
    if not red:
        print("NOT PROVEN: the test passes without the fix, so it doesn't test this fix.")
        print("Make it exercise the exact case the fix is for, then run this again.")
        return 1
    if not green_again:
        print(tail(out3))
        print("NOT PROVEN: the test passed at first but fails after the fix was put back. Is it flaky,"
              " or does it leave state behind?")
        return 2
    print("PROVEN: the test fails without the fix and passes with it.")
    if BUILD_ERROR.search(out2):
        print("Careful: without the fix it seems to have failed to build or import, not on an assertion.\n"
              "That still counts as red, but check it fails for the right reason: test the behaviour the fix\n"
              "changes through code that existed before the fix.")
    if not a.verbose:
        print("What it said without the fix:")
        print(tail(out2, 8))
    return 0


def main(argv=None):
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    argv = list(sys.argv[1:] if argv is None else argv)
    command = []
    if "--" in argv:
        i = argv.index("--")
        argv, command = argv[:i], argv[i + 1:]
    ap = argparse.ArgumentParser(description="Prove a test fails without the fix and passes with it.",
                                 usage="%(prog)s [options] -- <test command>")
    ap.add_argument("--commit", help="the commit that holds the fix (default: uncommitted changes, else HEAD)")
    ap.add_argument("--cmd", help="test command as one shell string, instead of after --")
    ap.add_argument("--tests", action="append", default=[], metavar="GLOB",
                    help="extra pattern for files that count as tests and stay in place (repeatable)")
    ap.add_argument("--timeout", type=float, help="seconds per test run")
    ap.add_argument("--dry-run", action="store_true", help="show which files would be taken out, run nothing")
    ap.add_argument("--restore", action="store_true", help="put back files from an interrupted run")
    ap.add_argument("-v", "--verbose", action="store_true", help="show the full test output of every run")
    ap.add_argument("--version", action="version", version=__version__)
    a = ap.parse_args(argv)
    a.command = command
    try:
        global TOP, BACKUP_DIR
        TOP = os.getcwd()
        TOP = git("rev-parse", "--show-toplevel").strip()
        BACKUP_DIR = os.path.join(git("rev-parse", "--absolute-git-dir").strip(), "prove-test-fails")
        if a.restore:
            root = latest_backup()
            if not root:
                print("nothing to restore")
                return 0
            print("restored: " + ", ".join(restore_backup(root)))
            return 0
        if latest_backup():
            raise Stop("an earlier run was interrupted; run with --restore first")
        return prove(a)
    except Stop as e:
        print(f"prove_test_fails: {e}", file=sys.stderr)
        return e.code
    except FileNotFoundError as e:
        print(f"prove_test_fails: {e}", file=sys.stderr)
        return 3


if __name__ == "__main__":
    sys.exit(main())

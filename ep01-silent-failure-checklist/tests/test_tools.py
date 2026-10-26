"""Tests for the three episode-1 tools. Run from the repository root:

    python -m unittest discover -s ep01-silent-failure-checklist/tests -v
"""
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout, redirect_stderr

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

import action_coverage  # noqa: E402
import prove_test_fails  # noqa: E402
import refcheck  # noqa: E402

DEMO = os.path.join(ROOT, "demo")


def capture(fn, *args):
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        code = fn(*args)
    return code, out.getvalue() + err.getvalue()


class Workdir(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="ep01-test-")

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def write(self, name, text):
        path = os.path.join(self.dir, name)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8", newline="") as f:
            f.write(text)
        return path


# ------------------------------------------------------------------ refcheck

class RefcheckTest(Workdir):
    def spec(self, checks, tables=None, enums=None):
        return self.write("spec.json", json.dumps({"tables": tables or {}, "enums": enums or {}, "checks": checks}))

    def test_demo_finds_the_five_planted_problems(self):
        code, out = capture(refcheck.run, os.path.join(DEMO, "refcheck", "spec.json"))
        self.assertEqual(code, 1)
        self.assertIn('kind = "Itme"   (did you mean "Item"?)', out)
        self.assertIn('main_card = "Shop"', out)
        self.assertIn('rewards = "gold-watch"', out)
        self.assertIn('when = "suspicion"', out)
        self.assertIn('"inspector" from npcs.id never appears', out)
        self.assertIn("7 checks, 5 failed, 5 problems", out)

    def test_clean_data_passes(self):
        self.write("a.csv", "id,kind\n1,Person\n2,Place\n")
        self.write("Kind.cs", "enum Kind { Person = 1, Place, /* old: Shop */ }\n")
        path = self.spec([{"column": "a.kind", "in": "Kind"}, {"column": "a.id", "unique": True},
                          {"column": "a.kind", "covers": "Kind"}],
                         {"a": "a.csv"}, {"Kind": {"file": "Kind.cs", "after": "enum Kind", "until": "}"}})
        code, out = capture(refcheck.run, path)
        self.assertEqual(code, 0, out)

    def test_enum_comments_are_not_names(self):
        self.write("a.csv", "kind\nShop\n")
        self.write("Kind.cs", "enum Kind {\n  Person, // Shop was removed\n}\n")
        path = self.spec([{"column": "a.kind", "in": "Kind"}], {"a": "a.csv"},
                         {"Kind": {"file": "Kind.cs", "after": "enum Kind", "until": "}"}})
        self.assertEqual(capture(refcheck.run, path)[0], 1)

    def test_enums_from_several_languages(self):
        cases = {
            "C#": ("enum CardKind\n{\n    Person = 1,\n    Place,   // was Shop\n    [Obsolete] Store = 1 << 3,\n}\n",
                   {"after": "enum CardKind", "until": "}"}, ["Person", "Place", "Store"]),
            "TypeScript": ('export enum CardKind { Person = "person", Place = "place" }\n',
                           {"after": "enum CardKind", "until": "}"}, ["Person", "Place"]),
            "Java": ('public enum CardKind {\n  PERSON("p"),\n  PLACE("q");\n  private final String c;\n}\n',
                     {"after": "enum CardKind", "until": ";"}, ["PERSON", "PLACE"]),
            "Rust": ("pub enum CardKind {\n    Person,\n    Place(u32),\n    Store { size: u8 },\n}\n",
                     {"after": "enum CardKind", "until": "\n}"}, ["Person", "Place", "Store"]),
            "Go": ("type Kind int\nconst (\n\tKindPerson Kind = iota\n\tKindPlace\n)\n",
                   {"after": "const (", "until": ")", "pattern": r"^\s*(Kind\w+)"}, ["KindPerson", "KindPlace"]),
        }
        for lang, (text, src, expected) in cases.items():
            self.write("enum.src", text)
            self.assertEqual(sorted(refcheck.load_enum(self.dir, lang, dict(src, file="enum.src"))), expected, lang)

    def test_a_check_that_sees_nothing_fails(self):
        self.write("a.csv", "id,kind\n1,\n2,\n")
        path = self.spec([{"column": "a.kind", "in": "K"}], {"a": "a.csv"}, {"K": ["x"]})
        code, out = capture(refcheck.run, path)
        self.assertEqual(code, 1)
        self.assertIn("checked 0 values", out)

    def test_unknown_column_is_a_spec_error_not_a_pass(self):
        self.write("a.csv", "id,kind\n1,x\n")
        path = self.spec([{"column": "a.knid", "in": "K"}], {"a": "a.csv"}, {"K": ["x"]})
        code, out = capture(refcheck.run, path)
        self.assertEqual(code, 2)
        self.assertIn('no column "knid"', out)

    def test_duplicates_and_row_minimum(self):
        self.write("a.csv", "id\n1\n2\n1\n")
        path = self.spec([{"column": "a.id", "unique": True}, {"rows": "a", "min": 5}], {"a": "a.csv"})
        code, out = capture(refcheck.run, path)
        self.assertEqual(code, 1)
        self.assertIn('repeats a.csv:2', out)
        self.assertIn("has 3 rows, expected at least 5", out)

    def test_json_lists_split_and_extract(self):
        self.write("t.json", json.dumps({"data": {"items": [{"id": "a", "tags": ["x", "y"]}, {"id": "b", "f": "$p + $q"}]}}))
        path = self.spec([{"column": "t.tags", "in": "T"}, {"column": "t.f", "extract": r"\$(\w+)", "in": "V"}],
                         {"t": {"file": "t.json", "key": "data.items"}}, {"T": ["x"], "V": ["p"]})
        code, out = capture(refcheck.run, path)
        self.assertEqual(code, 1)
        self.assertIn('tags = "y"', out)
        self.assertIn('f = "q"', out)


# ------------------------------------------------------------------ action_coverage

class CoverageTest(Workdir):
    def run_tool(self, events, actions="a\nb\nc\nd\ne\n", extra=()):
        self.write("actions.txt", actions)
        log = self.write("log.jsonl", "\n".join(json.dumps(e) for e in events) + "\n")
        return capture(action_coverage.main, ["--actions", os.path.join(self.dir, "actions.txt"), log, *extra])

    def test_demo_log(self):
        code, out = capture(action_coverage.main, ["--actions", os.path.join(DEMO, "coverage", "actions.csv"),
                                                   os.path.join(DEMO, "coverage", "events.jsonl")])
        self.assertEqual(code, 1)
        for text in ("launder-money", "publish-story", "run-shop", "needs a Shop card", "rob-bank",
                     "the command path skips the gate", "FAIL: 1 action blew up; 1 gate bypass"):
            self.assertIn(text, out)

    def test_four_buckets(self):
        events = [
            {"type": "menu", "options": [{"action": "a", "possible": True}, {"action": "b", "possible": False, "reason": "gold"},
                                         {"action": "c", "possible": True}, {"action": "e", "possible": True}]},
            {"type": "resolved", "action": "a", "outcome": "success"},
            {"type": "resolved", "action": "e", "outcome": "failure"},
        ]
        stats, unknown, n = action_coverage.tally(action_coverage.load_actions(self.write("x.txt", "a\nb\nc\nd\ne\n")),
                                                  iter(events))
        self.assertEqual({k: s.bucket() for k, s in stats.items()},
                         {"a": "ran", "b": "never-possible", "c": "never-chosen", "d": "never-offered", "e": "ran"})
        self.assertEqual(stats["e"].failure, 1)
        self.assertEqual(stats["e"].error, 0, "a failed roll is a rule, not an error")

    def test_clean_run_passes_and_strict_fails_on_dead_actions(self):
        events = [{"type": "offered", "action": a} for a in "abcde"] + [{"type": "resolved", "action": "a"}]
        self.assertEqual(self.run_tool(events)[0], 0)
        self.assertEqual(self.run_tool(events, actions="a\nz\n", extra=["--allow", "b,c,d,e"])[0], 1)  # b-e unknown
        events.append({"type": "offered", "action": "b", "possible": False})
        self.assertEqual(self.run_tool(events, actions="a\nb\nq\n", extra=["--strict"])[0], 1)
        self.assertEqual(self.run_tool([{"type": "offered", "action": "a"}, {"type": "resolved", "action": "a"},
                                        {"type": "offered", "action": "b", "possible": False}],
                                       actions="a\nb\nq\n", extra=["--strict", "--allow", "b,q"])[0], 0)

    def test_errors_unknown_actions_and_bypass_fail(self):
        code, out = self.run_tool([{"type": "offered", "action": "a"}, {"type": "resolved", "action": "a", "outcome": "error", "detail": "KeyError"}])
        self.assertEqual(code, 1)
        self.assertIn("KeyError", out)
        code, out = self.run_tool([{"type": "offered", "action": "zzz"}])
        self.assertIn("not in your action list", out)
        self.assertEqual(code, 1)
        code, out = self.run_tool([{"type": "offered", "action": "a", "possible": False}, {"type": "resolved", "action": "a"}])
        self.assertIn("skips the gate", out)
        self.assertEqual(code, 1)

    def test_empty_log_is_not_a_pass(self):
        code, out = self.run_tool([{"type": "something-else"}])
        self.assertEqual(code, 1)
        self.assertIn("no offered/resolved events", out)

    def test_csv_output(self):
        out_csv = os.path.join(self.dir, "out.csv")
        self.run_tool([{"type": "offered", "action": "a"}], extra=["--csv", out_csv])
        with open(out_csv, encoding="utf-8") as f:
            self.assertTrue(f.readline().startswith("action,name,bucket"))


# ------------------------------------------------------------------ prove_test_fails

BUGGY = "def price(qty):\n    return qty * 10\n"
FIXED = "def price(qty):\n    if qty < 0:\n        raise ValueError('negative')\n    return qty * 10\n"
GOOD_TEST = ("import unittest\nfrom shop import price\n\nclass T(unittest.TestCase):\n"
             "    def test_negative(self):\n        with self.assertRaises(ValueError):\n            price(-1)\n")
WEAK_TEST = ("import unittest\nfrom shop import price\n\nclass T(unittest.TestCase):\n"
             "    def test_positive(self):\n        self.assertEqual(price(2), 20)\n")


class ProveTest(Workdir):
    def git(self, *args):
        subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@example.com", "-c", "core.autocrlf=false", *args],
                       cwd=self.dir, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    def setUp(self):
        super().setUp()
        if shutil.which("git") is None:
            self.skipTest("git not installed")
        self.git("init", "-q")
        self.write("shop.py", BUGGY)
        self.git("add", ".")
        self.git("commit", "-q", "-m", "buggy")
        self.cwd = os.getcwd()
        os.chdir(self.dir)

    def tearDown(self):
        os.chdir(self.cwd)
        super().tearDown()

    def prove(self, *extra):
        cmd = ["--", sys.executable, "-m", "unittest", "-q", "test_shop"]
        return capture(prove_test_fails.main, [*extra, *cmd])

    def read(self, name):
        with open(os.path.join(self.dir, name), encoding="utf-8") as f:
            return f.read()

    def test_good_test_is_proven_and_files_restored(self):
        self.write("shop.py", FIXED)
        self.write("test_shop.py", GOOD_TEST)
        code, out = self.prove()
        self.assertEqual(code, 0, out)
        self.assertIn("PROVEN", out)
        self.assertEqual(self.read("shop.py"), FIXED)
        self.assertEqual(self.read("test_shop.py"), GOOD_TEST)

    def test_weak_test_is_caught(self):
        self.write("shop.py", FIXED)
        self.write("test_shop.py", WEAK_TEST)
        code, out = self.prove()
        self.assertEqual(code, 1, out)
        self.assertIn("doesn't test this fix", out)
        self.assertEqual(self.read("shop.py"), FIXED)

    def test_committed_fix(self):
        self.write("shop.py", FIXED)
        self.write("test_shop.py", GOOD_TEST)
        self.git("add", ".")
        self.git("commit", "-q", "-m", "fix")
        code, out = self.prove()             # clean tree -> last commit
        self.assertEqual(code, 0, out)
        self.assertIn("the last commit", out)
        self.assertEqual(self.read("shop.py"), FIXED)

    def test_new_code_file_is_removed_then_restored(self):
        self.write("rules.py", "LIMIT = 0\n")
        self.write("shop.py", "from rules import LIMIT\n" + FIXED.replace("qty < 0", "qty < LIMIT"))
        self.write("test_shop.py", GOOD_TEST)
        code, out = self.prove()
        self.assertEqual(code, 0, out)
        self.assertTrue(os.path.isfile(os.path.join(self.dir, "rules.py")))

    def test_failing_test_with_fix(self):
        self.write("shop.py", BUGGY.replace("10", "11"))
        self.write("test_shop.py", WEAK_TEST)
        code, out = self.prove()
        self.assertEqual(code, 2, out)

    def test_restore_after_interruption(self):
        self.write("shop.py", FIXED)
        prove_test_fails.TOP = self.dir
        prove_test_fails.BACKUP_DIR = os.path.join(self.dir, ".git", "prove-test-fails")
        prove_test_fails.save_backup(["shop.py"])
        self.write("shop.py", BUGGY)                       # simulate a run killed mid-way
        code, out = self.prove()
        self.assertEqual(code, 3)
        self.assertIn("--restore", out)
        code, out = capture(prove_test_fails.main, ["--restore"])
        self.assertEqual(code, 0, out)
        self.assertEqual(self.read("shop.py"), FIXED)

    def test_is_test(self):
        for p in ("tests/x.py", "test_a.py", "a_test.go", "a.test.ts", "ShopTests.cs", "spec/a.rb", "src/__tests__/a.js"):
            self.assertTrue(prove_test_fails.is_test(p, []), p)
        for p in ("shop.py", "contest.py", "latest.go", "src/Testing.md2"):
            self.assertFalse(prove_test_fails.is_test(p, []), p)


if __name__ == "__main__":
    unittest.main()

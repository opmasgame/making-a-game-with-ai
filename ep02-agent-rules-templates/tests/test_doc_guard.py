"""Tests for doc_guard.py. Run from the repository root:

    python -m unittest discover -s ep02-agent-rules-templates/tests -v
"""
import filecmp
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

import doc_guard  # noqa: E402

LABELS = doc_guard.Labels(None, None)
DOC = """# 00 · Concept

Version: v0.2. Day: 2. Status: draft.

## Decided **DECIDED**

- Two players. (day 1)
- 20 minutes a game. (day 1)

### Card types

- Goods, Stalls. (day 2)

## Proposals

- Hand size 5 **PROPOSED**.
- Stall limit 3 **DECIDED** (day 2)

## Choices I made for you

- Three nights **PROPOSED**.
"""


def denied(stdout):
    """True when the hook's JSON output denies the tool call."""
    if not stdout.strip():
        return False
    decision = json.loads(stdout)["hookSpecificOutput"]
    assert decision["hookEventName"] == "PreToolUse"
    return decision["permissionDecision"] == "deny" and "Only the user can" in decision["permissionDecisionReason"]


class Args:
    def __init__(self, **kw):
        self.paths = ["docs/*.md"]
        self.files = []
        self.no_header = False
        self.rev = "HEAD"
        self.__dict__.update(kw)


class GuardTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="ep02-test-")
        os.makedirs(os.path.join(self.dir, "docs"))
        self.doc = os.path.join(self.dir, "docs", "00-concept.md")
        with open(self.doc, "w", encoding="utf-8") as f:
            f.write(DOC)
        os.environ.pop("DOC_GUARD", None)

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def hook(self, tool, **tool_input):
        tool_input.setdefault("file_path", self.doc)
        event = {"tool_name": tool, "cwd": self.dir, "tool_input": tool_input}
        out, err = io.StringIO(), io.StringIO()
        old = os.environ.pop("CLAUDE_PROJECT_DIR", None)
        try:
            code = doc_guard.hook(Args(), LABELS, stdin=io.StringIO(json.dumps(event)), stdout=out, stderr=err)
        finally:
            if old is not None:
                os.environ["CLAUDE_PROJECT_DIR"] = old
        self.assertEqual(code, 0, "the hook always exits 0 and decides through JSON")
        return (2 if denied(out.getvalue()) else 0), err.getvalue()

    # -- what counts as decided

    def test_decided_lines(self):
        lines = doc_guard.decided_lines(DOC, LABELS)
        self.assertIn("- Two players. (day 1)", lines)
        self.assertIn("- Goods, Stalls. (day 2)", lines, "a subsection of a DECIDED heading is decided too")
        self.assertIn("- Stall limit 3 **DECIDED** (day 2)", lines)
        self.assertNotIn("- Hand size 5 **PROPOSED**.", lines)
        self.assertNotIn("## Proposals", lines)

    def test_comments_and_code_blocks_are_ignored(self):
        text = "<!-- **DECIDED** example -->\n```\n## Not a heading **DECIDED**\n```\n- plain\n"
        self.assertEqual(doc_guard.decided_lines(text, LABELS).get("- plain"), None)

    def test_chinese_labels(self):
        text = "## 已定的事【已定】\n\n- 两名玩家\n\n## 提案\n\n- 手牌 5 张【提案】\n- 摊位上限 3【已定】\n"
        lines = doc_guard.decided_lines(text, LABELS)
        self.assertIn("- 两名玩家", lines)
        self.assertIn("- 摊位上限 3【已定】", lines)
        self.assertNotIn("- 手牌 5 张【提案】", lines)

    # -- the hook

    def test_editing_a_proposal_is_allowed(self):
        self.assertEqual(self.hook("Edit", old_string="Hand size 5", new_string="Hand size 6")[0], 0)

    def test_promoting_a_proposal_is_blocked(self):
        code, err = self.hook("Edit", old_string="Hand size 5 **PROPOSED**", new_string="Hand size 5 **DECIDED**")
        self.assertEqual(code, 2)
        self.assertIn("added:   - Hand size 5 **DECIDED**.", err)
        self.assertIn("Only the user can", err)

    def test_adding_under_a_decided_heading_is_blocked(self):
        code, err = self.hook("Edit", old_string="- 20 minutes a game. (day 1)\n",
                              new_string="- 20 minutes a game. (day 1)\n- No online play.\n")
        self.assertEqual(code, 2)
        self.assertIn("No online play", err)

    def test_rewording_or_removing_a_decided_line_is_blocked(self):
        self.assertEqual(self.hook("Edit", old_string="Two players.", new_string="Two to four players.")[0], 2)
        self.assertEqual(self.hook("Edit", old_string="- Two players. (day 1)\n", new_string="")[0], 2)

    def test_moving_a_label_between_lines_is_blocked(self):
        code, _ = self.hook("Edit", old_string="- Hand size 5 **PROPOSED**.\n- Stall limit 3 **DECIDED** (day 2)",
                            new_string="- Hand size 5 **DECIDED**.\n- Stall limit 3 **PROPOSED** (day 2)")
        self.assertEqual(code, 2)

    def test_write_that_keeps_decided_lines_is_allowed(self):
        self.assertEqual(self.hook("Write", content=DOC.replace("draft", "in review"))[0], 0)

    def test_write_that_drops_a_decided_line_is_blocked(self):
        self.assertEqual(self.hook("Write", content=DOC.replace("- Two players. (day 1)\n", ""))[0], 2)

    def test_new_file_with_decided_content_is_blocked(self):
        new = os.path.join(self.dir, "docs", "01-turn.md")
        self.assertEqual(self.hook("Write", file_path=new, content="## Rules **DECIDED**\n- x\n")[0], 2)
        self.assertEqual(self.hook("Write", file_path=new, content="## Rules\n- x **PROPOSED**\n")[0], 0)

    def test_crlf_files_and_replace_all(self):
        with open(self.doc, "w", encoding="utf-8", newline="\r\n") as f:
            f.write(DOC)
        self.assertEqual(self.hook("Edit", old_string="(day 1)", new_string="(day 0)", replace_all=True)[0], 2)
        self.assertEqual(self.hook("Edit", old_string="Three nights", new_string="Four nights")[0], 0)

    def test_multiedit(self):
        code, _ = self.hook("MultiEdit", edits=[{"old_string": "Hand size 5", "new_string": "Hand size 4"},
                                                 {"old_string": "Two players", "new_string": "Three players"}])
        self.assertEqual(code, 2)

    def test_files_outside_paths_and_other_tools_pass(self):
        other = os.path.join(self.dir, "README.md")
        self.assertEqual(self.hook("Write", file_path=other, content="## X **DECIDED**\n")[0], 0)
        self.assertEqual(self.hook("Bash", command="echo")[0], 0)

    def test_edit_that_would_fail_anyway_passes(self):
        self.assertEqual(self.hook("Edit", old_string="not in the file", new_string="**DECIDED**")[0], 0)

    def test_switch_off(self):
        os.environ["DOC_GUARD"] = "off"
        try:
            self.assertEqual(self.hook("Edit", old_string="Two players.", new_string="One player.")[0], 0)
        finally:
            del os.environ["DOC_GUARD"]

    def test_bad_input_never_breaks_the_session(self):
        out = io.StringIO()
        code = doc_guard.hook(Args(), LABELS, stdin=io.StringIO("not json"), stdout=out, stderr=io.StringIO())
        self.assertEqual((code, out.getvalue()), (0, ""))

    def test_hook_runs_as_a_process(self):
        event = {"tool_name": "Edit", "cwd": self.dir,
                 "tool_input": {"file_path": self.doc, "old_string": "Two players.", "new_string": "Two to six players."}}
        env = dict(os.environ, CLAUDE_PROJECT_DIR=self.dir)
        event["tool_input"]["new_string"] = "Two to six players · 两到六人."     # non-ASCII must survive any console code page
        r = subprocess.run([sys.executable, os.path.join(ROOT, "doc_guard.py"), "hook"], input=json.dumps(event).encode("utf-8"),
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env)
        self.assertEqual(r.returncode, 0)
        self.assertTrue(denied(r.stdout.decode("utf-8")))
        self.assertIn("两到六人", json.loads(r.stdout.decode("utf-8"))["hookSpecificOutput"]["permissionDecisionReason"])

    # -- lint

    def lint(self, text):
        return [m for _, m in doc_guard.lint_text("x.md", text, LABELS)]

    def test_lint_clean_doc(self):
        self.assertEqual(self.lint(DOC), [])

    def test_lint_finds_problems(self):
        text = "# X\n\nThe economy is verified.\n- a **PROPOSED** **DECIDED**\n"
        problems = " | ".join(self.lint(text))
        self.assertIn("no version line", problems)
        self.assertIn('"verified" with no evidence', problems)
        self.assertIn("both DECIDED and PROPOSED", problems)
        self.assertIn("Choices I made for you", problems)

    def test_lint_accepts_evidence_and_negation(self):
        ok = ("Version: v1. Day: 1.\n"
              "- Economy verified in `sim --seed 3`.\n"
              "- Verified, see https://example.com/log.\n"
              "- Verified in commit 3f2a9c1.\n"
              "- Don't write \"verified\" before a prototype.\n"
              "- 没有原型之前不写「已验证」。\n")
        self.assertEqual(self.lint(ok), [])

    def test_lint_chinese(self):
        problems = " | ".join(self.lint("# 概念\n\n经济系统已验证。\n- 手牌 5【提案】\n"))
        self.assertIn("no version line", problems)
        self.assertIn("已验证", problems)
        self.assertIn("Choices I made for you", problems)
        self.assertEqual(self.lint("版本：v0.1。第 1 天。\n- 手牌 5【提案】\n\n## 替你做的选择\n- 三晚【提案】\n"), [])

    def test_templates_and_example_pass_lint(self):
        out = io.StringIO()
        files = [os.path.join(ROOT, "DESIGN-DOC-template.md"), os.path.join(ROOT, "zh", "设计文档-模板.md"),
                 os.path.join(ROOT, "example", "docs")]
        with redirect_stdout(out):
            code = doc_guard.lint(Args(files=files), LABELS)
        self.assertEqual(code, 0, out.getvalue())

    def test_example_ships_the_same_script(self):
        self.assertTrue(filecmp.cmp(os.path.join(ROOT, "doc_guard.py"), os.path.join(ROOT, "example", "tools", "doc_guard.py"),
                                    shallow=False), "copy doc_guard.py into example/tools/")

    def test_settings_example_is_valid(self):
        for p in ("settings.example.json", os.path.join("example", ".claude", "settings.json")):
            with open(os.path.join(ROOT, p), encoding="utf-8") as f:
                hooks = json.load(f)["hooks"]["PreToolUse"][0]
            self.assertEqual(hooks["matcher"], "Edit|Write")
            self.assertIn("doc_guard.py\" hook", hooks["hooks"][0]["command"])


class DiffTest(unittest.TestCase):
    def setUp(self):
        if shutil.which("git") is None:
            self.skipTest("git not installed")
        self.dir = tempfile.mkdtemp(prefix="ep02-diff-")
        self.cwd = os.getcwd()
        os.chdir(self.dir)
        os.makedirs("docs")
        with open("docs/00.md", "w", encoding="utf-8") as f:
            f.write(DOC)
        for cmd in (["init", "-q"], ["add", "."], ["commit", "-q", "-m", "x"]):
            subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@example.com", *cmd], check=True,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    def tearDown(self):
        os.chdir(self.cwd)
        shutil.rmtree(self.dir, ignore_errors=True)

    def test_diff(self):
        out = io.StringIO()
        self.assertEqual(doc_guard.diff(Args(), LABELS, out=out), 0)
        with open("docs/00.md", "w", encoding="utf-8") as f:
            f.write(DOC.replace("Hand size 5 **PROPOSED**", "Hand size 5 **DECIDED**"))
        out = io.StringIO()
        self.assertEqual(doc_guard.diff(Args(), LABELS, out=out), 1)
        self.assertIn("added:   - Hand size 5 **DECIDED**.", out.getvalue())


if __name__ == "__main__":
    unittest.main()

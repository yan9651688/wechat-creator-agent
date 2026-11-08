"""观察模式不把作者的表达当作需要修改的错误。"""

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT = (
    Path(__file__).resolve().parents[1]
    / ".claude/skills/human-writing/scripts/check_prose.py"
)


class ProseAdvisoryTests(unittest.TestCase):
    def run_checker(self, *arguments, input_text=None):
        return subprocess.run(
            [sys.executable, "-I", str(SCRIPT), *map(str, arguments)],
            input=input_text, capture_output=True, text=True, check=False,
        )

    def test_style_observations_preserve_original_bytes(self):
        original = (
            "# 我自己的稿子\r\n\r\n"
            "我的判断：最大的感触不是苦，而是比较。\r\n"
            "那么，再试一次。。。\r\n"
        ).encode("utf-8")
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "定稿.md"
            path.write_bytes(original)
            result = self.run_checker("--advisory", path)
            self.assertEqual(path.read_bytes(), original)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("第 3 行第 5 列，中文冒号", result.stdout)
        self.assertIn("最大的感触不是苦，而是比较", result.stdout)
        self.assertIn("事实真伪未核验", result.stdout)
        self.assertIn("作者要求、人工语料与上下文", result.stdout)
        for judgement in ("需要修改", "禁用", "删掉一半", "放开几句", "合格", "评分", "AI"):
            self.assertNotIn(judgement, result.stdout)

    def test_default_mode_retains_style_failure(self):
        result = self.run_checker("-", input_text="我的判断：不是苦，而是比较。")
        self.assertEqual(result.returncode, 1)
        self.assertIn("需要修改", result.stdout)
        self.assertIn("禁用翻案句", result.stdout)

    def test_statistical_warnings_do_not_become_rewrite_instructions(self):
        text = (
            "因为今天菜市场的商贩准备收摊，所以我提着空篮子沿着街道走回家，"
            "路过街口又买了几袋面粉和两盒鸡蛋。\n\n"
        ) * 20
        default = self.run_checker("-", input_text=text)
        self.assertIn("删掉一半试试", default.stdout)
        self.assertIn("放开几句", default.stdout)
        advisory = self.run_checker("--advisory", "-", input_text=text)
        self.assertEqual(advisory.returncode, 0, advisory.stderr)
        for judgement in ("删掉一半", "放开几句", "过于接近", "偏高", "需要修改"):
            self.assertNotIn(judgement, advisory.stdout)

    def test_stdin_and_no_observations_are_successful(self):
        result = self.run_checker("--advisory", "-", input_text="我今天去了菜市场。")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("本次未匹配", result.stdout)

    def test_code_and_urls_do_not_create_punctuation_observations(self):
        result = self.run_checker(
            "--advisory", "-",
            input_text="我今天去了菜市场。\n\n```json\n{\"地址\": \"https://example.com\"}\n```\n",
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn("英文冒号", result.stdout)

    def test_missing_file_is_an_error(self):
        with tempfile.TemporaryDirectory() as directory:
            result = self.run_checker("--advisory", Path(directory) / "missing.md")
        self.assertEqual(result.returncode, 2)
        self.assertIn("无法读取稿件", result.stderr)

    def test_invalid_utf8_is_an_error(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "broken.md"
            path.write_bytes(b"\xff")
            result = self.run_checker("--advisory", path)
        self.assertEqual(result.returncode, 2)
        self.assertIn("无法读取稿件", result.stderr)

    def test_no_chinese_and_invalid_arguments_are_errors(self):
        result = self.run_checker("--advisory", "-", input_text="just text")
        self.assertEqual(result.returncode, 2)
        self.assertIn("没有检测到汉字", result.stderr)
        result = self.run_checker("--advisory")
        self.assertEqual(result.returncode, 2)


if __name__ == "__main__":
    unittest.main()

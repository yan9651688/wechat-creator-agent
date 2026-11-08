import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / '工具' / '句子形状.py'
SPEC = importlib.util.spec_from_file_location('sentence_stats', SCRIPT)
stats = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(stats)


class SentenceStatsTests(unittest.TestCase):
    def test_short_sentences_and_unpunctuated_paragraphs_are_not_merged(self):
        result = stats.describe('好。行！\n\n下一句\n\n最后一句')
        self.assertEqual(result['paragraphs'], 3)
        self.assertEqual(result['sentences'], 4)
        self.assertEqual(result['mean_length'], 2.25)
        self.assertEqual(result['mean_commas'], 0)

    def test_markdown_non_prose_blocks_are_excluded(self):
        text = '''# 标题很长，不要计入。

正文，接着说。

> 引用不计入。
引用的续行也不计入。

![图片说明](image.png)

表头 | 另一列
--- | ---
内容，很多。 | 另一列。

~~~text
提示词，很长。
~~~

````python
```
代码，不算。
````

    缩进代码，不算。

小标题
------

结尾。
'''
        result = stats.describe(text)
        self.assertEqual(result['paragraphs'], 2)
        self.assertEqual(result['sentences'], 2)
        self.assertEqual(result['mean_commas'], 0.5)
        self.assertEqual(result['mean_length'], 4)

    def test_inline_markup_does_not_count_urls_or_images(self):
        text = '**用词**，看[原文](https://example.org/a)。![图](pic.png)\n\n`code!`好。'
        self.assertEqual(stats.describe(text)['mean_length'], 3.5)
        self.assertEqual(stats.describe(text)['sentences'], 2)

    def test_unclosed_fence_is_not_counted_as_prose(self):
        self.assertEqual(stats.describe('开头。\n\n~~~\n提示词。')['sentences'], 1)
        result = stats.describe('# 只有标题\n\n```\n代码')
        self.assertEqual(result['sentences'], 0)
        self.assertIsNone(result['mean_length'])

    def test_list_items_are_separate_without_final_punctuation(self):
        result = stats.describe('- 短\n- 长一点\n\n1. 再一句')
        self.assertEqual(result['sentences'], 3)
        self.assertEqual(result['paragraphs'], 3)

    def test_cli_is_read_only_and_references_have_no_targets_or_scores(self):
        with tempfile.TemporaryDirectory() as directory:
            paths = [Path(directory) / name for name in ('短稿.md', '长稿.md', '参考一.md', '参考二.md')]
            contents = ['好！\r\n\r\n行。。。', '其实，这句我还会接着讲，讲完才停。', '就是：不是这个，而是那个。', '停。']
            for path, text in zip(paths, contents):
                path.write_bytes(text.encode('utf-8'))
            originals = [path.read_bytes() for path in paths]
            command = [sys.executable, '-I', str(SCRIPT), *map(str, paths[:2]),
                       '--reference', str(paths[2]), '--reference', str(paths[3]), '--json']
            run = subprocess.run(command, capture_output=True, text=True)
            self.assertEqual(run.returncode, 0, run.stderr)
            result = json.loads(run.stdout)
            self.assertEqual(len(result['articles']), 2)
            self.assertEqual(len(result['references']), 2)
            self.assertEqual(result['articles'][0]['mean_length'], 1)
            self.assertEqual(result['references'][1]['mean_length'], 1)
            for item in result['articles'] + result['references']:
                self.assertEqual(set(item), {'path', 'paragraphs', 'sentences', 'mean_commas', 'mean_length'})
            self.assertEqual([path.read_bytes() for path in paths], originals)
            self.assertEqual(set(Path(directory).iterdir()), set(paths))
            plain = subprocess.run([sys.executable, '-I', str(SCRIPT), str(paths[0])], capture_output=True, text=True)
            self.assertEqual(plain.returncode, 0, plain.stderr)
            self.assertIn('不是写作目标', plain.stdout)
            for verdict in ('再改一轮', '偏短', '上限', '合格', '达标'):
                self.assertNotIn(verdict, plain.stdout)

    def test_missing_input_fails_without_a_style_verdict(self):
        with tempfile.TemporaryDirectory() as directory:
            run = subprocess.run([sys.executable, '-I', str(SCRIPT), str(Path(directory) / 'missing.md')],
                                 capture_output=True, text=True)
            self.assertEqual(run.returncode, 2)
            self.assertEqual(run.stdout, '')


if __name__ == '__main__':
    unittest.main()

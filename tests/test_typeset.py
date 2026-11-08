"""排版不能丢正文、改变作者手迹，或在失败时覆盖源文件/已有成品。"""
import base64
import contextlib
import hashlib
import importlib.util
import io
import json
import os
from html.parser import HTMLParser
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / '工具' / '红白排版.py'
PNG = base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aKz8AAAAASUVORK5CYII=')


class Text(HTMLParser):
    def __init__(self, markup):
        super().__init__()
        self.parts = []
        self.root_attrs = None
        self.sections = 0
        self.minimum_sections = 0
        self.feed(markup)

    def handle_data(self, data):
        self.parts.append(data)

    def handle_starttag(self, tag, attrs):
        if tag == 'br':
            self.parts.append('\n')
        if tag == 'section':
            if self.root_attrs is None:
                self.root_attrs = dict(attrs)
            self.sections += 1

    def handle_endtag(self, tag):
        if tag == 'section':
            self.sections -= 1
            self.minimum_sections = min(self.minimum_sections, self.sections)

    @property
    def text(self):
        return ''.join(self.parts)


class TypesetTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.md = self.base / '2-定稿.md'
        self.config = self.base / '配置.json'
        self.out = self.base / '正文.html'
        self.settings = {'tags': [], 'phrases': [], 'quote_highlights': [],
                         'signoff_prefix': '我是作者'}
        self.write_config()

    def write_config(self):
        self.config.write_text(json.dumps({self.base.name: self.settings}), encoding='utf-8')

    def run_cli(self, out=None):
        return subprocess.run([sys.executable, '-I', str(SCRIPT), str(self.config),
                               str(self.md), str(out or self.out)], text=True, capture_output=True)

    def assert_success(self):
        before = self.md.read_bytes()
        result = self.run_cli()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.md.read_bytes(), before)
        rendered = Text(self.out.read_text(encoding='utf-8'))
        self.assertEqual(rendered.root_attrs['data-source-file'], self.md.name)
        self.assertEqual(rendered.root_attrs['data-source-sha256'], hashlib.sha256(before).hexdigest())
        self.assertEqual(rendered.sections, 0)
        self.assertEqual(rendered.minimum_sections, 0)
        self.assertIn('SHA-256', result.stdout)
        return rendered

    def test_no_chapters_keeps_all_paragraphs_and_author_punctuation(self):
        self.md.write_text('# 标题\n这这件事，其实不是 A，而是 B。。。\n同一段的下一行 - 原样。\n\n短句！\n', encoding='utf-8')
        rendered = self.assert_success()
        self.assertIn('这这件事，其实不是 A，而是 B。。。\n同一段的下一行 - 原样。', rendered.text)
        self.assertIn('短句！', rendered.text)
        self.assertEqual(self.out.read_text().count('短句！'), 1)

    def test_adjacent_heading_body_and_multiple_images_are_not_swallowed(self):
        (self.base / 'a.png').write_bytes(PNG)
        (self.base / 'b.png').write_bytes(PNG)
        self.settings['tags'] = ['ONE']
        self.write_config()
        self.md.write_text('# 标题\n开头。\n## 章节\n正文。\n### 小节\n接着说。\n![图一](a.png)\n![图二](b.png)\n收尾。', encoding='utf-8')
        rendered = self.assert_success()
        for expected in ('开头。', '章节', '正文。', '小节', '接着说。', '图一', '图二', '收尾。'):
            self.assertIn(expected, rendered.text)
        markup = self.out.read_text()
        self.assertEqual(markup.count('<img '), 2)
        self.assertEqual(markup.count('data:image/png;base64,'), 2)

    def test_code_fences_keep_blank_lines_indent_and_shorter_inner_fence(self):
        code = '  第一行\n\n\t第二行\n```\n  第三行'
        self.md.write_text('# 标题\n````text\n' + code + '\n````\n~~~\n  下一个\n~~~\n完。', encoding='utf-8')
        rendered = self.assert_success()
        self.assertIn(code, rendered.text)
        self.assertIn('  下一个', rendered.text)
        self.assertIn('完。', rendered.text)

    def test_title_only_and_quote_only_are_valid(self):
        for body in ('# 标题', '# 标题\n> 原话：\n> 保留下一行。。。'):
            with self.subTest(body=body):
                self.md.write_text(body, encoding='utf-8')
                rendered = self.assert_success()
                if '原话' in body:
                    self.assertIn('原话：\n保留下一行。。。', rendered.text)

    def test_signoff_only_moves_when_paragraph_starts_with_prefix(self):
        self.md.write_text('# 标题\n正文说我是作者，这句话仍然是正文。', encoding='utf-8')
        rendered = self.assert_success().text
        self.assertLess(rendered.index('正文说'), rendered.index('END'))
        self.md.write_text('# 标题\n正文。\n\n我是作者，下次见。。。', encoding='utf-8')
        rendered = self.assert_success().text
        self.assertGreater(rendered.index('我是作者'), rendered.index('END'))
        self.assertEqual(rendered.count('我是作者，下次见。。。'), 1)

    def test_validation_failures_preserve_existing_output(self):
        self.out.write_bytes(b'previous output')
        cases = [('# 标题\n## 没有对应 tag\n正文。', None),
                 ('# 标题\n```\n未闭合', None),
                 ('# 标题\n正文。', {'tags': []}),
                 ('# 标题\n| A | B |\n| --- | --- |\n| too | many | columns |', None)]
        for text, settings in cases:
            with self.subTest(text=text, settings=settings):
                self.md.write_text(text, encoding='utf-8')
                if settings is not None:
                    self.config.write_text(json.dumps({self.base.name: settings}), encoding='utf-8')
                else:
                    self.write_config()
                result = self.run_cli()
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(self.out.read_bytes(), b'previous output')
                self.assertEqual(self.md.read_text(), text)

    def test_cannot_overwrite_source_or_config_through_alias(self):
        self.md.write_text('# 标题\n保留。', encoding='utf-8')
        for source in (self.md, self.config):
            for kind in ('direct', 'symlink', 'hardlink'):
                with self.subTest(source=source.name, kind=kind):
                    alias = self.base / ('alias-' + kind)
                    if alias.exists() or alias.is_symlink():
                        alias.unlink()
                    if kind == 'direct':
                        alias = source
                    elif kind == 'symlink':
                        alias.symlink_to(source)
                    else:
                        os.link(source, alias)
                    before = source.read_bytes()
                    result = self.run_cli(alias)
                    self.assertNotEqual(result.returncode, 0)
                    self.assertEqual(source.read_bytes(), before)

    def test_source_changed_during_render_rejects_output(self):
        self.md.write_text('# 标题\n原稿。', encoding='utf-8')
        self.out.write_text('previous output', encoding='utf-8')
        spec = importlib.util.spec_from_file_location('typeset_under_test', SCRIPT)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        original_render = module.render

        def changed(text):
            result = original_render(text)
            self.md.write_text('# 标题\n作者新改的。', encoding='utf-8')
            return result

        with mock.patch.object(module, 'render', changed), contextlib.redirect_stderr(io.StringIO()):
            result = module.main([str(self.config), str(self.md), str(self.out)])
        self.assertEqual(result, 1)
        self.assertEqual(self.out.read_text(), 'previous output')
        self.assertIn('作者新改的', self.md.read_text())


if __name__ == '__main__':
    unittest.main()

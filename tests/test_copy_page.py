"""复制页的标题、摘要必须与正文使用同一版源稿。"""
import contextlib
import hashlib
import html
import importlib.util
import io
import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / '工具' / '一键复制总页.py'
SPEC = importlib.util.spec_from_file_location('copy_page_under_test', SCRIPT)
COPY = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(COPY)


class CopyPageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.article = self.root / '2026-01-01-测试'
        self.article.mkdir()
        self.draft = self.article / '1-自改稿.md'
        self.final = self.article / '2-定稿.md'
        self.draft.write_text('# 初稿标题\n\n> 初稿摘要\n\n初稿正文', encoding='utf-8')
        self.final.write_text('# 作者定的标题。。。\n\n> 作者的摘要：原样！\n\n原样正文', encoding='utf-8')
        self.body = self.article / '文章_排版_红白.html'
        self.write_body(self.final)
        (self.article / '配图').mkdir()
        self.covers = [self.article / '配图' / name for name in ('封面-公众号.png', '封面-1比1.png')]
        for cover in self.covers:
            cover.write_bytes(b'cover fixture')
        self.out = self.root / '总页.html'

    def write_body(self, source):
        sha = hashlib.sha256(source.read_bytes()).hexdigest()
        self.body.write_text('<section data-source-file="' + html.escape(source.name, quote=True) +
                             '" data-source-sha256="' + sha + '">正文内容</section>', encoding='utf-8')

    def run_main(self, output=None, converter=None):
        with mock.patch.object(COPY, 'jpg_uri', side_effect=converter or (lambda path: 'data:image/jpeg;base64,fixture')), \
             contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            return COPY.main([str(self.root), str(output or self.out), self.article.name])

    def test_metadata_uses_final_title_and_summary(self):
        self.assertEqual(self.run_main(), 0)
        output = self.out.read_text()
        self.assertIn('作者定的标题。。。', output)
        self.assertIn('作者的摘要：原样！', output)
        self.assertNotIn('初稿标题', output)
        self.assertNotIn('初稿摘要', output)
        self.assertIn(self.body.read_text(), output)

    def test_metadata_selects_actual_source_even_when_final_exists(self):
        self.write_body(self.draft)
        self.assertEqual(self.run_main(), 0)
        self.assertIn('初稿标题', self.out.read_text())
        self.assertNotIn('作者定的标题。。。', self.out.read_text())

    def test_stale_source_rejects_and_preserves_existing_page(self):
        self.out.write_text('previous page')
        self.final.write_text('# 新改的标题\n\n作者又改了。', encoding='utf-8')
        self.assertEqual(self.run_main(), 1)
        self.assertEqual(self.out.read_text(), 'previous page')

    def test_legacy_html_prefers_final_then_draft(self):
        self.body.write_text('<section>旧版正文</section>')
        self.assertEqual(self.run_main(), 0)
        self.assertIn('作者定的标题。。。', self.out.read_text())
        self.final.unlink()
        self.assertEqual(self.run_main(), 0)
        self.assertIn('初稿标题', self.out.read_text())

    def test_incomplete_invalid_or_escaping_metadata_does_not_fall_back(self):
        self.out.write_text('previous page')
        for attrs in ('data-source-file="2-定稿.md"',
                      'data-source-sha256="' + '0' * 64 + '"',
                      'data-source-file="../outside.md" data-source-sha256="' + '0' * 64 + '"',
                      'data-source-file="2-定稿.md" data-source-sha256="bad"',
                      'data-source-file="2-定稿.md" data-source-file="1-自改稿.md" data-source-sha256="' + '0' * 64 + '"'):
            with self.subTest(attrs=attrs):
                self.body.write_text('<section ' + attrs + '>正文</section>')
                self.assertEqual(self.run_main(), 1)
                self.assertEqual(self.out.read_text(), 'previous page')

    def test_source_filename_html_entities_are_decoded(self):
        source = self.article / '作者的"定稿&.md'
        source.write_text('# 特殊文件名\n\n> 特殊摘要\n\n正文', encoding='utf-8')
        self.write_body(source)
        self.assertEqual(self.run_main(), 0)
        self.assertIn('特殊文件名', self.out.read_text())

    def test_output_cannot_overwrite_any_read_input_or_alias(self):
        for source in [self.final, self.body] + self.covers:
            for kind in ('direct', 'symlink', 'hardlink'):
                with self.subTest(source=source.name, kind=kind):
                    alias = self.root / 'output-alias'
                    if alias.exists() or alias.is_symlink():
                        alias.unlink()
                    if kind == 'direct':
                        output = source
                    elif kind == 'symlink':
                        alias.symlink_to(source)
                        output = alias
                    else:
                        os.link(source, alias)
                        output = alias
                    before = source.read_bytes()
                    self.assertEqual(self.run_main(output), 1)
                    self.assertEqual(source.read_bytes(), before)

    def test_source_changed_during_packaging_preserves_previous_page(self):
        self.out.write_text('previous page')

        def edit_source(path):
            self.final.write_text('# 打包时作者又改了\n\n新正文', encoding='utf-8')
            return 'data:image/jpeg;base64,fixture'

        self.assertEqual(self.run_main(converter=edit_source), 1)
        self.assertEqual(self.out.read_text(), 'previous page')


if __name__ == '__main__':
    unittest.main()

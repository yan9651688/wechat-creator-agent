import importlib.util
import json
from pathlib import Path
import tempfile
import threading
import unittest
import urllib.request
from http.server import HTTPServer


SCRIPT = Path(__file__).resolve().parents[1] / '工具' / '逐行改稿.py'
SPEC = importlib.util.spec_from_file_location('line_edit', SCRIPT)
le = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(le)

DRAFT = '''# 标题

> 引言

第一段。

```
代码里

有空行
```

![图](配图/a.jpg)

第二段。

第三段。
'''


class LineEditTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        (self.dir / '1-自改稿.md').write_text(DRAFT, encoding='utf-8')
        le.setup(str(self.dir))

    def tearDown(self):
        self.tmp.cleanup()

    def test_blocks_keep_fenced_code_together(self):
        texts = [b for b, _ in le.blocks(DRAFT)]
        self.assertEqual(len(texts), 7)
        self.assertIn('代码里\n\n有空行', texts[3])
        self.assertEqual(le.blocks(DRAFT)[2][1], 5)  # 起始行号

    def test_without_final_draft_right_side_equals_source(self):
        rows = le.rows()
        self.assertTrue(all(r['cur'] == r['src'] for r in rows))
        self.assertEqual([r['kind'] for r in rows][3:5], ['code', 'img'])

    def test_final_draft_edits_align_to_source_rows(self):
        final = DRAFT.replace('第一段。', '第一段，我改过了。').replace('\n第三段。\n', '\n') + '\n新加一段。\n'
        (self.dir / '2-定稿.md').write_text(final, encoding='utf-8')
        rows = le.rows()
        self.assertEqual(len(rows), 7)
        self.assertEqual(rows[2]['cur'], '第一段，我改过了。')
        self.assertEqual(rows[1]['cur'], '> 引言')
        joined = '\n\n'.join(r['cur'] for r in rows if r['cur'])
        self.assertNotIn('第三段', joined)
        self.assertIn('新加一段。', joined)

    def test_hints_read_from_comparison_table(self):
        (self.dir / '改稿对照.md').write_text(
            '| 行 | 原文 | 预判 |\n|---|---|---|\n| L5 | 第一段。 | **可能删** |\n| L17 | 第三段。 | — |\n',
            encoding='utf-8')
        rows = {r['line']: r['hint'] for r in le.rows()}
        self.assertEqual(rows[5], '可能删')
        self.assertEqual(rows[17], '')

    def test_save_writes_final_draft_and_unchanged_save_roundtrips(self):
        server = HTTPServer(('127.0.0.1', 0), le.H)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        try:
            port = server.server_address[1]
            with urllib.request.urlopen(f'http://127.0.0.1:{port}/') as r:
                page = r.read().decode('utf-8')
            self.assertIn('逐行改稿', page)
            text = '\n\n'.join(r['cur'] for r in le.rows()) + '\n'
            req = urllib.request.Request(f'http://127.0.0.1:{port}/save',
                                         data=json.dumps({'text': text}).encode('utf-8'),
                                         headers={'Content-Type': 'application/json'})
            with urllib.request.urlopen(req) as r:
                self.assertTrue(json.loads(r.read())['ok'])
        finally:
            server.shutdown()
            server.server_close()
        self.assertEqual((self.dir / '2-定稿.md').read_text(encoding='utf-8'), DRAFT)


if __name__ == '__main__':
    unittest.main()

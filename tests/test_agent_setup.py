import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / '工具' / '一键配置.py'
SPEC = importlib.util.spec_from_file_location('agent_setup', SCRIPT)
setup = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(setup)


class AgentSetupTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        (root / '.agents/skills/gzh-design').mkdir(parents=True)
        (root / '.agents/skills/gzh-design/SKILL.md').write_text('---\nname: gzh-design\n---\n', encoding='utf-8')
        (root / '规则').mkdir()
        (root / '规则/01-我是谁.md').write_text('名字：`<名字>`，读者：`<读者 1>`\n', encoding='utf-8')
        (root / '.env.example').write_text('IMAGE_API_KEY=\n', encoding='utf-8')
        (root / 'AGENTS.md').write_text('# 规则\n', encoding='utf-8')
        self.root = root
        self.old_root = setup.ROOT
        setup.ROOT = root

    def tearDown(self):
        setup.ROOT = self.old_root
        self.tmp.cleanup()

    def test_gemini_entry_points_back_to_agents_md(self):
        self.assertEqual(setup.write_entry('GEMINI.md'), '已生成')
        text = (self.root / 'GEMINI.md').read_text(encoding='utf-8')
        self.assertIn('@AGENTS.md', text)
        self.assertEqual(setup.write_entry('GEMINI.md'), '已就绪')

    def test_existing_user_entry_file_is_not_overwritten(self):
        (self.root / 'CLAUDE.md').write_text('我自己的规则\n', encoding='utf-8')
        result = setup.write_entry('CLAUDE.md')
        self.assertIn('没覆盖', result)
        self.assertEqual((self.root / 'CLAUDE.md').read_text(encoding='utf-8'), '我自己的规则\n')

    def test_agents_md_native_agents_need_no_entry(self):
        self.assertIn('不用生成', setup.write_entry('AGENTS.md'))

    def test_claude_skill_link_points_to_shared_skills(self):
        self.assertEqual(setup.link_skills('.claude/skills'), '已建链接')
        self.assertTrue((self.root / '.claude/skills/gzh-design/SKILL.md').exists())
        self.assertEqual(setup.link_skills('.claude/skills'), '已就绪')

    def test_env_copied_once_and_identity_blanks_counted(self):
        self.assertIn('已从', setup.ensure_env_file())
        self.assertEqual(setup.ensure_env_file(), '已存在')
        self.assertEqual(setup.check_identity()['身份空格'], 2)

    def test_check_only_run_changes_nothing_and_prints_json(self):
        before = sorted(p.name for p in REPO.iterdir())
        out = subprocess.run([sys.executable, '-I', str(SCRIPT), '--json'],
                             capture_output=True, text=True, check=True).stdout
        data = json.loads(out)
        self.assertEqual(data['本次配置'], {})
        self.assertIn('gzh-design', data['环境']['技能']['值'])
        self.assertEqual(before, sorted(p.name for p in REPO.iterdir()))

    def test_unknown_agent_is_rejected(self):
        r = subprocess.run([sys.executable, '-I', str(SCRIPT), '--agent', 'nope'],
                           capture_output=True, text=True)
        self.assertNotEqual(r.returncode, 0)


if __name__ == '__main__':
    unittest.main()

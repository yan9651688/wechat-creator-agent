# 一键配置：检查环境，按你用的 Agent 生成入口文件和技能链接，报告还要你填什么。
# 用法：
#   python3 -I 工具/一键配置.py                     只检查，不改任何文件
#   python3 -I 工具/一键配置.py --agent codex        为某个 Agent 配置（可写多个，或 all）
#   python3 -I 工具/一键配置.py --agent claude --json  结果输出成 JSON，方便 Agent 读
# 支持的 Agent：claude codex kimi zcode gemini cursor other
# 只会新建文件和链接，已有的入口文件不是本脚本生成的就不覆盖；不写密钥，不联网。
import argparse
import importlib.util
import json
import os
import re
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MARK = '<!-- 由 工具/一键配置.py 生成，规则请改 AGENTS.md -->'

# 每个 Agent：会自动读哪个入口文件、技能放哪、需要本脚本补什么
AGENTS = {
    'claude': {'名字': 'Claude Code', '入口': 'CLAUDE.md', '技能目录': '.claude/skills',
               '说明': '读 CLAUDE.md（里面用 @AGENTS.md 导入），技能扫 .claude/skills，指向 .agents/skills 的链接。'},
    'codex': {'名字': 'Codex CLI', '入口': 'AGENTS.md', '技能目录': '.agents/skills',
              '说明': '原生读 AGENTS.md，技能扫 .agents/skills，不用额外文件。AGENTS.md 合计默认上限 32 KiB。'},
    'kimi': {'名字': 'Kimi Code', '入口': 'AGENTS.md', '技能目录': '.agents/skills',
             '说明': '原生读 AGENTS.md，项目技能扫 .kimi-code/skills 和 .agents/skills，不用额外文件。'},
    'zcode': {'名字': 'ZCode', '入口': 'AGENTS.md', '技能目录': '.agents/skills',
              '说明': '按第三方介绍用 AGENTS.md 放项目规则；技能目录未在官方文档核实，自动加载不了就按路径读 SKILL.md。'},
    'gemini': {'名字': 'Gemini CLI', '入口': 'GEMINI.md', '技能目录': '.agents/skills',
               '说明': '读 GEMINI.md，本脚本生成一个指回 AGENTS.md 的 GEMINI.md。'},
    'cursor': {'名字': 'Cursor', '入口': 'AGENTS.md', '技能目录': '.agents/skills',
               '说明': '读仓库根目录的 AGENTS.md，不用额外文件；技能按路径读 SKILL.md。'},
    'other': {'名字': '其他 Agent', '入口': 'AGENTS.md', '技能目录': '.agents/skills',
              '说明': '第一句话让它先读 AGENTS.md；技能按路径读 SKILL.md。'},
}

ENTRY_TEXT = {
    'CLAUDE.md': '# Claude Code 入口\n\n本仓库的规则写在 `AGENTS.md`，所有 Agent 共用这一份。Claude Code 用下面这行把它导入；改规则请改 `AGENTS.md`，不要改这里。\n\n@AGENTS.md\n',
    'GEMINI.md': f'{MARK}\n# Gemini CLI 入口\n\n本仓库的规则写在 `AGENTS.md`，所有 Agent 共用这一份。开工前先读它，改规则也只改它。\n\n@AGENTS.md\n',
}


def check_env():
    r = {}
    r['python'] = {'ok': sys.version_info >= (3, 9), '值': sys.version.split()[0], '要求': '3.9 以上'}
    r['Pillow'] = {'ok': importlib.util.find_spec('PIL') is not None,
                   '修法': 'python3 -m pip install -r requirements.txt'}
    mac = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'
    chrome = os.environ.get('CHROME') or (mac if Path(mac).exists() else None) or next(
        (shutil.which(n) for n in ('google-chrome', 'chromium', 'chromium-browser') if shutil.which(n)), None)
    r['Chrome'] = {'ok': bool(chrome), '值': chrome, '用途': '小红书卡片、封面排字截图；没有也能写稿排版',
                   '修法': '装 Chrome，或设置环境变量 CHROME=<浏览器路径>'}
    env = ROOT / '.env'
    key = False
    if env.exists():
        key = bool(re.search(r'^IMAGE_API_KEY=\S+', env.read_text(encoding='utf-8'), re.M))
    key = key or bool(os.environ.get('IMAGE_API_KEY'))
    codex = shutil.which('codex')
    r['生图'] = {'ok': key or bool(codex),
                 '值': 'OpenAI 兼容接口' if key else ('Codex CLI image_gen' if codex else '未配置'),
                 '修法': '在 .env 填 IMAGE_API_KEY（推荐，任何 Agent 都能用），或装 Codex CLI'}
    skills = sorted(p.parent.name for p in (ROOT / '.agents/skills').glob('*/SKILL.md'))
    r['技能'] = {'ok': bool(skills), '值': skills}
    return r


def check_identity():
    p = ROOT / '规则/01-我是谁.md'
    left = re.findall(r'`<[^`>]+>`', p.read_text(encoding='utf-8')) if p.exists() else []
    samples = [f for f in (ROOT / '语料/改稿对照/samples').glob('*.md')] if (ROOT / '语料/改稿对照/samples').exists() else []
    return {'身份空格': len(left), '身份文件': '规则/01-我是谁.md', '改稿样本': len(samples)}


def link_skills(target):
    """target 如 .claude/skills：建一个指向 .agents/skills 的链接；不行就报告"""
    dst = ROOT / target
    src = ROOT / '.agents/skills'
    if dst.is_dir() and (dst / 'gzh-design/SKILL.md').exists():
        return '已就绪'
    if dst.exists() or dst.is_symlink():
        if dst.is_file() and dst.stat().st_size < 200:  # Windows 上 git 把链接检出成了一行文本
            dst.unlink()
        else:
            return f'{target} 已存在但不是指向 .agents/skills 的链接，没动它'
    dst.parent.mkdir(parents=True, exist_ok=True)
    try:
        os.symlink(os.path.relpath(src, dst.parent), dst, target_is_directory=True)
        return '已建链接'
    except OSError:
        return f'建链接失败（Windows 可开开发者模式后重跑），或让 Agent 直接读 .agents/skills/<技能>/SKILL.md'


def write_entry(name):
    p = ROOT / name
    text = ENTRY_TEXT.get(name)
    if text is None or name == 'AGENTS.md':
        return '原生读 AGENTS.md，不用生成'
    if p.exists():
        old = p.read_text(encoding='utf-8')
        if '@AGENTS.md' in old:
            return '已就绪'
        if MARK not in old:
            return f'{name} 已存在且不是本脚本生成的，没覆盖；请在里面加一行 @AGENTS.md'
    p.write_text(text, encoding='utf-8')
    return '已生成'


def ensure_env_file():
    env, ex = ROOT / '.env', ROOT / '.env.example'
    if env.exists():
        return '已存在'
    if ex.exists():
        shutil.copyfile(ex, env)
        return '已从 .env.example 复制，密钥还空着'
    return '没有 .env.example'


def main():
    ap = argparse.ArgumentParser(description='一键配置公众号创作 Agent')
    ap.add_argument('--agent', nargs='*', default=[], help='claude codex kimi zcode gemini cursor other all')
    ap.add_argument('--json', action='store_true', help='输出 JSON')
    a = ap.parse_args()
    names = list(AGENTS) if 'all' in a.agent else a.agent
    bad = [n for n in names if n not in AGENTS]
    if bad:
        ap.error(f'不认识的 Agent：{bad}，可选 {list(AGENTS)} 或 all')

    actions = {}
    if names:
        actions['.env'] = ensure_env_file()
        for n in names:
            info = AGENTS[n]
            done = {'入口': write_entry(info['入口'])}
            if info['技能目录'] != '.agents/skills':
                done['技能'] = link_skills(info['技能目录'])
            done['说明'] = info['说明']
            actions[info['名字']] = done
    env = check_env()
    ident = check_identity()
    todo = [f"{k}：{v.get('修法', '')}" for k, v in env.items() if not v['ok']]
    if ident['身份空格']:
        todo.append(f"填 {ident['身份文件']}，还有 {ident['身份空格']} 处 `<…>` 空着（问作者，别替他编）")
    if not ident['改稿样本']:
        todo.append('语料/改稿对照/samples/ 还没有改稿样本，写满 3～5 篇人工改稿后再蒸馏口吻')
    out = {'仓库': str(ROOT), '环境': env, '身份与语料': ident, '本次配置': actions, '还要做': todo}

    if a.json:
        print(json.dumps(out, ensure_ascii=False, indent=2))
        return
    print(f'仓库：{ROOT}\n')
    print('环境检查')
    for k, v in env.items():
        val = v.get('值')
        val = '、'.join(val) if isinstance(val, list) else val
        print(f"  {'✓' if v['ok'] else '✗'} {k}" + (f'：{val}' if val else ''))
    if actions:
        print('\n本次配置')
        for k, v in actions.items():
            print(f'  {k}：' + ('；'.join(f'{a}={b}' for a, b in v.items()) if isinstance(v, dict) else v))
    else:
        print('\n（只做了检查。要配置就加 --agent <名字>，比如 --agent codex）')
    print('\n还要做' if todo else '\n全部就绪')
    for t in todo:
        print(f'  - {t}')


if __name__ == '__main__':
    main()

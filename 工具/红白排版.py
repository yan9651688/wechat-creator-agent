# 把教程 Markdown 排成 gzh-design 红白色系正文片段（组件 HTML 取自 theme-red-white.md）
# 用法：python3 -I 红白排版.py <配置.json> <文章 md> <输出 html>
# 只加样式，不改原文：下划线、加粗都是包在原文已有的字上。
# 分隔线和 END 线改成纯色：渐变可能触发公众号 darkmode-no-gradient 检测。
import base64
import html
import json
import os
import re
import sys

md_path = sys.argv[2]
out_path = sys.argv[3]
md_dir = os.path.dirname(os.path.abspath(md_path))
# 配置按文章目录名取
cfg = json.load(open(sys.argv[1], encoding='utf-8'))[os.path.basename(md_dir)]
text = open(md_path, encoding='utf-8').read().replace('\r\n', '\n')

FONT = "-apple-system,BlinkMacSystemFont,'PingFang SC','Hiragino Sans GB','Microsoft YaHei',sans-serif"
used = []  # 已经划过的短语，全文只划一次


def esc(s):
    return html.escape(s, quote=False)


def leaf(s):
    return '<span leaf="">' + esc(s) + '</span>'


def underline_spans(s, limit=3):
    """在段落里找配置的关键短语，按出现顺序最多包 limit 处淡粉下划线。"""
    hits = []
    for ph in cfg['phrases']:
        if ph in used:
            continue
        i = s.find(ph)
        if i >= 0 and not any(a < i + len(ph) and i < b for a, b, _ in hits):
            hits.append((i, i + len(ph), ph))
    hits.sort()
    hits = hits[:limit]
    for _, _, ph in hits:
        used.append(ph)
    out, pos = [], 0
    for a, b, _ in hits:
        if a > pos:
            out.append(leaf(s[pos:a]))
        out.append('<span style="border-bottom:2px solid #FECACA;font-weight:600;">' + leaf(s[a:b]) + '</span>')
        pos = b
    if pos < len(s):
        out.append(leaf(s[pos:]))
    return ''.join(out)


def para(s):
    m = re.match(r'^(第[一二三四五六七八九十]+：)(.*)$', s)
    if m:
        inner = '<strong>' + leaf(m.group(1)) + '</strong>' + underline_spans(m.group(2), 2)
    else:
        inner = underline_spans(s)
    return '<p style="margin-bottom:20px;font-size:15px;line-height:1.8;text-align:justify;">' + inner + '</p>'


def image(alt, src):
    with open(os.path.join(md_dir, src), 'rb') as f:
        data = 'data:image/jpeg;base64,' + base64.b64encode(f.read()).decode()
    mb = '8px' if alt else '10px'
    h = ('<section style="background:#FFF;border-radius:12px;padding:6px;border:1px solid #E5E7EB;'
         'box-shadow:0 4px 12px -2px rgba(0,0,0,0.08);margin-bottom:' + mb + ';">'
         '<section style="margin:0;border-radius:8px;overflow:hidden;">'
         '<span leaf=""><img src="' + data + '" style="max-width:100%;height:auto;display:block;margin:0 auto;"></span>'
         '</section></section>')
    if alt:
        h += '<p style="font-size:12px;color:#9CA3AF;text-align:center;margin:0 0 24px;">' + leaf('— ' + alt) + '</p>'
    return h


def table(rows):
    cells = [[c.strip() for c in r.strip().strip('|').split('|')] for r in rows]
    head, body = cells[0], [r for r in cells[2:]]
    th = ''.join('<th style="background:#DC2626;color:#fff;font-weight:700;padding:8px 12px;text-align:left;">'
                 + leaf(c) + '</th>' for c in head)
    trs = []
    for i, r in enumerate(body):
        bg = 'background:#FEF2F2;' if i % 2 else ''
        trs.append('<tr>' + ''.join('<td style="padding:8px 12px;border-bottom:1px solid #FEE2E2;color:#374151;' + bg + '">'
                                    + leaf(c) + '</td>' for c in r) + '</tr>')
    return ('<section style="margin-bottom:24px;overflow-x:auto;">'
            '<table style="width:100%;border-collapse:collapse;font-size:14px;">'
            '<thead><tr>' + th + '</tr></thead><tbody>' + ''.join(trs) + '</tbody></table></section>')


def aside(s):
    return ('<section style="border-left:4px solid #D6D3D1;padding:14px 20px;margin-bottom:24px;background:#FAFAFA;border-radius:0 8px 8px 0;">'
            '<p style="font-size:14px;color:#374151;margin:0;line-height:1.8;text-align:justify;">' + leaf(s) + '</p></section>')


def quote_card(q):
    parts, pos = [], 0
    for kw in cfg['quote_highlights']:
        i = q.find(kw, pos)
        if i < 0:
            continue
        if i > pos:
            parts.append(leaf(q[pos:i]))
        parts.append('<span style="background:#DC2626;color:#FFFFFF;padding:2px 8px;border-radius:4px;">' + leaf(kw) + '</span>')
        pos = i + len(kw)
    if pos < len(q):
        parts.append(leaf(q[pos:]))
    return ('<section style="margin:10px 10px 32px;background:#ffffff;border-radius:12px;box-shadow:0 4px 24px -4px rgba(220,38,38,0.15);padding:28px 24px 22px;overflow:hidden;">'
            '<p style="font-size:42px;color:#DC2626;font-weight:900;margin:0;line-height:0.6;">' + leaf('“') + '</p>'
            '<p style="font-size:16px;font-weight:800;color:#1C1917;margin:12px 0 8px;line-height:1.75;padding-left:4px;">' + ''.join(parts) + '</p>'
            '<p style="text-align:right;font-size:12px;color:#9CA3AF;margin:8px 0 0;letter-spacing:1px;">' + leaf('—— ' + cfg.get('author','作者')) + '</p>'
            '</section>')


def guide(points):
    cards = []
    for i, p in enumerate(points):
        mr = 'margin-right:8px;' if i < len(points) - 1 else ''
        cards.append('<section style="flex:1;background:#FEF2F2;border-radius:10px;padding:16px 12px;' + mr + 'text-align:center;border:1px solid #FEE2E2;">'
                     '<p style="display:inline-block;background:#DC2626;color:#FFFFFF;font-size:12px;font-weight:800;padding:2px 10px;border-radius:4px;margin:0 0 8px;">' + leaf('%02d' % (i + 1)) + '</p>'
                     '<p style="font-size:13px;font-weight:700;color:#1C1917;margin:0;">' + leaf(p) + '</p></section>')
    return ('<section style="padding:0 10px 32px;"><p style="font-size:14px;color:#9CA3AF;margin:0 0 14px;letter-spacing:1px;">' + leaf('📌 本文看点') + '</p>'
            '<section style="display:flex;justify-content:space-between;">' + ''.join(cards) + '</section></section>')


DIVIDER = ('<section style="padding:0 10px;"><section style="height:1px;background:#FCA5A5;margin:0;">'
           '<span leaf=""><br></span></section></section>')


def chapter_head(n, tag, title, first):
    mt = '16px' if first else '48px'
    return ('<section style="margin-top:' + mt + ';margin-bottom:28px;padding:0 10px;">'
            '<section style="display:flex;align-items:center;justify-content:space-between;margin-bottom:20px;padding-bottom:14px;border-bottom:3px solid #DC2626;">'
            '<section style="display:flex;align-items:center;">'
            '<span style="display:inline-block;background:#DC2626;color:#FFFFFF;font-size:18px;font-weight:900;padding:4px 14px;border-radius:6px;margin-right:14px;line-height:1.3;">' + leaf('%02d' % n) + '</span>'
            '<section><p style="font-size:10px;color:#DC2626;font-weight:700;letter-spacing:3px;margin:0 0 2px;text-transform:uppercase;">' + leaf(tag) + '</p>'
            '<h3 style="font-size:18px;font-weight:800;color:#1C1917;margin:0;letter-spacing:0.5px;">' + leaf(title) + '</h3></section>'
            '</section></section>')


END = ('<section style="padding:0 10px;"><section style="text-align:center;margin:0 0 32px;"><section style="display:flex;align-items:center;justify-content:center;">'
       '<span style="height:2px;width:60px;background:#DC2626;margin-right:12px;"><span leaf=""><br></span></span>'
       '<span style="font-size:11px;color:#DC2626;letter-spacing:3px;font-weight:700;"><span leaf="">END</span></span>'
       '<span style="height:2px;width:60px;background:#DC2626;margin-left:12px;"><span leaf=""><br></span></span>'
       '</section></section></section>')

# ---- 解析 ----
# ``` 围栏先抽出来，免得里面的空行把一段提示词拆成好几块
codes = []


def _keep_code(m):
    codes.append(m.group(1).split('\n'))
    return '\n\n\x00CODE%d\x00\n\n' % (len(codes) - 1)


text = re.sub(r'^```[^\n]*\n(.*?)\n```$', _keep_code, text, flags=re.S | re.M)
blocks = [b.strip() for b in re.split(r'\n\s*\n', text) if b.strip()]
title_line = blocks.pop(0)
assert title_line.startswith('# ')
quote = None
if blocks and blocks[0].startswith('> '):
    quote = blocks.pop(0)[2:].strip()
# 文末落款单独拿出来放签名区
sign = blocks.pop() if cfg.get('signoff_prefix') and cfg['signoff_prefix'] in blocks[-1] else None

out = []
# 封面放正文首图：公众号选封面时可以「从正文选择」，不用再上传一次
cover = os.path.join(md_dir, '配图', '封面-公众号.jpg')
if os.path.exists(cover):
    with open(cover, 'rb') as f:
        out.append('<section style="margin:0 0 20px;">'
                   '<span leaf=""><img src="data:image/jpeg;base64,' + base64.b64encode(f.read()).decode()
                   + '" style="width:100%;height:auto;display:block;"></span></section>')
if quote:
    out.append(quote_card(quote))
chapters = 0
in_chapter = False
pre = []


def code_block(lines):
    # common-components.md 1b 浅色代码块：每行一个 <p>，不用 white-space:pre，空行用全角空格占位
    p = ('<p style="margin:0;font-family:\'SF Mono\',Consolas,Monaco,monospace;font-size:13px;line-height:1.6;color:#24292F;">'
         '<span leaf="">{}</span></p>')
    return ('<section style="margin:0 0 20px;border-radius:8px;overflow:hidden;background:#F6F8FA;border:1px solid #E5E7EB;border-left:3px solid #DC2626;">'
            '<section style="padding:7px 14px;border-bottom:1px solid #E5E7EB;">'
            '<span style="font-size:12px;color:#9CA3AF;font-family:Consolas,Monaco,monospace;letter-spacing:1px;"><span leaf="">Prompt · 可直接复制</span></span></section>'
            '<section style="padding:11px 14px;">' + ''.join(p.format(esc(l) or '　') for l in lines) + '</section></section>')


def render_block(b):
    m = re.fullmatch(r'\x00CODE(\d+)\x00', b)
    if m:
        return code_block(codes[int(m.group(1))])
    if b.startswith('!['):
        m = re.match(r'!\[(.*?)\]\((.+?)\)', b)
        return image(m.group(1), m.group(2))
    if b.startswith('|'):
        return table(b.split('\n'))
    if b.startswith('> '):
        return aside(b[2:].strip())
    assert not b.startswith(('#', '-', '*', '1.')), '未处理的块：' + b[:30]
    return para(b.replace('\n', ''))


body = []
for b in blocks:
    if b.startswith('## '):
        if chapters == 0:
            out.append('<section style="padding:0 10px;">' + ''.join(pre) + '</section>')
            if cfg.get('guide'):
                out.append(guide(cfg['guide']))
        else:
            out.append(''.join(body) + '</section>')
            out.append(DIVIDER)
            body = []
        chapters += 1
        title = b[3:].strip()
        out.append(chapter_head(chapters, cfg['tags'][chapters - 1], title, chapters == 1))
        continue
    (pre if chapters == 0 else body).append(render_block(b))
out.append(''.join(body) + '</section>')
out.append(END)
if sign:
    out.append('<section style="padding:0 10px;"><p style="margin-bottom:20px;font-size:15px;line-height:1.8;text-align:justify;">'
               + leaf(sign) + '</p></section>')

html_out = ('<section style="max-width:677px;margin:0 auto;background:#ffffff;font-family:' + FONT +
            ';color:#374151;line-height:1.75;letter-spacing:0.5px;overflow-x:hidden;">' + ''.join(out) + '</section>')
open(out_path, 'w', encoding='utf-8').write(html_out)

assert chapters == len(cfg['tags']), f'章节数 {chapters} 和英文小标数 {len(cfg["tags"])} 不一致'
missing = [p for p in cfg['phrases'] if p not in used]
print(f'章节 {chapters}，图片 {html_out.count("<img ")}，下划线 {len(used)}，未用到的短语 {missing}')

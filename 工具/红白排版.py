# 把教程 Markdown 排成 gzh-design 红白色系正文片段（组件 HTML 取自 theme-red-white.md）
# 用法：python3 -I 红白排版.py <配置.json> <文章 md> <输出 html>
# 只加样式，不改原文：下划线、加粗都是包在原文已有的字上。
# 分隔线和 END 线改成纯色：渐变可能触发公众号 darkmode-no-gradient 检测。
import base64
import html
import hashlib
import json
import mimetypes
import os
import re
import sys
import tempfile
from pathlib import Path

FONT = "-apple-system,BlinkMacSystemFont,'PingFang SC','Hiragino Sans GB','Microsoft YaHei',sans-serif"
used = []  # 已经划过的短语，全文只划一次


def esc(s):
    return html.escape(s, quote=False)


def leaf(s):
    return '<span leaf="">' + esc(s).replace('\n', '<br>') + '</span>'


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
        mime = mimetypes.guess_type(src)[0]
        if mime not in {'image/jpeg', 'image/png', 'image/gif', 'image/webp'}:
            raise ValueError('不支持的图片类型：' + src)
        data = 'data:' + mime + ';base64,' + base64.b64encode(f.read()).decode()
    mb = '8px' if alt else '10px'
    h = ('<section style="background:#FFF;border-radius:12px;padding:6px;border:1px solid #E5E7EB;'
         'box-shadow:0 4px 12px -2px rgba(0,0,0,0.08);margin-bottom:' + mb + ';">'
         '<section style="margin:0;border-radius:8px;overflow:hidden;">'
         '<span leaf=""><img src="' + data + '" style="max-width:100%;height:auto;display:block;margin:0 auto;"></span>'
         '</section></section>')
    if alt:
        h += '<p style="font-size:12px;color:#9CA3AF;text-align:center;margin:0 0 24px;">' + leaf(alt) + '</p>'
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

# ---- 解析与输出 ----
# 按行识别结构，标题、图片和代码块不依赖前后有空行。
HEADING = re.compile(r"^ {0,3}(#{1,6})[ \t]+(.+)$")
FENCE = re.compile(r"^ {0,3}(`{3,}|~{3,})(.*)$")
IMAGE = re.compile(r"!\[(.*?)\]\(([^\n]+?)\)")
TABLE_RULE = re.compile(r"^:?-{3,}:?$")


def parse_blocks(text):
    lines = text.splitlines()
    blocks, paragraph = [], []

    def flush():
        if paragraph:
            blocks.append(('paragraph', '\n'.join(paragraph)))
            paragraph.clear()

    i = 0
    while i < len(lines):
        line = lines[i]
        if not line.strip():
            flush()
            i += 1
            continue
        fence = FENCE.match(line)
        heading = HEADING.match(line)
        images = list(IMAGE.finditer(line))
        if fence:
            flush()
            marker = fence.group(1)
            closing = re.compile(r'^ {0,3}' + re.escape(marker[0]) +
                                 '{' + str(len(marker)) + r',}[ \t]*$')
            code = []
            i += 1
            while i < len(lines) and not closing.match(lines[i]):
                code.append(lines[i])
                i += 1
            if i == len(lines):
                raise ValueError('代码围栏未闭合，未生成排版文件')
            blocks.append(('code', code))
        elif heading:
            flush()
            blocks.append(('heading' + str(len(heading.group(1))), heading.group(2)))
        elif images and not IMAGE.sub('', line).strip():
            flush()
            blocks.extend(('image', (m.group(1), m.group(2))) for m in images)
        elif line.lstrip().startswith('!['):
            raise ValueError('图片必须独占一行；请把同一行的正文另起一行：' + line)
        elif line.startswith('>'):
            flush()
            quote = []
            while i < len(lines) and lines[i].startswith('>'):
                content = lines[i][1:]
                quote.append(content[1:] if content.startswith(' ') else content)
                i += 1
            blocks.append(('quote', '\n'.join(quote)))
            continue
        elif line.lstrip().startswith('|'):
            flush()
            rows = []
            while i < len(lines) and lines[i].lstrip().startswith('|'):
                rows.append(lines[i])
                i += 1
            cells = [[c.strip() for c in row.strip().strip('|').split('|')] for row in rows]
            if len(cells) >= 2 and all(TABLE_RULE.fullmatch(c) for c in cells[1]):
                if any(len(row) != len(cells[0]) for row in cells[1:]):
                    raise ValueError('表格列数不一致，未生成排版文件')
                blocks.append(('table', rows))
            else:
                # 不是 Markdown 表格的竖线文本照原样保留，不吞第二行。
                blocks.append(('paragraph', '\n'.join(rows)))
            continue
        else:
            paragraph.append(line)
        i += 1
    flush()
    return blocks


def code_block(lines):
    # 保留代码里的缩进和空行；不插入全角空格冒充源文本。
    return ('<section style="margin:0 0 20px;border-radius:8px;overflow:hidden;background:#F6F8FA;border:1px solid #E5E7EB;border-left:3px solid #DC2626;">'
            '<section style="padding:7px 14px;border-bottom:1px solid #E5E7EB;">'
            '<span style="font-size:12px;color:#9CA3AF;font-family:Consolas,Monaco,monospace;letter-spacing:1px;"><span leaf="">Prompt · 可直接复制</span></span></section>'
            '<section style="padding:11px 14px;">'
            '<p style="margin:0;white-space:pre-wrap;overflow-wrap:anywhere;font-family:Consolas,Monaco,monospace;font-size:13px;line-height:1.6;color:#24292F;">'
            '<span leaf="">' + esc('\n'.join(lines)) + '</span></p></section></section>')


def render_block(block):
    kind, content = block
    if kind == 'code':
        return code_block(content)
    if kind == 'image':
        return image(*content)
    if kind == 'table':
        return table(content)
    if kind == 'quote':
        return aside(content)
    if kind.startswith('heading'):
        return ('<h4 style="border-left:4px solid #DC2626;padding-left:12px;font-size:16px;line-height:1.8;margin:24px 0 16px;">'
                + leaf(content) + '</h4>')
    return para(content)


def render(text):
    blocks = parse_blocks(text)
    if not blocks or blocks[0][0] != 'heading1':
        raise ValueError('文章第一行需要是 # 标题')
    # 公众号标题由复制页单独提供，正文不重复插入。
    blocks.pop(0)
    count = sum(kind == 'heading2' for kind, _ in blocks)
    if count != len(cfg['tags']):
        raise ValueError(f'章节数 {count} 和英文小标数 {len(cfg["tags"])} 不一致')

    quote = blocks.pop(0)[1] if blocks and blocks[0][0] == 'quote' else None
    sign = None
    prefix = cfg.get('signoff_prefix')
    if prefix and blocks and blocks[-1][0] == 'paragraph' and blocks[-1][1].startswith(prefix):
        sign = blocks.pop()[1]

    out = []
    cover = Path(md_dir) / '配图' / '封面-公众号.jpg'
    # 源稿已放首图时不再重复插入同一封面。
    explicit_cover = any(kind == 'image' and (Path(md_dir) / content[1]).resolve() == cover.resolve()
                         for kind, content in blocks)
    if cover.exists() and not explicit_cover:
        out.append(image('', str(cover)))
    if quote is not None:
        out.append(quote_card(quote))

    chapters, body = 0, []
    for block in blocks:
        kind, content = block
        if kind == 'heading2':
            if chapters == 0:
                out.append('<section style="padding:0 10px;">' + ''.join(body) + '</section>')
                if cfg.get('guide'):
                    out.append(guide(cfg['guide']))
            else:
                out.append(''.join(body) + '</section>')
                out.append(DIVIDER)
            body = []
            chapters += 1
            out.append(chapter_head(chapters, cfg['tags'][chapters - 1], content, chapters == 1))
        else:
            body.append(render_block(block))
    if chapters:
        out.append(''.join(body) + '</section>')
    else:
        out.append('<section style="padding:0 10px;">' + ''.join(body) + '</section>')
    out.append(END)
    if sign is not None:
        out.append('<section style="padding:0 10px;">' + para(sign) + '</section>')
    return ('<section style="max-width:677px;margin:0 auto;background:#ffffff;font-family:' + FONT +
            ';color:#374151;line-height:1.75;letter-spacing:0.5px;overflow-x:hidden;">' + ''.join(out) + '</section>'), chapters


def same_file(a, b):
    return a.resolve() == b.resolve() or (a.exists() and b.exists() and os.path.samefile(a, b))


def main(argv=None):
    global cfg, md_dir, used
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) != 3:
        print('用法：python3 -I 红白排版.py <配置.json> <文章 md> <输出 html>', file=sys.stderr)
        return 2
    config_path, md_path, out_path = map(Path, argv)
    try:
        if any(same_file(out_path, source) for source in (config_path, md_path)):
            raise ValueError('输出路径不能覆盖源稿或配置（含软链接和硬链接）')
        original = md_path.read_bytes()
        source_hash = hashlib.sha256(original).hexdigest()
        config_bytes = config_path.read_bytes()
        md_dir = str(md_path.resolve().parent)
        settings = json.loads(config_bytes)
        if not isinstance(settings, dict):
            raise ValueError('配置顶层必须是按文章目录名组织的对象')
        cfg = settings.get(Path(md_dir).name)
        if not isinstance(cfg, dict):
            raise ValueError('配置中缺少文章目录：' + Path(md_dir).name)
        for key in ('tags', 'phrases', 'quote_highlights'):
            if key not in cfg or not isinstance(cfg[key], list) or not all(isinstance(v, str) and v for v in cfg[key]):
                raise ValueError(key + ' 必须是字符串列表，可留空列表')
        if 'guide' in cfg and (not isinstance(cfg['guide'], list) or not all(isinstance(v, str) for v in cfg['guide'])):
            raise ValueError('guide 必须是字符串列表')
        for key in ('author', 'signoff_prefix'):
            if key in cfg and not isinstance(cfg[key], str):
                raise ValueError(key + ' 必须是字符串')
        used = []
        html_out, chapters = render(original.decode('utf-8').replace('\r\n', '\n'))
        html_out = html_out.replace('<section ', '<section data-source-file="' + html.escape(md_path.name, quote=True) +
                                    '" data-source-sha256="' + source_hash + '" ', 1)
        if hashlib.sha256(md_path.read_bytes()).hexdigest() != source_hash or config_path.read_bytes() != config_bytes:
            raise ValueError('排版期间源稿或配置发生变化，请重新排版')
        # 全部解析与校验完成后才替换输出；失败不留下半份成品。
        if any(same_file(out_path, source) for source in (config_path, md_path)):
            raise ValueError('输出路径不能覆盖源稿或配置')
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=out_path.parent,
                                             prefix='.' + out_path.name + '.', delete=False) as f:
                temporary = Path(f.name)
                f.write(html_out)
            os.replace(temporary, out_path)
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
        missing = [p for p in cfg['phrases'] if p not in used]
        print(f'章节 {chapters}，图片 {html_out.count("<img ")}，下划线 {len(used)}，未用到的短语 {missing}')
        print(f'源稿 SHA-256：{source_hash}（排版前后相同）')
        return 0
    except (OSError, ValueError, TypeError, KeyError) as error:
        print('排版失败：' + str(error), file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())

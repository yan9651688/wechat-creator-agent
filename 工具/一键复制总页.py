# 把几篇红白风成品和封面打包成一个一键复制页
# 用法：python3 -I 一键复制总页.py <文章根目录> <输出 html> <目录名>...
# 每篇：复制标题、复制摘要、复制正文（富文本）、复制/下载两张封面
import base64
import hashlib
import html
from html.parser import HTMLParser
import io
import os
from pathlib import Path
import re
import sys
import tempfile


def jpg_uri(path):
    # 只在确实转换封面时加载，可先完成版本和输入路径检查。
    from PIL import Image
    buf = io.BytesIO()
    with Image.open(path) as image:
        image.convert('RGB').save(buf, 'JPEG', quality=90)
    return 'data:image/jpeg;base64,' + base64.b64encode(buf.getvalue()).decode()


class SourceMetadata(HTMLParser):
    def __init__(self, content):
        super().__init__()
        self.attributes = None
        self.feed(content)

    def handle_starttag(self, tag, attrs):
        if self.attributes is None:
            self.attributes = attrs if tag == 'section' else []


def source_for_body(directory, content):
    attrs = SourceMetadata(content).attributes or []
    metadata = [(k, v) for k, v in attrs if k in ('data-source-file', 'data-source-sha256')]
    if not metadata:
        print('旧排版缺少源稿版本标记，无法校验正文版本，建议重新排版', file=sys.stderr)
        # 兼容旧排版文件；没有版本标记时只能按定稿优先取标题与摘要。
        for name in ('2-定稿.md', '1-自改稿.md'):
            path = directory / name
            if path.is_file():
                return path, path.read_bytes()
        raise ValueError(str(directory) + ' 缺少定稿或自改稿')
    if len(metadata) != 2 or len(dict(metadata)) != 2:
        raise ValueError('排版文件的源稿版本标记不完整或重复，请重新排版')
    values = dict(metadata)
    name, expected = values['data-source-file'], values['data-source-sha256']
    if not name or name in ('.', '..') or '/' in name or '\\' in name:
        raise ValueError('排版文件的源稿标记必须是同目录文件名')
    if not expected or not re.fullmatch('[0-9a-fA-F]{64}', expected):
        raise ValueError('排版文件的源稿 SHA-256 无效，请重新排版')
    path = directory / name
    if path.resolve().parent != directory.resolve():
        raise ValueError('排版文件指向的源稿不在文章目录内')
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != expected.lower():
        raise ValueError(str(path) + ' 与排版文件版本不一致，请先重新排版')
    return path, raw


def same_file(a, b):
    return a.resolve() == b.resolve() or (a.exists() and b.exists() and os.path.samefile(a, b))


def build_page(cards, navs):
    return f'''<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>文章一键复制</title>
<style>
:root{{--red:#DC2626;--ink:#1C1917;--paper:#FAF7F2;--line:#E7E1D8;--mute:#78716C}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--paper);color:var(--ink);font:15px/1.7 -apple-system,'PingFang SC','Microsoft YaHei',sans-serif}}
header{{position:sticky;top:0;z-index:5;background:#fff;border-bottom:2px solid var(--red);padding:12px 16px}}
header h1{{margin:0 0 6px;font-size:18px}}header nav{{display:flex;flex-wrap:wrap;gap:6px}}
header nav a{{color:var(--ink);text-decoration:none;border:1px solid var(--line);padding:2px 10px;font-size:13px}}
header nav a:hover{{border-color:var(--red);color:var(--red)}}
main{{max-width:880px;margin:0 auto;padding:16px}}
.card{{background:#fff;border:1px solid var(--line);border-top:4px solid var(--red);padding:18px 18px 8px;margin:0 0 22px;scroll-margin-top:90px}}
.no{{color:var(--red);font-weight:800;letter-spacing:2px;font-size:13px}}.card h2{{margin:0 0 10px;font-size:20px}}
.row{{display:flex;gap:10px;align-items:flex-start;border-top:1px dashed var(--line);padding:10px 0}}
.row label{{flex:0 0 36px;color:var(--mute);font-size:13px;padding-top:2px}}.row p{{flex:1;margin:0;word-break:break-all}}
.row.main p{{color:var(--mute);font-size:13px}}.row a{{color:var(--red)}}
button,.btn{{flex:0 0 auto;cursor:pointer;border:1px solid var(--ink);background:#fff;color:var(--ink);font:13px/1 inherit;padding:7px 12px;text-decoration:none;display:inline-block}}
button:hover,.btn:hover{{border-color:var(--red);color:var(--red)}}button.red{{background:var(--red);border-color:var(--red);color:#fff}}
.covers{{display:grid;grid-template-columns:2.35fr 1fr;gap:12px;border-top:1px dashed var(--line);padding:12px 0}}
figure{{margin:0}}figure img{{width:100%;display:block;border:1px solid var(--line)}}
figcaption{{display:flex;justify-content:space-between;align-items:center;gap:6px;flex-wrap:wrap;font-size:12px;color:var(--mute);margin-top:6px}}
figcaption span{{display:flex;gap:6px}}
#toast{{position:fixed;left:50%;bottom:28px;transform:translateX(-50%);background:var(--ink);color:#fff;padding:9px 18px;font-size:14px;opacity:0;transition:opacity .2s;pointer-events:none}}#toast.show{{opacity:1}}
@media (max-width:600px){{.covers{{grid-template-columns:1fr}}.row{{flex-wrap:wrap}}.row p{{flex-basis:calc(100% - 46px)}}.row button{{margin-left:46px}}}}
</style></head><body>
<header><h1>文章 · 一键复制</h1><nav>{''.join(navs)}</nav></header>
<main>{''.join(cards)}</main><div id="toast"></div>
<script>
function toast(m){{var t=document.getElementById('toast');t.textContent=m;t.classList.add('show');clearTimeout(t._h);t._h=setTimeout(function(){{t.classList.remove('show')}},2400)}}
function put(htmlStr,text){{var ok=false,ta=document.createElement('textarea'),h=function(e){{e.clipboardData.setData('text/plain',text);if(htmlStr)e.clipboardData.setData('text/html',htmlStr);e.preventDefault()}};
document.addEventListener('copy',h,{{once:true}});ta.value=text;ta.style.position='fixed';ta.style.left='-9999px';document.body.appendChild(ta);ta.select();
try{{ok=document.execCommand('copy')}}catch(e){{}}ta.remove();document.removeEventListener('copy',h);return ok}}
function copyText(id){{toast(put(null,document.getElementById(id).textContent)?'已复制':'复制失败，请手动选中复制')}}
function copyRich(id){{var tpl=document.getElementById(id),d=document.createElement('div');d.appendChild(tpl.content.cloneNode(true));
toast(put(tpl.innerHTML.trim(),d.innerText)?'正文已复制，去公众号编辑器粘贴':'复制失败，请用「单独打开预览」')}}
async function copyImg(id){{try{{var b=await (await fetch(document.getElementById(id).src)).blob();
var png=await new Promise(function(r){{var i=new Image();i.onload=function(){{var c=document.createElement('canvas');c.width=i.naturalWidth;c.height=i.naturalHeight;c.getContext('2d').drawImage(i,0,0);c.toBlob(r,'image/png')}};i.src=URL.createObjectURL(b)}});
await navigator.clipboard.write([new ClipboardItem({{'image/png':png}})]);toast('图片已复制')}}catch(e){{toast('浏览器不让复制图片，点「下载」')}}}}
</script></body></html>'''


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) < 3:
        print('用法：python3 -I 一键复制总页.py <文章根目录> <输出 html> <目录名>...', file=sys.stderr)
        return 2
    root, out_path, *dirs = argv
    output = Path(out_path)
    cards, navs, inputs = [], [], {}
    try:
        for i, d in enumerate(dirs):
            directory = Path(root) / d
            p = str(directory)
            bodies = sorted(f for f in directory.glob('*_排版_*.html')
                            if not f.name.endswith(('_预览.html', '副本.html')))
            if len(bodies) != 1:
                raise ValueError(str(directory) + ' 应当只有一个正文排版 HTML，实际找到 ' + str(len(bodies)))
            body_path = bodies[0]
            body_bytes = body_path.read_bytes()
            content = body_bytes.decode('utf-8').strip()
            md_path, md_bytes = source_for_body(directory, content)
            inputs[body_path] = body_bytes
            inputs[md_path] = md_bytes
            md = md_bytes.decode('utf-8').splitlines()
            if not md or not md[0].startswith('# '):
                raise ValueError(str(md_path) + ' 第一行需要是 # 标题')
            title = md[0][2:].strip()
            summary = next((line[2:].strip() for line in md[1:] if line.startswith('> ')), '')
            preview = os.path.relpath(str(body_path)[:-5] + '_预览.html', os.path.dirname(out_path))
            covers = [(n, os.path.join(p, '配图', f)) for n, f in
                      (('公众号头条 2.35:1', '封面-公众号.png'), ('次条 / 分享卡 1:1', '封面-1比1.png'))]
            short = os.path.basename(d).split('-', 3)[-1]
            navs.append(f'<a href="#a{i}">{html.escape(short)}</a>')
            for _, cover_path in covers:
                path = Path(cover_path)
                inputs[path] = path.read_bytes()
            if any(same_file(output, path) for path in inputs):
                raise ValueError('输出路径不能覆盖源稿、正文 HTML 或封面（含软链接和硬链接）')
            cover_html = ''.join(
                f'<figure><img id="c{i}_{k}" src="{jpg_uri(f)}" alt="">'
                f'<figcaption>{n}<span><button onclick="copyImg(\'c{i}_{k}\')">复制图片</button>'
                f'<a class="btn" download="{html.escape(short)}-{os.path.basename(f)[:-4]}.jpg" '
                f'href="" onclick="this.href=document.getElementById(\'c{i}_{k}\').src">下载</a></span></figcaption></figure>'
                for k, (n, f) in enumerate(covers))
            cards.append(f'''<section class="card" id="a{i}">
        <div class="no">{i + 1:02d}</div><h2>{html.escape(short)}</h2>
        <div class="row"><label>标题</label><p id="t{i}">{html.escape(title)}</p><button onclick="copyText('t{i}')">复制</button></div>
        <div class="row"><label>摘要</label><p id="s{i}">{html.escape(summary)}</p><button onclick="copyText('s{i}')">复制</button></div>
        <div class="row main"><label>正文</label><p>红白风排版，图片已内嵌。<a href="{html.escape(preview)}" target="_blank">单独打开预览</a></p><button class="red" onclick="copyRich('b{i}')">复制正文到公众号</button></div>
        <template id="b{i}">{content}</template>
        <div class="covers">{cover_html}</div>
        </section>''')


        page = build_page(cards, navs)
        if any(same_file(output, path) for path in inputs):
            raise ValueError('输出路径不能覆盖输入文件')
        if any(path.read_bytes() != raw for path, raw in inputs.items()):
            raise ValueError('打包期间源稿、正文或封面发生变化，请重新生成')
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=output.parent,
                                             prefix='.' + output.name + '.', delete=False) as f:
                temporary = Path(f.name)
                f.write(page)
            os.replace(temporary, output)
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
        print(out_path, round(len(page) / 1e6, 1), 'MB')
        return 0
    except (OSError, ValueError, ImportError) as error:
        print('打包失败：' + str(error), file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())

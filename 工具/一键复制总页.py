# 把几篇红白风成品和封面打包成一个一键复制页
# 用法：python3 -I 一键复制总页.py <文章根目录> <输出 html> <目录名>...
# 每篇：复制标题、复制摘要、复制正文（富文本，和预览页同一种写法）、复制/下载两张封面
import base64
import glob
import html
import io
import os
import sys

from PIL import Image

root, out_path, dirs = sys.argv[1], sys.argv[2], sys.argv[3:]


def jpg_uri(path):
    buf = io.BytesIO()
    Image.open(path).convert('RGB').save(buf, 'JPEG', quality=90)
    return 'data:image/jpeg;base64,' + base64.b64encode(buf.getvalue()).decode()


cards, navs = [], []
for i, d in enumerate(dirs):
    p = os.path.join(root, d)
    md = open(os.path.join(p, '1-自改稿.md'), encoding='utf-8').read().split('\n')
    title = md[0][2:].strip()
    summary = next((l[2:].strip() for l in md[1:] if l.startswith('> ')), '')
    body = [f for f in glob.glob(os.path.join(p, '*_排版_*.html'))
            if not f.endswith(('_预览.html', '副本.html'))]
    assert len(body) == 1, body
    content = open(body[0], encoding='utf-8').read().strip()
    preview = os.path.relpath(body[0][:-5] + '_预览.html', os.path.dirname(out_path))
    covers = [(n, os.path.join(p, '配图', f)) for n, f in
              (('公众号头条 2.35:1', '封面-公众号.png'), ('次条 / 分享卡 1:1', '封面-1比1.png'))]
    short = os.path.basename(d).split('-', 3)[-1]
    navs.append(f'<a href="#a{i}">{html.escape(short)}</a>')
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

page = f'''<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">
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
open(out_path, 'w', encoding='utf-8').write(page)
print(out_path, round(len(page) / 1e6, 1), 'MB')

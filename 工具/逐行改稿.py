# 逐行改稿：左边 1-自改稿.md 原文（只读）+ 预判，右边可改，保存写 2-定稿.md
# 用法：python3 -I 工具/逐行改稿.py <文章目录> [端口，默认 8765]
# 浏览器打开 http://localhost:8765 ，改完点「保存」或按 ⌘S。
import difflib
import json
import os
import re
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = DST = HINTS = ''


def setup(d):
    """指定文章目录：读 1-自改稿.md，写 2-定稿.md，预判读 改稿对照.md（可选）"""
    global SRC, DST, HINTS
    if not os.path.isabs(d) and not os.path.isdir(d):
        d = os.path.join(ROOT, d)
    d = os.path.abspath(d)
    if not os.path.exists(os.path.join(d, '1-自改稿.md')):
        sys.exit(f'找不到 {os.path.join(d, "1-自改稿.md")}')
    SRC = os.path.join(d, '1-自改稿.md')
    DST = os.path.join(d, '2-定稿.md')
    HINTS = os.path.join(d, '改稿对照.md')
    return d


def blocks(text):
    """按空行切段，``` 围栏里的空行不切。返回 [(段文字, 起始行号)]"""
    out, cur, start, fence = [], [], 1, False
    for i, line in enumerate(text.split('\n'), 1):
        if line.startswith('```'):
            fence = not fence
        if not fence and not line.strip():
            if cur:
                out.append(('\n'.join(cur), start))
                cur = []
            continue
        if not cur:
            start = i
        cur.append(line)
    if cur:
        out.append(('\n'.join(cur), start))
    return out


def hints():
    h = {}
    if not os.path.exists(HINTS):
        return h
    for line in open(HINTS, encoding='utf-8'):
        cells = [c.strip() for c in line.strip().strip('|').split('|')]
        if len(cells) < 3:
            continue
        m = re.match(r'L(\d+)', cells[0])
        if m and cells[-1] not in ('—', '-', ''):
            h.setdefault(int(m.group(1)), []).append(cells[-1].replace('**', ''))
    return h


def rows():
    src = blocks(open(SRC, encoding='utf-8').read())
    a = [b for b, _ in src]
    if os.path.exists(DST):
        b = [x for x, _ in blocks(open(DST, encoding='utf-8').read())]
    else:
        b = list(a)
    right = [None] * len(a)
    extra_before = []  # 定稿开头多出来、对不上原文的段
    sm = difflib.SequenceMatcher(None, a, b, autojunk=False)
    last = -1
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == 'equal' or (tag == 'replace' and i2 - i1 == j2 - j1):
            for k in range(i2 - i1):
                right[i1 + k] = b[j1 + k]
            last = i2 - 1
        elif tag == 'replace':
            for k in range(i1, i2):
                right[k] = ''
            right[i1] = '\n\n'.join(b[j1:j2])
            last = i2 - 1
        elif tag == 'delete':
            for k in range(i1, i2):
                right[k] = ''
            last = i2 - 1
        elif tag == 'insert':
            add = '\n\n'.join(b[j1:j2])
            if last < 0:
                extra_before.append(add)
            else:
                right[last] = (right[last] + '\n\n' + add) if right[last] else add
    if extra_before and right:
        right[0] = '\n\n'.join(extra_before + [right[0] or ''])
    h = hints()
    out = []
    for (txt, ln), r in zip(src, right):
        out.append({'line': ln, 'src': txt, 'cur': r if r is not None else txt,
                    'hint': ' / '.join(h.get(ln, [])),
                    'kind': 'code' if txt.startswith('```') else 'img' if txt.startswith('![') else 'text'})
    return out


PAGE = r'''<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>逐行改稿</title>
<style>
:root{--bg:#f6f4ef;--card:#fff;--ink:#1f1b18;--mute:#8a8178;--red:#c62a1f;--chg:#fff6d6;--line:#e6e0d6}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.75 -apple-system,"PingFang SC",sans-serif}
header{position:sticky;top:0;z-index:5;background:var(--card);border-bottom:1px solid var(--line);padding:10px 20px;display:flex;gap:14px;align-items:center}
header b{font-size:16px}header .s{color:var(--mute);font-size:13px;flex:1}
button{font:inherit;border:0;border-radius:6px;padding:6px 14px;cursor:pointer;background:var(--red);color:#fff}
button.g{background:#eee;color:var(--ink)}
main{max-width:1400px;margin:0 auto;padding:16px 20px 80px}
.row{display:grid;grid-template-columns:44px 1fr 1fr;gap:12px;padding:10px 0;border-bottom:1px dashed var(--line)}
.ln{color:var(--mute);font-size:12px;padding-top:6px;text-align:right}
.src{white-space:pre-wrap;padding:6px 10px;background:#fbfaf7;border-radius:6px}
.hint{margin-top:6px;font-size:13px;color:var(--red)}.hint:before{content:"预判："}
textarea{width:100%;font:inherit;line-height:1.75;color:var(--ink);border:1px solid var(--line);border-radius:6px;padding:6px 10px;resize:vertical;background:var(--card);field-sizing:content;min-height:44px}
textarea:focus{outline:2px solid #e9b4ae;border-color:transparent}
.row.chg textarea{background:var(--chg)}
.row.code .src,.row.code textarea{font:12px/1.6 ui-monospace,Menlo,monospace;max-height:140px;overflow:auto}
.row.img .src{color:var(--mute);font-size:13px}
.del{color:var(--red);font-size:12px}
ins{background:#d9f2d9;text-decoration:none}del{background:#f8d4d0}
.df{font-size:13px;margin-top:6px;white-space:pre-wrap;color:#555}
</style></head><body>
<header><b>逐行改稿</b><span class="s" id="st">左边是自改稿（只读），右边改，黄底是改过的。⌘S 保存到 2-定稿.md</span>
<button class="g" onclick="onlyChg()" id="fb">只看改过的</button><button onclick="save()">保存</button></header>
<main id="m"></main>
<script>
const R=__ROWS__;let dirty=false,only=false;
const m=document.getElementById('m');
function esc(s){return s.replace(/[&<>]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;'}[c]))}
function diff(a,b){const n=a.length,k=b.length;if(n*k>400000)return '';const dp=Array.from({length:n+1},()=>new Uint16Array(k+1));
for(let i=n-1;i>=0;i--)for(let j=k-1;j>=0;j--)dp[i][j]=a[i]===b[j]?dp[i+1][j+1]+1:Math.max(dp[i+1][j],dp[i][j+1]);
let i=0,j=0,o='';while(i<n&&j<k){if(a[i]===b[j]){o+=esc(a[i]);i++;j++}else if(dp[i+1][j]>=dp[i][j+1]){o+='<del>'+esc(a[i++])+'</del>'}else{o+='<ins>'+esc(b[j++])+'</ins>'}}
while(i<n)o+='<del>'+esc(a[i++])+'</del>';while(j<k)o+='<ins>'+esc(b[j++])+'</ins>';return o.replace(/<\/del><del>/g,'').replace(/<\/ins><ins>/g,'')}
R.forEach((r,i)=>{const d=document.createElement('div');d.className='row '+r.kind;d.innerHTML=
`<div class="ln">L${r.line}</div><div><div class="src">${esc(r.src)}</div>${r.hint?`<div class="hint">${esc(r.hint)}</div>`:''}</div>
<div><textarea spellcheck="false"></textarea><div class="df"></div></div>`;
const t=d.querySelector('textarea');t.value=r.cur;t.oninput=()=>{dirty=true;upd(d,r,t);st('未保存')};m.appendChild(d);upd(d,r,t)});
function upd(d,r,t){const c=t.value!==r.src;d.classList.toggle('chg',c);d.querySelector('.df').innerHTML=c?(t.value.trim()?diff(r.src,t.value):'<span class="del">这段删掉了</span>'):'';
if(only)d.style.display=c?'':'none'}
function onlyChg(){only=!only;document.getElementById('fb').textContent=only?'看全部':'只看改过的';
document.querySelectorAll('.row').forEach((d,i)=>{d.style.display=(!only||d.classList.contains('chg'))?'':'none'})}
function st(s){document.getElementById('st').textContent=s}
async function save(){const parts=[...document.querySelectorAll('textarea')].map(t=>t.value.replace(/\s+$/,'')).filter(v=>v.trim());
const r=await fetch('/save',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({text:parts.join('\n\n')+'\n'})});
const j=await r.json();if(j.ok){dirty=false;st('已保存 '+new Date().toLocaleTimeString()+'，改了 '+document.querySelectorAll('.row.chg').length+' 段')}else st('保存失败：'+j.err)}
addEventListener('keydown',e=>{if((e.metaKey||e.ctrlKey)&&e.key==='s'){e.preventDefault();save()}});
addEventListener('beforeunload',e=>{if(dirty){e.preventDefault();e.returnValue=''}});
</script></body></html>'''


class H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _send(self, code, body, ctype):
        b = body.encode('utf-8')
        self.send_response(code)
        self.send_header('Content-Type', ctype)
        self.send_header('Content-Length', str(len(b)))
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()
        self.wfile.write(b)

    def do_GET(self):
        if self.path not in ('/', '/index.html'):
            return self._send(404, 'not found', 'text/plain; charset=utf-8')
        data = json.dumps(rows(), ensure_ascii=False).replace('</', '<\\/')
        self._send(200, PAGE.replace('__ROWS__', data), 'text/html; charset=utf-8')

    def do_POST(self):
        if self.path != '/save':
            return self._send(404, '{}', 'application/json')
        try:
            n = int(self.headers.get('Content-Length', 0))
            text = json.loads(self.rfile.read(n))['text']
            tmp = DST + '.tmp'
            with open(tmp, 'w', encoding='utf-8') as f:
                f.write(text)
            os.replace(tmp, DST)
            print('已保存', DST, flush=True)
            self._send(200, '{"ok":true}', 'application/json')
        except Exception as e:
            self._send(500, json.dumps({'ok': False, 'err': str(e)}, ensure_ascii=False), 'application/json')


def main():
    if len(sys.argv) < 2:
        sys.exit('用法：python3 -I 工具/逐行改稿.py <文章目录> [端口，默认 8765]')
    d = setup(sys.argv[1])
    port = int(sys.argv[2]) if len(sys.argv) > 2 else 8765
    print(f'逐行改稿：{d}\n打开 http://localhost:{port}', flush=True)
    HTTPServer(('127.0.0.1', port), H).serve_forever()


if __name__ == '__main__':
    main()

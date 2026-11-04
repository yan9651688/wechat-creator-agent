#!/usr/bin/env python3
"""把分镜里的每张卡片渲染成 1242×1660 的小红书竖图。

用法：python3 -I 工具/小红书卡片.py <小红书目录> [卡片名...]
      目录里要有 分镜.json，输出到 <小红书目录>/卡片/<名字>.png
      不写卡片名就全部渲染。

分镜.json 的格式：
  {"theme": "红白",                      # 目前只有红白
   "cards": [{"name": "01-封面A",
              "bg": "底图/封面A-物件.png",  # 可选，相对小红书目录；不写用内页纹理
              "badge": true,              # 可选，左下角头像角标，默认 true（头像文件不存在则自动不显示）
              "page": "2/9",              # 可选，右下角页码
              "html": "<div class=...>"}]} # 卡片内容，用下面 CSS 里的类

字由浏览器排，不交给生图模型，所以不会错字。图片路径写相对小红书目录的路径。
"""
import json
import os
import shutil
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
_MAC_CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
# 可用环境变量 CHROME 指定浏览器；默认 macOS Chrome，其次 PATH 里的 chrome/chromium
CHROME = os.environ.get("CHROME") or (_MAC_CHROME if Path(_MAC_CHROME).exists() else
    next((shutil.which(n) for n in ("google-chrome", "chromium", "chromium-browser") if shutil.which(n)), _MAC_CHROME))
W, H = 1242, 1660
AVATAR = ROOT / "素材/IP/头像.jpg"   # 你自己的头像/IP；没有这个文件就不显示角标
NAME = os.environ.get("XHS_NAME", "你的名字")                       # 角标旁边的署名

CSS = """
:root{--paper:#F6F1E7;--ink:#1B1A18;--red:#C62A1F;--grey:#6B655C;--line:#D9D0C0}
*{margin:0;padding:0;box-sizing:border-box}
html,body{width:%dpx;height:%dpx;overflow:hidden}
body{background:var(--paper) center/cover no-repeat;color:var(--ink);
  font-family:"PingFang SC","Hiragino Sans GB","STHeiti",sans-serif;position:relative}
.wrap{position:absolute;inset:110px 96px 190px}
.kicker{display:inline-block;font-size:34px;font-weight:600;color:#fff;background:var(--red);
  padding:8px 22px;letter-spacing:2px;margin-bottom:34px}
h1{font-size:150px;line-height:1.08;font-weight:900;letter-spacing:-2px}
h2{font-size:78px;line-height:1.2;font-weight:800;margin-bottom:44px}
h1 em,h2 em,b em,.big em{font-style:normal;color:var(--red)}
.sub{font-size:48px;font-weight:600;color:var(--ink);margin-top:36px;line-height:1.4}
.brush{height:22px;width:62%%;background:var(--red);margin:30px 0 0;border-radius:2px 14px 4px 10px;
  transform:rotate(-1.2deg);opacity:.92}
p{font-size:42px;line-height:1.62;margin-bottom:28px}
.note{font-size:32px;color:var(--grey);line-height:1.5}
ol.items{list-style:none;counter-reset:n}
ol.items li{counter-increment:n;font-size:48px;line-height:1.45;padding:26px 0 26px 92px;position:relative;
  border-bottom:2px solid var(--line)}
ol.items li:before{content:counter(n);position:absolute;left:0;top:26px;width:62px;height:62px;border-radius:50%%;
  background:var(--ink);color:#fff;font-size:36px;font-weight:700;text-align:center;line-height:62px}
ol.items li small{display:block;font-size:32px;color:var(--grey);margin-top:6px}
table{width:100%%;border-collapse:collapse;font-size:40px}
td,th{padding:18px 10px;border-bottom:2px solid var(--line);text-align:left;vertical-align:top}
th{font-size:32px;color:var(--grey);font-weight:500}
td.num{color:var(--red);font-weight:800;font-size:52px;white-space:nowrap}
tr.low td{color:var(--grey)}tr.low td.num{color:var(--grey);font-size:44px}
.stats{display:flex;align-items:center;gap:30px;margin:10px 0 50px}
.stat{flex:1;background:#fff;border:3px solid var(--ink);padding:36px 30px;box-shadow:12px 12px 0 var(--ink)}
.stat .big{font-size:120px;font-weight:900;line-height:1}
.stat .lab{font-size:34px;color:var(--grey);margin-top:14px}
.arrow{font-size:80px;color:var(--red);font-weight:900}
.shot{display:block;width:100%%;border:3px solid var(--ink);box-shadow:14px 14px 0 rgba(27,26,24,.9);
  background:#fff;object-fit:cover;object-position:top}
.card{background:#fff;border-left:12px solid var(--red);padding:30px 36px;font-size:44px;line-height:1.5;
  font-weight:700;margin:36px 0}
.tag{display:inline-block;border:3px solid var(--ink);font-size:36px;font-weight:700;padding:10px 24px;margin-top:40px;
  background:#fff}
.badge{position:absolute;left:96px;bottom:70px;display:flex;align-items:center;gap:20px}
.badge img{width:96px;height:96px;border-radius:50%%;border:4px solid var(--ink);object-fit:cover}
.badge span{font-size:32px;font-weight:700;letter-spacing:1px}
.page{position:absolute;right:96px;bottom:96px;font-size:32px;color:var(--grey);font-weight:600;letter-spacing:2px}
""" % (W, H)


def render(card, base, tex, out):
    bg = card.get("bg") or tex
    bg_url = (base / bg).resolve().as_uri() if bg else ""
    html = re.sub(r"""src=(["'])""", lambda m: "src=%s%s/" % (m.group(1), base.resolve().as_uri()), card["html"])
    badge = card.get("badge", True) and AVATAR.exists()
    page = card.get("page", "")
    doc = f"""<!doctype html><html><head><meta charset="utf-8"><style>{CSS}</style></head>
<body style="background-image:url('{bg_url}')">
{html}
{f'<div class="badge"><img src="{AVATAR.as_uri()}"><span>{NAME}</span></div>' if badge else ''}
{f'<div class="page">{page}</div>' if page else ''}
</body></html>"""
    with tempfile.NamedTemporaryFile("w", suffix=".html", delete=False, encoding="utf-8") as f:
        f.write(doc)
        tmp = f.name
    subprocess.run([CHROME, "--headless=new", "--no-sandbox", "--disable-gpu", "--hide-scrollbars",
                    "--force-device-scale-factor=1", "--allow-file-access-from-files",
                    f"--window-size={W},{H}", "--virtual-time-budget=3000",
                    f"--screenshot={out}", Path(tmp).as_uri()],
                   check=True, capture_output=True)
    Path(tmp).unlink()


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    base = Path(sys.argv[1])
    spec = json.loads((base / "分镜.json").read_text(encoding="utf-8"))
    tex = spec.get("texture", "底图/内页纹理.png")
    if not (base / tex).exists():
        tex = ""
    only = set(sys.argv[2:])
    (base / "卡片").mkdir(exist_ok=True)
    for card in spec["cards"]:
        if only and card["name"] not in only:
            continue
        out = base / "卡片" / f"{card['name']}.png"
        render(card, base, tex, out)
        print(out)


if __name__ == "__main__":
    main()

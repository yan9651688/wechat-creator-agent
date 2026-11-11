"""直接调 OpenAI 兼容的图片接口出一张图。

用法：
  python3 -I 工具/生图api.py <输出.png> "<提示词>" [--size 1024x1024] [--model 名字] [--ref 图1,图2]
  提示词以 @ 开头表示从文件读。
  --ref 图1,图2  带参考图（走 /images/edits），比如 IP 封面带身份参考图；不带走 /images/generations。
  一般不用直接调它：工具/生图.sh 配了 IMAGE_API_KEY 时会自动转到这里，并带上 素材/IP/ 的参考图。
  遇到限流（「当前请求较多」、429、5xx）自动等 20 秒重试，最多 8 次。

密钥只从环境变量（或仓库根目录 .env）读：IMAGE_API_KEY、IMAGE_API_BASE、IMAGE_MODEL。
日志不记密钥。每次生成在本篇目录的 提示词/api生图记录.txt 追加一条提示词、模型、耗时。
"""
import base64
import json
import os
import sys
import time
import urllib.request
from pathlib import Path


def main():
    args = sys.argv[1:]
    root = Path(__file__).resolve().parent.parent
    env = root / ".env"
    if env.exists():
        for line in env.read_text(encoding="utf-8").splitlines():
            k, sep, v = line.partition("=")
            if sep and not line.lstrip().startswith("#") and v.strip():
                os.environ.setdefault(k.strip(), v.strip())
    size = os.environ.get("IMAGE_SIZE", "1024x1024")
    model = os.environ.get("IMAGE_MODEL", "gpt-image-1")
    if "--size" in args:
        i = args.index("--size"); size = args[i + 1]; del args[i:i + 2]
    if "--model" in args:
        i = args.index("--model"); model = args[i + 1]; del args[i:i + 2]
    refs = []
    if "--ref" in args:
        i = args.index("--ref"); refs = args[i + 1].split(","); del args[i:i + 2]
    if len(args) < 2:
        sys.exit(__doc__)
    out, prompt = Path(args[0]), args[1]
    if prompt.startswith("@"):
        prompt = Path(prompt[1:]).read_text(encoding="utf-8")
    key = os.environ.get("IMAGE_API_KEY")
    base = os.environ.get("IMAGE_API_BASE", "https://api.openai.com/v1").rstrip("/")
    if not key:
        sys.exit("缺 IMAGE_API_KEY（写在 .env 或 export）")

    import subprocess
    t0 = time.time()
    data, last = None, ""
    for attempt in range(8):
        if refs:
            cmd = ["curl", "-sS", "-m", "600", base + "/images/edits", "-H", "Authorization: Bearer " + key,
                   "-F", "model=" + model, "-F", "size=" + size, "-F", "prompt=" + prompt]
            for r in refs:
                cmd += ["-F", "image[]=@" + r]
            raw = subprocess.run(cmd, capture_output=True, text=True).stdout
        else:
            body = json.dumps({"model": model, "prompt": prompt, "size": size, "n": 1}).encode()
            req = urllib.request.Request(base + "/images/generations", data=body, headers={
                "Authorization": "Bearer " + key, "Content-Type": "application/json"})
            try:
                with urllib.request.urlopen(req, timeout=600) as r:
                    raw = r.read().decode()
            except urllib.error.HTTPError as e:
                raw = e.read().decode(errors="replace")
            except Exception as e:
                raw = str(e)
        try:
            d = json.loads(raw)
        except Exception:
            d = {}
        if d.get("data"):
            data = d
            break
        last = raw[:300]
        if attempt < 7:
            print(f"接口没返回图片，20 秒后重试（{attempt + 1}/8）：{last[:80]}", file=sys.stderr)
            time.sleep(float(os.environ.get("IMAGE_RETRY_SECONDS", "20")))
    if not data:
        sys.exit(f"{out} 失败：{last}")
    secs = time.time() - t0
    item = data["data"][0]
    if item.get("b64_json"):
        img = base64.b64decode(item["b64_json"])
    elif item.get("url"):
        with urllib.request.urlopen(item["url"], timeout=300) as r:
            img = r.read()
    else:
        sys.exit("返回里没有图片：" + json.dumps(data)[:500])
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(img)

    log_dir = out.parent
    if log_dir.name in ("配图", "底图") or log_dir.parent.name == "配图":
        log_dir = log_dir.parent if log_dir.name in ("配图", "底图") else log_dir.parent.parent
    log_dir = log_dir / "提示词"
    log_dir.mkdir(exist_ok=True)
    with open(log_dir / "api生图记录.txt", "a", encoding="utf-8") as f:
        f.write(f"时间：{time.strftime('%Y-%m-%d %H:%M:%S')}\n输出：{out}\n模型：{model}  尺寸：{size}  耗时：{secs:.0f} 秒\n"
                f"接口：{base}  参考图：{refs}\n提示词：\n{prompt}\n\n")
    print(f"{out}  {secs:.0f} 秒")


if __name__ == "__main__":
    main()

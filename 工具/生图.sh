#!/usr/bin/env bash
# 生图：配了 IMAGE_API_KEY 走 OpenAI 兼容接口，否则用 Codex CLI 自带的 image_gen。
# 用法：工具/生图.sh <输出.png> "<画面描述>"
#       工具/生图.sh <输出.png> @提示词文件.txt
#       NO_IP=1 工具/生图.sh ……   不带参考图和角色要求，出纯底图（小红书封面、纹理）
# 素材/IP/ 里有身份参考、风格参考图就一起传给 codex exec；没有就纯文字出图。
# 生成后把图片拷到输出路径，并在输出目录的 提示词/ 下记录提示词和原始文件位置。
set -euo pipefail

if [ $# -lt 2 ]; then
  echo "用法：$0 <输出.png> \"<画面描述>\" 或 @提示词文件.txt" >&2
  exit 1
fi

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUT="$1"
PROMPT="$2"
if [ "${PROMPT:0:1}" = "@" ]; then
  PROMPT="$(cat "${PROMPT:1}")"
fi


# ---- 模式一：OpenAI 兼容图片接口（设置了 IMAGE_API_KEY 时启用）----
# 环境变量（可写在仓库根目录 .env）：IMAGE_API_KEY、IMAGE_API_BASE、IMAGE_MODEL、IMAGE_SIZE
[ -f "$ROOT/.env" ] && { set -a; . "$ROOT/.env"; set +a; }
if [ -n "${IMAGE_API_KEY:-}" ]; then
  BASE="${IMAGE_API_BASE:-https://api.openai.com/v1}"
  MODEL="${IMAGE_MODEL:-gpt-image-1}"
  SIZE="${IMAGE_SIZE:-1024x1024}"
  STYLE_NOTE="$(cat "$ROOT/素材/IP/角色与画风说明.txt" 2>/dev/null || true)"
  API_REFS=""
  if [ "${NO_IP:-}" != "1" ]; then
    for f in "$ROOT"/素材/IP/身份参考.* "$ROOT"/素材/IP/风格参考.*; do
      [ -f "$f" ] && API_REFS="${API_REFS:+$API_REFS,}$f"
    done
  else
    STYLE_NOTE=""
  fi
  P="${STYLE_NOTE:+$STYLE_NOTE
}$PROMPT
不要水印、不要随机 logo。"
  # 有参考图走 /images/edits，没有走 /images/generations；接口忙会自动重试
  exec python3 -I "$ROOT/工具/生图api.py" "$OUT" "$P" --size "$SIZE" --model "$MODEL" ${API_REFS:+--ref "$API_REFS"}
fi
# ---- 模式二：没配 API 时，用 Codex CLI 的 image_gen ----

# 可选：你自己的形象/风格参考图（IP 角色、画风样图）。没放就按纯文字描述出图。
#   素材/IP/身份参考.*    角色长相以它为准
#   素材/IP/风格参考.*    只参考画法和笔触
REFS=()
for f in "$ROOT"/素材/IP/身份参考.* "$ROOT"/素材/IP/风格参考.*; do
  [ -f "$f" ] && REFS+=("$f")
done
GEN_DIR="$HOME/.codex/generated_images"

STYLE_NOTE="$(cat "$ROOT/素材/IP/角色与画风说明.txt" 2>/dev/null || true)"

FULL_PROMPT="请调用 image_gen 生成一张图片，只生成这一张，不要写代码，不要改任何文件。
${STYLE_NOTE:+
角色与画风要求（来自素材/IP/角色与画风说明.txt）：
$STYLE_NOTE
}
本次画面：
$PROMPT

不要水印、不要随机 logo。生成完成后，只回复生成图片在本机的完整路径。"

# NO_IP=1：忽略参考图和角色说明，只按本次描述出图
if [ "${NO_IP:-}" = "1" ]; then
  REFS=()
  FULL_PROMPT="请调用 image_gen 生成一张图片，只生成这一张，不要写代码，不要改任何文件。
不要水印和随机 logo。

本次画面：
$PROMPT

生成完成后，只回复生成图片在本机的完整路径。"
fi

mkdir -p "$(dirname "$OUT")"
MARK="$(mktemp)"
LAST="$(mktemp)"
trap 'rm -f "$MARK" "$LAST"' EXIT

echo "调用 codex exec 生图中……" >&2
# 提示词走标准输入：--image 会把后面的位置参数都当成图片文件
if [ ${#REFS[@]} -gt 0 ]; then
  printf '%s' "$FULL_PROMPT" | codex exec --skip-git-repo-check -s read-only \
    -o "$LAST" --image "${REFS[@]}" >&2
else
  printf '%s' "$FULL_PROMPT" | codex exec --skip-git-repo-check -s read-only -o "$LAST" >&2
fi

# 优先用 codex 回复里的路径，找不到就取本次运行之后新生成的图片
SRC="$(grep -oE '/[^[:space:]`"]+\.(png|jpg|jpeg|webp)' "$LAST" | head -1 || true)"
if [ -z "$SRC" ] || [ ! -f "$SRC" ]; then
  SRC="$(find "$GEN_DIR" -type f \( -name '*.png' -o -name '*.jpg' -o -name '*.webp' \) -newer "$MARK" -print0 2>/dev/null \
    | xargs -0 ls -t 2>/dev/null | head -1 || true)"
fi
if [ -z "$SRC" ] || [ ! -f "$SRC" ]; then
  echo "没找到生成的图片。codex 的回复：" >&2
  cat "$LAST" >&2
  exit 2
fi

cp "$SRC" "$OUT"

# 日志放在本篇目录的 提示词/ 下；输出在 配图/ 里时往上一级
LOG_DIR="$(dirname "$OUT")"
case "$(basename "$LOG_DIR")" in 配图|底图) LOG_DIR="$(dirname "$LOG_DIR")" ;; esac
LOG_DIR="$LOG_DIR/提示词"
mkdir -p "$LOG_DIR"
{
  echo "时间：$(date '+%Y-%m-%d %H:%M:%S')"
  echo "输出：$OUT"
  echo "原始文件：$SRC"
  echo "参考图：${REFS[*]:-无}"
  echo
  echo "$PROMPT"
} > "$LOG_DIR/$(basename "${OUT%.*}").txt"

echo "$OUT"

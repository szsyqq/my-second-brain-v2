#!/usr/bin/env bash
# v2 一键部署脚本：本地 vault → convert.py → 推 GitHub Pages (gh-pages)
# 前置：vault 已 git commit（历史版本跟踪依赖 vault 的 git 历史）
# 用法：./deploy.sh "部署说明"   （说明省略则用时间戳）
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OUTPUT="$ROOT/output"
TMP="$(mktemp -d /tmp/v2site.XXXXXX)"
MSG="${1:-deploy: $(date +%Y%m%dT%H%M%S)}"
REMOTE="https://github.com/szsyqq/my-second-brain-v2.git"

# 1) 定位 python3（managed 3.13 优先，回退系统 python3）
PY="$(command -v python3 || true)"
if [ -z "$PY" ] || [ ! -x "$PY" ]; then
  PY="/Users/panyp/.workbuddy/binaries/python/versions/3.13.12/bin/python3"
fi
if [ ! -x "$PY" ]; then
  echo "❌ 找不到 python3，请先安装 Python 3.12+"
  exit 1
fi

# 2) 构建
echo "▶ 运行 convert.py ..."
cd "$ROOT"
"$PY" scripts/convert.py

# 3) 准备静态产物
echo "▶ 复制 output/ 到临时仓库 ..."
cp -R "$OUTPUT/." "$TMP/"
touch "$TMP/.nojekyll"

# 4) 推 gh-pages（GIT_HTTP_VERSION=1 规避 HTTP/2 偶发失败）
echo "▶ 推送到 gh-pages ..."
cd "$TMP"
git init -q
git config user.email "vault@local"
git config user.name "local-vault"
export GIT_HTTP_VERSION=1
git add -A
git commit -q -m "$MSG"
git push -f "$REMOTE" HEAD:gh-pages

echo "✅ 部署完成：$MSG"
echo "🌐 https://szsyqq.github.io/my-second-brain-v2/"
echo "   若页面未立即更新，等约 1-2 分钟 Pages 构建，或硬刷新 (Cmd+Shift+R)"

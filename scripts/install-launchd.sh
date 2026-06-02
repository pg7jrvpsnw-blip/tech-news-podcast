#!/bin/zsh
# 一键安装/重装 launchd job
# 用法: bash scripts/install-launchd.sh

set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${0}")/.." && pwd)"
LABEL="com.guoxu.tech-news-podcast"
PLIST_SRC="${PROJECT_DIR}/scripts/${LABEL}.plist"
PLIST_DST="${HOME}/Library/LaunchAgents/${LABEL}.plist"

mkdir -p "${HOME}/Library/LaunchAgents"
mkdir -p "${PROJECT_DIR}/logs"
chmod +x "${PROJECT_DIR}/scripts/daily.sh"

# 替换占位 → 实际路径
sed "s|REPLACE_PROJECT_DIR|${PROJECT_DIR}|g" "${PLIST_SRC}" > "${PLIST_DST}"
echo "installed: ${PLIST_DST}"

# 如果已 load 过先 unload
launchctl bootout "gui/$(id -u)" "${PLIST_DST}" 2>/dev/null || true

# 加载新版本
launchctl bootstrap "gui/$(id -u)" "${PLIST_DST}"
launchctl enable "gui/$(id -u)/${LABEL}"

echo "✓ launchd job 已加载,每天上午 10:03 自动跑"
echo ""
echo "常用命令:"
echo "  立即跑一次:  launchctl kickstart -k gui/\$(id -u)/${LABEL}"
echo "  停止:        launchctl bootout gui/\$(id -u) ${PLIST_DST}"
echo "  看日志:      tail -f ${PROJECT_DIR}/logs/\$(date +%Y-%m-%d).log"

#!/bin/zsh
# 安装/更新 crontab 任务: 每天上午 10:03 跑 daily.sh
# 用法: bash scripts/install-cron.sh

set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${0}")/.." && pwd)"
DAILY_SH="${PROJECT_DIR}/scripts/daily.sh"
MARKER="# tech-news-podcast"

chmod +x "${DAILY_SH}"

# 取出现有 crontab(没有就空),过滤掉旧版本同名 job,追加新行
NEW_LINE="3 10 * * * ${DAILY_SH} ${MARKER}"

(crontab -l 2>/dev/null | grep -v "${MARKER}" || true; echo "${NEW_LINE}") | crontab -

echo "✓ crontab 已更新:"
crontab -l | grep "${MARKER}"
echo ""
echo "常用命令:"
echo "  立即手动跑:  bash ${DAILY_SH}"
echo "  看 crontab:  crontab -l"
echo "  删除任务:    crontab -l | grep -v '${MARKER}' | crontab -"
echo "  看今日日志:  tail -f ${PROJECT_DIR}/logs/\$(date +%Y-%m-%d).log"
echo ""
echo "注意:"
echo "  - macOS cron 在系统睡眠时不跑(合盖+插电也不会唤醒)"
echo "  - 错过没有补跑机制(launchd 才有);忘记跑就 \`bash daily.sh\` 手动补"
echo "  - 首次启用可能要给 cron 完全磁盘访问权限:"
echo "    系统设置 → 隐私与安全 → 完全磁盘访问 → +/usr/sbin/cron"

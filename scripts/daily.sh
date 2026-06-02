#!/bin/zsh
# 每日跑一次:抓新闻 → 摘要 → TTS → 渲染 → push GitHub
# 由 launchd 调用(详见 com.guoxu.tech-news-podcast.plist)
# 单独跑也行: bash scripts/daily.sh

set -euo pipefail

PROJECT_DIR="${HOME}/Workspace/workspace_claudecode/projects/tech-news-podcast"
LOG_DIR="${PROJECT_DIR}/logs"
mkdir -p "${LOG_DIR}"
LOG_FILE="${LOG_DIR}/$(date +%Y-%m-%d).log"

# launchd 启动时 PATH 极简,需要补上 brew / uv / git 路径
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:${PATH}"

cd "${PROJECT_DIR}"

{
  echo "===== $(date '+%Y-%m-%d %H:%M:%S') daily.sh start ====="

  # 1. 抓 + 摘要 + TTS + 渲染
  uv run python -m src.main

  # 2. 把今天的产物 commit + push
  git add data/ site/
  if git diff --staged --quiet; then
    echo "no changes — nothing to commit"
  else
    git commit -m "daily: $(date '+%Y-%m-%d') 自动生成"
    git push
    echo "pushed to origin/main"
  fi

  echo "===== $(date '+%Y-%m-%d %H:%M:%S') daily.sh done ====="
} >> "${LOG_FILE}" 2>&1

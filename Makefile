.PHONY: help install check check-full dev stop rebuild run run-skip-tts fetch clean

help: ## 显示这个帮助信息
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-18s\033[0m %s\n", $$1, $$2}'

install: ## 安装依赖(uv sync + ffmpeg + 创建 .env)
	@command -v ffmpeg >/dev/null 2>&1 || (echo "Installing ffmpeg…" && brew install ffmpeg)
	uv sync
	@test -f .env || (cp .env.example .env && echo "已创建 .env,请编辑填入 API key")

check: ## 配置体检(.env / ffmpeg / Claude / OpenAI / R2)
	uv run python -m src.check

check-full: ## 完整体检(含真跑一次 RSS 抓取,慢一些)
	uv run python -m src.check --rss

dev: ## 起本地 HTTP server (8765 端口)
	@echo "→ http://localhost:8765"
	@cd site && python3 -m http.server 8765

stop: ## 停掉占用 8765 的 server
	@lsof -ti:8765 | xargs kill 2>/dev/null && echo "stopped" || echo "no server running"

rebuild: ## 只重渲染网站,不重新抓/总结/合成 (用于改 CSS/模板后预览)
	uv run python -m src.main --rebuild

run: ## 跑全流程:抓 → Claude 摘要 → TTS → 渲染
	uv run python -m src.main

run-skip-tts: ## 跑全流程但跳过 TTS (省 OpenAI 钱,只验证 Claude 部分)
	uv run python -m src.main --skip-tts

fetch: ## 只跑 fetch 看看每个源拉到多少
	uv run python -m src.fetch

clean: ## 清掉本地音频和构建产物
	rm -rf site/audio/*.mp3 site/index.html site/feed.xml site/episodes site/archive.html site/static

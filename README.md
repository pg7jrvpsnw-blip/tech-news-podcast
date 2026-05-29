# 每日科技速读

每天自动抓取昨日中英文科技新闻 → AI 总结要点 → 合成中文播客 → 输出网站 + 标准 RSS Podcast Feed。

可以在 Apple Podcasts / 小宇宙 / Pocket Casts 等播客 App 直接订阅,通勤路上听。

## 一图看懂

```
[每日 07:23 北京时间 GitHub Actions cron]
    ↓
fetch  抓 20 个中英文 RSS 源 → 按"昨天"过滤 → 单源限流 → 截断 50 条
    ↓
summarize  Claude (mify/PPIO) 逐条摘要 + 主题分类 + 整体播音稿
    ↓
tts  OpenAI gpt-4o-mini-tts 中文女声(shimmer),分段合成拼接 mp3
    ↓
upload  mp3 推到 Cloudflare R2(出站免费,关键)
    ↓
build  Jinja2 渲染 HTML + feedgen 生成 iTunes 兼容 RSS
    ↓
git push  CF Pages 自动部署
    ↓
[网站浏览 / 播客 App 订阅 RSS]
```

## 一键开始(本地)

```bash
make install      # uv sync + brew install ffmpeg + 创建 .env
# 编辑 .env 填入 ANTHROPIC_API_KEY / OPENAI_API_KEY
make run          # 全流程跑一次(花约 ¥0.5)
make dev          # 起本地 server -> http://localhost:8765
```

`make help` 看所有命令。

## 主要 Make 命令

| 命令              | 作用                                             |
| ----------------- | ------------------------------------------------ |
| `make install`    | 一次性配置:uv sync + ffmpeg + 创建 .env          |
| `make run`        | 全流程:抓 + Claude 摘要 + TTS + 渲染 + 上传      |
| `make run-skip-tts` | 跑流程但跳过 TTS(省 OpenAI 钱,只看摘要效果)  |
| `make rebuild`    | 只重渲染网站(改 CSS/模板后用,不烧 API 钱)      |
| `make fetch`      | 只跑 fetch 看每个源拉到多少                      |
| `make dev`        | 启本地 HTTP server(8765)                       |
| `make stop`       | 停掉 server                                      |
| `make clean`      | 清掉构建产物                                     |

## 输出文件

- `site/index.html` — 最新一期(部署后变成首页)
- `site/episodes/<date>.html` — 每期归档
- `site/feed.xml` — 播客 RSS feed(订阅这个)
- `site/audio/<date>.mp3` — mp3 音频(本地;部署后传 R2,不进 Git)
- `data/episodes/<date>.json` — 每期中间数据(进 Git)

## 上云部署(阶段 2)

详细 plan:`~/.claude/plans/gentle-fluttering-emerson.md`

### 一、Cloudflare R2(存音频)

1. 注册 [Cloudflare](https://www.cloudflare.com/) 账号
2. 进 **R2** 面板 → 创建 bucket(例:`tech-news-podcast`)
3. **Settings → Public Access** 启用公开访问,记下公开域名(例 `https://pub-xxx.r2.dev` 或自定义 `audio.your-domain.com`)
4. **R2 → Manage API Tokens** 创建 token,记下 `Account ID` / `Access Key` / `Secret Key`

### 二、GitHub 仓库

1. 把项目推到 GitHub(公开仓 Actions 无限免费;私有仓 2000 分钟/月)
2. 仓库 **Settings → Secrets and variables → Actions** 添加:
   - `ANTHROPIC_API_KEY` `ANTHROPIC_BASE_URL` `ANTHROPIC_MODEL`
   - `OPENAI_API_KEY` `OPENAI_TTS_MODEL` `OPENAI_TTS_VOICE`
   - `R2_ACCOUNT_ID` `R2_ACCESS_KEY` `R2_SECRET_KEY` `R2_BUCKET` `R2_PUBLIC_BASE`
   - `PODCAST_TITLE` `PODCAST_AUTHOR` `PODCAST_EMAIL` `PODCAST_DESCRIPTION` `PODCAST_SITE_URL`
3. 仓库 **Actions** 标签页可手动触发 `Daily Podcast Build` 测试一次

### 三、Cloudflare Pages(托管网站)

1. **CF dashboard → Workers & Pages → Create → Connect Git**
2. 选你的仓库,**Build settings**:
   - Build command:留空(已是静态产物)
   - Build output directory:`site`
3. 点 **Save and Deploy**
4. 拿到 `https://xxx.pages.dev` 域名,回头填回 `PODCAST_SITE_URL` secret

### 四、提交到播客平台

把 `https://<your>.pages.dev/feed.xml` 这个 URL:

- **小宇宙**:[创作中心](https://creator.xiaoyuzhoufm.com/) → 添加节目 → 粘 RSS
- **Apple Podcasts**:[Podcasts Connect](https://podcastsconnect.apple.com/) → 提交,审核 1-3 天
- **Pocket Casts / Overcast / Spotify**:支持 RSS 直接订阅

提交前先用 [castfeedvalidator.com](https://castfeedvalidator.com) 校验。

## 排错

- **fetch 拿不到东西**:确认时区,默认是"北京时间昨天 0~24 点"。指定 `--date YYYY-MM-DD` 试试。
- **36Kr/虎嗅/机器之心 失效**:RSSHub 限流。后续可自建 RSSHub 替换,或换用国内同类源,见 `src/config.py`。
- **TTS 报 4096 字符上限**:`config.py` 里 `TTS_CHUNK_LIMIT` 已设为 3500,长稿自动拼接。
- **pydub 报 ffmpeg 找不到**:`brew install ffmpeg` 或在 Linux 用 `apt install ffmpeg`。
- **GitHub Actions 跑挂**:大概率是 secret 没填齐 / mify 端点跨墙不通。考虑换 Anthropic 官方 key,或自建 GH Actions runner。

## 成本

按每天 50 条新闻 / 8 分钟播客算:

| 项                                  | 单价              | 日均  |
| ----------------------------------- | ----------------- | ----- |
| Claude (mify/PPIO 0.22x + caching)  | ¥5/M 综合         | ~¥0.3 |
| OpenAI TTS gpt-4o-mini-tts          | $0.015/1k chars   | ~¥0.2 |
| Cloudflare R2 (出站免费!)           | 10GB 免费         | ¥0    |
| GitHub Actions (公开仓无限)         | -                 | ¥0    |
| Cloudflare Pages                    | 500 次构建/月     | ¥0    |
| **合计**                            |                   | **~¥0.5/天 = ¥15/月** |

## 项目结构

```
src/
  config.py       — 新闻源 + API 配置
  fetch.py        — RSS 抓取 + 去重 + 单源限流
  summarize.py    — Claude 逐条摘要 + 整体播音稿(prompt caching)
  tts.py          — OpenAI TTS 分段拼接
  upload.py       — R2 上传(未配则本地)
  build_site.py   — Jinja2 渲染 HTML
  build_feed.py   — feedgen 生成 iTunes 兼容 RSS
  main.py         — 编排入口
templates/        — HTML 模板(base/episode/archive)
static/           — CSS / SVG 封面 / 自定义播放器 JS
data/episodes/    — 每期 JSON(进 Git)
site/             — 构建产物(audio/ 不进 Git,推 R2)
.github/workflows/daily.yml — 定时任务
```

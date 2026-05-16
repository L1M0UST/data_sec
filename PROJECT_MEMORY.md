# 项目记忆（data_sec）

## 目标
抓取多个安全资讯站点的数据泄露/数据泄漏相关内容，按天落盘到本地，便于后续分析与归档。

核心约束与策略：
- 默认走本地代理（解决 403/地区/WAF 等问题）
- 每天可重复运行，依靠 SQLite 去重
- 以“先跑通并稳定落盘”为优先；对被强拦截站点采取 RSS 摘要降级策略

## 当前站点覆盖（sites.yaml）
- The Hacker News（data breach 标签列表页）
- SecurityWeek（全站 RSS feed，关键词过滤后以 RSS 摘要落盘）
- DataBreachToday（news 列表页）
- IT Security News（全站 RSS feed，关键词过滤后以 RSS 摘要落盘）
- BleepingComputer（tag 列表页；曾遇到 feed 404/403，改用 HTML 列表页）

## 入口与反爬处理经验
- SecurityWeek：
  - `topics/data-leak/feed/` 会 403
  - `https://www.securityweek.com/feed/` 通过代理可 200，但文章正文页仍 403
  - 当前采取降级：`rss_use_summary: true`，直接落盘 RSS 的 title/pubDate/description，不抓正文页
- IT Security News：
  - `https://www.itsecuritynews.info/feed/` 可访问
  - 该站为聚合站点，正文常指向外部来源；当前采取降级：`rss_use_summary: true`（落盘 RSS 摘要，不抓外站正文）
- BleepingComputer：
  - `/tag/data-breach/feed/` 在代理环境下可能 404/403
  - 改为抓取 `https://www.bleepingcomputer.com/tag/data-breach/`（HTML 列表页）

## 运行方式
Python 版本：
- 需要 **Python >= 3.10**（代码中使用了 `str | None` 这类类型标注语法）

安装依赖：
- `python -m pip install -r requirements.txt`

运行：
- `python main.py --max-per-site 50`

可选：
- `--date YYYY-MM-DD`
- `--proxy http://127.0.0.1:7890`（覆盖所有站点代理）

默认代理：
- `sites.yaml` 顶层 `default_proxy: http://127.0.0.1:7890`（所有站点默认走代理；若站点 `fetch.proxy` 或 CLI `--proxy` 提供则覆盖）

## 抓取“日期限制”现状
- 当前实现 **没有严格的“只抓当天”限制**：
  - 对 HTML 抓取站点：正文抽取目前不解析 `published_at`（`extract.py` 返回 `published_at=None`），因此无法按日期过滤
  - 对 RSS 摘要模式站点：会把 RSS 的 `pubDate` 文本写入 `published_at`，但目前也未用于过滤
- CLI 有 `--today-only`，但在 `published_at` 普遍不可用的情况下 **实际效果有限**（更多依赖去重/站点入口返回的“最新列表”）

## 抓取频率建议（每天一次 vs 两次）
- 建议默认 **每天 1 次**（例如早上），稳定、资源占用低，靠站点“最新列表/RSS”覆盖大多数新增内容。
- 如果你更在意“更快发现新增”，可以 **每天 2 次**（例如早上 + 下午/晚上），配合去重（`state.db`）通常不会重复落盘太多。
- 规模变大后的控制手段：
  - 通过 `--max-per-site` 限制单站每次处理数量
  - 通过 `fetch.rate_limit_per_sec` 控制频率，减少被封风险
  - 依靠 `state.db` 去重，避免二次抓取同 URL

## 输出结构（data/）
- `data/articles/YYYY-MM-DD/<site_id>/*.md`
  - markdown 带简单 frontmatter（title/url/source/site_id/published_at/crawled_at）
- `data/index/YYYY-MM-DD.jsonl`
  - 每篇文章一行 JSON，包含内容文本与保存路径
- `data/state/state.db`
  - SQLite 状态库，用于 **去重 + 记录抓取结果**
  - 主要表：`seen(url_hash primary key, site_id, url, first_seen_at, last_status)`
    - `url_hash`：对 `site_id|url` 的稳定 hash，作为去重主键
    - `last_status`：最近一次抓取状态（success/failed）
  - 作用：同一 URL 之后重复运行不会再次下载/落盘（节省流量与时间）
- `data/logs/YYYY-MM-DD_summary.log`
- `data/logs/YYYY-MM-DD_summary.jsonl`
  - 每日总览与事件日志（entry_failed/article_failed/site_summary）

## 代码结构（crawler/）
- `main.py`
  - CLI：`--config --date --today-only --max-per-site --proxy`
- `crawler/config.py`
  - 读取 `sites.yaml`，生成 `AppConfig`（含 `default_proxy`）与 `SiteConfig`
- `crawler/fetcher.py`
  - `httpx` + 可选 `curl_cffi` 两种后端
  - 支持代理（httpx proxies / curl_cffi proxies）
  - `fetch_text`/`fetch_bytes` 带重试与限速
- `crawler/discover.py`
  - HTML 列表页：解析 `<a href>` + allow/deny regex
  - RSS：解析 item/entry link
  - `discover_links_from_rss_filtered` 支持 `item_text_allow_regex`（基于 title/category/description 过滤）
- `crawler/extract.py`
  - 使用 `trafilatura` 抽取正文文本（目前未专门抽标题/发布时间）
- `crawler/state.py`
  - SQLite 去重
- `crawler/writer.py`
  - `Article` 数据结构
  - 写 md + 写 index jsonl
- `crawler/runner.py`
  - 主流程：发现链接 -> 去重 -> 抓取/抽取 -> 落盘
  - 可观测性：
    - 控制台 + `data/logs/<day>_summary.*`
    - 站点统计（entry_ok/failed/discovered/skipped_seen/success/failed + reason 分布）
  - SecurityWeek 降级：当 `discover.rss_use_summary: true` 且 mode=rss 时，直接用 RSS description 写入 `Article.content_text`

## 配置关键字段（sites.yaml）
顶层：
- `output_dir`
- `state_db`
- `user_agent`
- `default_proxy`（全站默认代理，当前为 `http://127.0.0.1:7890`）

站点：
- `site_id/name/entry_urls/allowed_domains`
- `discover.*`
  - `mode: html|rss`
  - `link_allow_regex` / `link_deny_regex`
  - `item_text_allow_regex`（RSS 条目过滤）
  - `rss_use_summary: true|false`（RSS 摘要落盘，不抓正文页）
- `fetch.*`
  - `rate_limit_per_sec`
  - `headers`（可选）
  - `use_curl_cffi: true|false`（对强反爬站点更像浏览器）
  - `proxy`（可选，覆盖全局默认）

## 已完成的改动摘要
- 增加全局代理：`default_proxy` + CLI `--proxy` 覆盖
- 增加每日总览日志文件：`data/logs/YYYY-MM-DD_summary.log/jsonl`
- SecurityWeek：从 topic feed 切换到全站 feed + 关键词过滤；正文页 403 时降级为 RSS 摘要落盘
- IT Security News：新增站点，使用全站 feed + 关键词过滤 + RSS 摘要落盘
- BleepingComputer：从 RSS 入口切换到 tag HTML 列表页

## 待改进（下一步建议）
- 标题/发布时间抽取：
  - 从 HTML JSON-LD/meta 提取 `title/published_at`
  - RSS 模式可直接用 item 的 title/pubDate
- 文件命名：当 title 为 URL 时避免超长，可用 url_hash 作为文件名或更稳定 slug
- `--today-only` 真正生效：需要统一发布期解析（RSS pubDate/HTML datePublished）
- 失败重试与错误分类更细：例如区分解析失败/抽取过短/被重定向到验证码页

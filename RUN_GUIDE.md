# 运行指南

## 1. 外网侧（互联网机器）

### 1.1 安装依赖
```bash
pip install -r requirements.txt
```

### 1.2 爬取新闻
```bash
python main.py --max-per-site 30 --proxy http://127.0.0.1:7890
```
- 输出目录：`internet_side/crawler_output/articles/`
- 状态库：`internet_side/crawler_state/state.db`
- 日志：`internet_side/crawler_output/logs/`

### 1.3 SFTP 上传到服务器
```bash
python info_extract_main.py --action upload
```
- 读取 `pipeline.yaml` 的 `upload_remote` 配置
- 上传目录：`internet_side/crawler_output/articles/`
- 远端目标：`/data_sec/internet_side/upload_articles/`
- 上传成功后自动删除本地文件

### 1.4 外网侧完整流程（爬取+上传）
```bash
python info_extract_main.py --action all
```

---

## 2. 内网侧（内网机器）

### 2.1 安装依赖
```bash
pip install -r requirements.txt
```

### 2.2 FTP 拉取文件
```bash
python info_extract_main.py --action pull
```
- 读取 `pipeline.yaml` 的 `ftp_remote` 配置
- 拉取到：`intranet_side/ftp_stage/inbox/`
- 可选：`delete_remote_after_download: true` 可在拉取后删远端

### 2.3 LLM 清洗 + 入库
```bash
python info_extract_main.py --action extract
```
- 从 `intranet_side/ftp_stage/inbox/` 读取 `.md`
- 调用 Qwen HTTP 结构化抽取
- 写入 ClickHouse `data_breach_events_distributed`
- 成功移到：`intranet_side/llm_pipeline/processed/`
- 失败移到：`intranet_side/llm_pipeline/failed/`

### 2.4 内网侧完整流程（拉取+抽取）
```bash
python info_extract_main.py --action all
```

---

## 3. 配置文件说明

### 3.1 `sites.yaml`
- 外网爬虫站点和代理配置
- `output_dir: internet_side/crawler_output`
- `state_db: internet_side/crawler_state/state.db`

### 3.2 `pipeline.yaml`
```yaml
upload_remote:          # 外网 SFTP 上传
  host: 127.0.0.1
  port: 22
  username: your_user
  password: your_password
  private_key_path:
  remote_base_dir: /data_sec/internet_side/upload_articles

ftp_remote:            # 内网 FTP 拉取
  host: 127.0.0.1
  port: 21
  username: your_user
  password: your_password
  remote_base_dir: /data_sec/internet_side/upload_articles
  local_inbox_dir: intranet_side/ftp_stage/inbox
  local_archive_dir: intranet_side/ftp_stage/archive
  delete_remote_after_download: false

llm:                   # Qwen HTTP
  endpoint: http://127.0.0.1:8000/v1/chat/completions
  api_key:
  model: qwen-plus
  timeout_seconds: 120
  max_input_chars: 12000

clickhouse:             # ClickHouse 入库
  host: 127.0.0.1
  port: 8123
  username: default
  password: ""
  database: default
  table: data_breach_events_distributed
  secure: false
```

---

## 4. 常见命令组合

### 4.1 外网：每天 00:01 跑前一天新闻
```bash
python main.py --date $(date -d 'yesterday' +%Y-%m-%d) --max-per-site 30 --proxy http://127.0.0.1:7890
python info_extract_main.py --action upload
```

### 4.2 内网：每天 00:05 跑拉取+入库
```bash
python info_extract_main.py --action all
```

---

## 5. 目录结构

```
e:/code/py/data_sec/
├─ sites.yaml
├─ pipeline.yaml
├─ main.py                 # 外网爬虫入口
├─ info_extract_main.py     # 内网 pipeline 入口
├─ internet_side/
│  └─ crawler_output/
│     ├─ articles/          # 爬虫输出 .md
│     ├─ index/            # 每日索引
│     └─ logs/             # 爬取日志
└─ intranet_side/
   └─ ftp_stage/
      └─ inbox/             # FTP 拉取到本地
   └─ llm_pipeline/
      ├─ processed/         # 成功入库
      └─ failed/           # 抽取/入库失败
```

---

## 6. 注意事项
- 外网机器只需要配置 `upload_remote`，内网机器只需要配置 `ftp_remote`
- 如果 FTP 服务器不是标准实现，请告知服务器类型，可优化兼容性
- LLM 抽取前会自动清洗脏字符，防止宕机
- 所有路径、端口、模型参数都可在 `pipeline.yaml` 中修改

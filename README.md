# data_sec
这是一个面向数据泄露新闻的采集、传输与结构化处理项目，分为外网抓取侧和内网处理侧两部分。
## 功能概览
- 外网侧：按站点规则抓取安全新闻，保存为 Markdown 文件。
- 传输侧：通过 SFTP/FTP 在外网与内网之间传递文章文件。
- 内网侧：调用大模型抽取结构化字段，并写入 ClickHouse。
## 项目结构
- `internet_side/`：新闻抓取、清洗、上传逻辑。
- `intranet_side/`：文件拉取、抽取、入库逻辑。
- `main.py`：外网抓取入口。
- `info_extract_main.py`：上传、拉取、抽取流程入口。
- `sites.yaml`：站点抓取规则配置。
- `pipeline.example.yaml`：流水线配置示例。
## 快速开始
1. 安装依赖：
```bash
pip install -r requirements.txt
```
2. 复制配置文件：
```bash
cp pipeline.example.yaml pipeline.yaml
```
3. 按实际环境填写 `pipeline.yaml` 中的 SFTP、FTP、LLM 与 ClickHouse 配置。
4. 运行抓取：
```bash
python main.py --max-per-site 30
```
5. 运行上传、拉取或抽取：
```bash
python info_extract_main.py --action upload
python info_extract_main.py --action pull
python info_extract_main.py --action extract
```
## 配置说明
- `pipeline.yaml` 含有账号、密码、API Key 等敏感信息，已被忽略，不会上传到仓库。
- `pipeline.example.yaml` 仅保留示例值，便于部署时复制修改。
- `data/` 目录用于保存抓取结果、状态库与运行产物，默认不纳入版本控制。
## 适用场景
该项目适合需要将外网安全资讯采集后，再在隔离环境中完成结构化分析与入库的流程。


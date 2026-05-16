from __future__ import annotations

import json
import re
from typing import Any

import requests

from intranet_side.info_extract.config import LlmConfig


def build_prompt(cleaned_text: str) -> str:
    return (
        "你是一个网络安全新闻结构化抽取助手。"
        "请将当前文章视为一条独立事件记录，并仅输出一条 JSON 记录。"
        "请从文章中提取数据泄露事件字段，并将正文翻译整理为专业中文，仅输出 JSON。"
        "忽略乱码、块字符、装饰符号、广告、下载引导、页脚残留。"
        "如果字段无法确定，返回 null、空字符串或空数组，不要猜测。"
        "JSON 字段必须包含: title, company_name, country, region, industry_sector, records_count, data_types, attack_vector, cve_ids, severity, ransom_involved, tags, breach_date, attacker_name, attacker_type, attacker_aliases, attacker_country, attacker_region, attacker_ips, attacker_domains, attacker_urls, summary, raw_content_zh。"
        "其中 ransom_involved 返回 0 或 1；records_count 返回整数或 null；data_types/cve_ids/tags/attacker_aliases/attacker_ips/attacker_domains/attacker_urls 返回数组。"
        "对于能够翻译为中文且不影响专业性的字段，请输出专业中文，例如 title、country、region、industry_sector、attack_vector、severity、data_types、tags、summary。"
        "对于公司名、产品名、CVE 编号、专有名词，可保留原文。"
        "attacker_name 表示攻击组织名称；attacker_type 表示攻击者类型；attacker_aliases 表示攻击组织别名；attacker_country 和 attacker_region 表示攻击来源国家和地区；attacker_ips、attacker_domains、attacker_urls 表示文中明确提到的攻击基础设施。"
        "这些 attacker 相关字段有就填写，没有就返回空字符串或空数组。"
        "raw_content_zh 必须是对正文主要内容的中文整理翻译，要求语义完整、表达专业、适合直接存库；不要只返回摘要，也不要保留大段英文原文。"
        "输出内容必须尽量符合数据库字段类型：字符串字段输出字符串，数组字段输出字符串数组，日期字段输出 YYYY-MM-DD，时间字段不要输出到字段中。"
        "文章内容如下：\n\n"
        + cleaned_text
    )


def _extract_json_text(content: str) -> str:
    fenced = re.search(r"```json\s*(\{.*?\})\s*```", content, flags=re.S)
    if fenced:
        return fenced.group(1)
    match = re.search(r"(\{.*\})", content, flags=re.S)
    if match:
        return match.group(1)
    raise ValueError("LLM response does not contain JSON object")


def request_qwen_json(config: LlmConfig, cleaned_text: str) -> dict[str, Any]:
    headers = {"Content-Type": "application/json"}
    if config.api_key:
        headers["Authorization"] = f"Bearer {config.api_key}"
    payload = {
        "model": config.model,
        "messages": [
            {"role": "system", "content": "You extract structured cybersecurity breach event JSON only."},
            {"role": "user", "content": build_prompt(cleaned_text)},
        ],
        "temperature": 0.1,
    }
    response = requests.post(
        config.endpoint,
        headers=headers,
        json=payload,
        timeout=config.timeout_seconds,
    )
    response.raise_for_status()
    data = response.json()
    content = data["choices"][0]["message"]["content"]
    return json.loads(_extract_json_text(content))

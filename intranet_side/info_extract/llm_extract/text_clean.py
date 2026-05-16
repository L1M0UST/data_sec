from __future__ import annotations

import json
import re
import unicodedata


def clean_text_for_llm(text: str) -> str:
    if not text:
        return ""
    text = unicodedata.normalize("NFKC", text)
    text = re.sub(r"[\u200B-\u200D\uFEFF]", "", text)
    text = re.sub(r"[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]", "", text)
    text = re.sub(r"[\u2580-\u259F\u2500-\u257F\u25A0-\u25FF]+", " ", text)
    text = re.sub(r"[\uE000-\uF8FF]", "", text)
    text = re.sub(r"([^\w\s])\1{5,}", r"\1\1", text)
    text = re.sub(r"[ \t]{2,}", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _coerce_to_text(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, (int, float, bool)):
        return str(value)
    if isinstance(value, dict):
        try:
            return json.dumps(value, ensure_ascii=False)
        except Exception:
            return str(value)
    if isinstance(value, (list, tuple, set)):
        parts: list[str] = []
        for item in value:
            item_text = _coerce_to_text(item)
            if item_text:
                parts.append(item_text)
        return " | ".join(parts)
    return str(value)


def sanitize_text_value(value: object, max_len: int = 2000) -> str:
    text = clean_text_for_llm(_coerce_to_text(value))
    text = text.replace("\x00", "")
    return text[:max_len]


def sanitize_string_list(values: object, max_items: int = 50, item_max_len: int = 200) -> list[str]:
    if values is None:
        iterable: list[object] = []
    elif isinstance(values, (list, tuple, set)):
        iterable = list(values)
    else:
        iterable = [values]
    out: list[str] = []
    for value in iterable:
        cleaned = sanitize_text_value(value, max_len=item_max_len)
        if cleaned and cleaned not in out:
            out.append(cleaned)
        if len(out) >= max_items:
            break
    return out

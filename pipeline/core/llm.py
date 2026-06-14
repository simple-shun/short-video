"""OpenRouter 聊天补全客户端。"""
import json
import requests

from .. import config


def chat(messages, model=None, temperature=0.9, max_tokens=8000, timeout=180):
    """调一次 chat completion，返回文本内容。"""
    resp = requests.post(
        f"{config.OPENROUTER_BASE}/chat/completions",
        headers={
            "Authorization": f"Bearer {config.openrouter_key()}",
            "Content-Type": "application/json",
        },
        json={
            "model": model or config.DEFAULT_MODEL,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        },
        timeout=timeout,
    )
    resp.raise_for_status()
    data = resp.json()
    if "error" in data:
        raise RuntimeError(f"OpenRouter 错误: {data['error']}")
    choices = data.get("choices") or []
    if not choices:
        raise RuntimeError(f"OpenRouter 返回无 choices: {str(data)[:300]}")
    if choices[0].get("finish_reason") == "length":
        raise RuntimeError("模型输出被 max_tokens 截断：减少 -n 数量或换长输出模型")
    content = choices[0].get("message", {}).get("content")
    if not content:
        raise RuntimeError(f"OpenRouter 返回空 content: {str(data)[:300]}")
    return content


def extract_json(text):
    """从模型回复里稳健地抠出 JSON（容忍 markdown 代码块/前后废话）。"""
    text = text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else text
        if text.rstrip().endswith("```"):
            text = text.rstrip()[:-3]
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    # 退而求其次：找最外层的 [ ] 或 { }
    for open_ch, close_ch in (("[", "]"), ("{", "}")):
        start = text.find(open_ch)
        end = text.rfind(close_ch)
        if start != -1 and end > start:
            try:
                return json.loads(text[start:end + 1])
            except json.JSONDecodeError:
                continue
    raise ValueError(f"无法从模型输出解析 JSON：{text[:300]}...")

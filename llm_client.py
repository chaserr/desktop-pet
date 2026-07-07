"""Thin LLM client using stdlib urllib. Supports 3 providers:
- "codex": OpenAI-compatible /chat/completions (default: OpenAI gpt-4o-mini)
- "deepseek": OpenAI-compatible /chat/completions (deepseek-chat)
- "claude": Anthropic /v1/messages

For "codex" and "claude" we can optionally shell out to the locally installed
CLI (`claude -p …` / `codex exec …`), reusing the user's existing login instead
of an API key stored in this app."""
import json
import subprocess
from typing import Iterable
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import auth_detect

PROVIDER_CODEX = "codex"
PROVIDER_CLAUDE = "claude"
PROVIDER_DEEPSEEK = "deepseek"

PROVIDERS: tuple[str, ...] = (PROVIDER_CODEX, PROVIDER_CLAUDE, PROVIDER_DEEPSEEK)

DEFAULT_SETTINGS: dict[str, dict] = {
    PROVIDER_CODEX: {
        "api_key": "",
        "model": "gpt-4o-mini",
        "base_url": "https://api.openai.com/v1",
        "use_local_cli": False,
    },
    PROVIDER_CLAUDE: {
        "api_key": "",
        "model": "claude-sonnet-4-6",
        "base_url": "https://api.anthropic.com/v1",
        "use_local_cli": False,
    },
    PROVIDER_DEEPSEEK: {
        "api_key": "",
        "model": "deepseek-chat",
        "base_url": "https://api.deepseek.com/v1",
    },
}

DEFAULT_SYSTEM_PROMPT = (
    "你是苏酱（星街彗星，Hoshimachi Suisei），一只陪伴用户桌面的可爱虚拟宠物。"
    "用轻快、温柔、俏皮的中文短句回复。每条回复不超过 60 字，允许适度使用 emoji。"
    "如果用户在抱怨累/困/烦，先共情再给具体轻量建议。"
)


class LlmError(RuntimeError):
    pass


def chat(
    provider: str,
    api_key: str,
    model: str,
    base_url: str,
    messages: list[dict],
    system_prompt: str = "",
    max_tokens: int = 512,
    timeout: int = 30,
    use_local_cli: bool = False,
) -> str:
    """Send `messages` (list of {role, content}) and return the assistant text.
    When use_local_cli is True and the provider supports it, we shell out to the
    CLI instead of hitting the HTTP API."""
    provider = provider.lower()
    if use_local_cli and provider in (PROVIDER_CLAUDE, PROVIDER_CODEX):
        return _call_via_cli(provider, messages, system_prompt, timeout=max(60, timeout))
    if not api_key:
        raise LlmError(f"{provider}: 未配置 api_key")
    if provider == PROVIDER_CLAUDE:
        return _call_claude(api_key, model, base_url, messages, system_prompt, max_tokens, timeout)
    if provider in (PROVIDER_CODEX, PROVIDER_DEEPSEEK):
        return _call_openai_compat(api_key, model, base_url, messages, system_prompt, max_tokens, timeout)
    raise LlmError(f"未知 provider: {provider}")


def _serialize_history(messages: list[dict], system_prompt: str) -> str:
    parts: list[str] = []
    if system_prompt:
        parts.append(f"[system]\n{system_prompt}")
    for m in messages:
        role = m.get("role", "user")
        content = m.get("content", "")
        parts.append(f"[{role}]\n{content}")
    return "\n\n".join(parts)


def _call_via_cli(
    provider: str,
    messages: list[dict],
    system_prompt: str,
    timeout: int,
) -> str:
    probe = auth_detect.claude() if provider == PROVIDER_CLAUDE else auth_detect.codex()
    if not probe.usable:
        missing = "未安装" if not probe.installed else "未登录"
        raise LlmError(f"{provider} CLI {missing}")
    prompt = _serialize_history(messages, system_prompt)
    if provider == PROVIDER_CLAUDE:
        cmd = [probe.binary or "claude", "-p", prompt]
    else:
        cmd = [probe.binary or "codex", "exec", prompt]
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        raise LlmError(f"{provider} CLI 超时 ({timeout}s)") from None
    except OSError as exc:
        raise LlmError(f"{provider} CLI 调用失败: {exc}") from None
    if result.returncode != 0:
        err = (result.stderr or result.stdout or "").strip()
        raise LlmError(f"{provider} CLI 失败: {err[:400]}")
    text = (result.stdout or "").strip()
    if not text:
        raise LlmError(f"{provider} CLI 返回空内容")
    return text


def _post_json(url: str, headers: dict[str, str], body: dict, timeout: int) -> dict:
    data = json.dumps(body).encode("utf-8")
    req = Request(url, data=data, headers=headers, method="POST")
    try:
        with urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except HTTPError as e:
        err_body = e.read().decode("utf-8", errors="replace")
        raise LlmError(f"HTTP {e.code}: {err_body[:400]}") from None
    except URLError as e:
        raise LlmError(f"网络错误: {e.reason}") from None


def _call_openai_compat(
    api_key: str,
    model: str,
    base_url: str,
    messages: list[dict],
    system_prompt: str,
    max_tokens: int,
    timeout: int,
) -> str:
    url = f"{base_url.rstrip('/')}/chat/completions"
    final_msgs: list[dict] = []
    if system_prompt:
        final_msgs.append({"role": "system", "content": system_prompt})
    final_msgs.extend(messages)
    body = {
        "model": model,
        "messages": final_msgs,
        "max_tokens": max_tokens,
        "stream": False,
    }
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }
    data = _post_json(url, headers, body, timeout)
    try:
        return data["choices"][0]["message"]["content"].strip()
    except (KeyError, IndexError, TypeError):
        raise LlmError(f"返回格式异常: {json.dumps(data)[:400]}") from None


def _call_claude(
    api_key: str,
    model: str,
    base_url: str,
    messages: list[dict],
    system_prompt: str,
    max_tokens: int,
    timeout: int,
) -> str:
    url = f"{base_url.rstrip('/')}/messages"
    body: dict = {
        "model": model,
        "max_tokens": max_tokens,
        "messages": [{"role": m["role"], "content": m["content"]} for m in messages],
    }
    if system_prompt:
        body["system"] = system_prompt
    headers = {
        "Content-Type": "application/json",
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
    }
    data = _post_json(url, headers, body, timeout)
    try:
        parts: Iterable[dict] = data["content"]
        text_chunks = [p.get("text", "") for p in parts if p.get("type") == "text"]
        return "".join(text_chunks).strip()
    except (KeyError, TypeError):
        raise LlmError(f"返回格式异常: {json.dumps(data)[:400]}") from None

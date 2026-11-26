"""
Unified LLM client with automatic fallback.

Primary: Google Gemini Flash, with Groq and OpenRouter as configured fallbacks.
Model availability and quotas depend on the provider account.

Both call sites (intent extraction + chat generation) go through complete().
Gemini is called over plain REST (requests) so there is no extra SDK dependency to
break — the API key is the only thing needed.

Env:
  GEMINI_API_KEY   free key from https://aistudio.google.com/apikey (optional)
  GEMINI_MODEL     default "gemini-3.5-flash-lite"
  GROQ_API_KEY     existing
  GROQ_MODEL       default "llama-3.3-70b-versatile"
"""

import os
import logging
import requests

logger = logging.getLogger(__name__)

GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.5-flash-lite")
GROQ_MODEL = os.environ.get("GROQ_MODEL", "llama-3.3-70b-versatile")
OPENROUTER_MODEL = os.environ.get("OPENROUTER_MODEL", "meta-llama/llama-3.3-70b-instruct:free")

_groq_client = None


def complete(
    messages: list[dict],
    temperature: float = 0.7,
    max_tokens: int = 700,
    json_mode: bool = False,
) -> str:
    """
    Chat completion with a 3-tier fallback: Gemini → Groq → OpenRouter.

    messages: OpenAI-style [{"role": "system"|"user"|"assistant", "content": str}, ...]
    json_mode: ask the model to return a single JSON object.
    Returns the assistant text (JSON string if json_mode).
    """
    errors = []
    if os.environ.get("GEMINI_API_KEY"):
        try:
            return _gemini_complete(messages, temperature, max_tokens, json_mode, os.environ["GEMINI_API_KEY"])
        except Exception as e:
            errors.append(f"gemini:{type(e).__name__}")
            logger.warning(f"[llm] Gemini failed ({type(e).__name__}) — trying Groq")
    try:
        return _groq_complete(messages, temperature, max_tokens, json_mode)
    except Exception as e:
        errors.append(f"groq:{type(e).__name__}")
        logger.warning(f"[llm] Groq failed ({type(e).__name__}) — trying OpenRouter")
    if os.environ.get("OPENROUTER_API_KEY"):
        try:
            return _openrouter_complete(messages, temperature, max_tokens, json_mode, os.environ["OPENROUTER_API_KEY"])
        except Exception as e:
            errors.append(f"openrouter:{type(e).__name__}")
            logger.error(f"[llm] OpenRouter failed ({type(e).__name__})")
    raise RuntimeError("all LLM providers failed: " + ", ".join(errors))


# ── OpenRouter (OpenAI-compatible REST) ───────────────────────────────────────

def _openrouter_complete(messages, temperature, max_tokens, json_mode, key) -> str:
    body = {
        "model": OPENROUTER_MODEL,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    if json_mode:
        body["response_format"] = {"type": "json_object"}
    resp = requests.post(
        "https://openrouter.ai/api/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {key}",
            "HTTP-Referer": os.environ.get("PUBLIC_BASE_URL", "http://127.0.0.1:8000"),
            "X-Title": "ApnaGhar Real Estate",
        },
        json=body,
        timeout=45,
    )
    resp.raise_for_status()
    data = resp.json()
    choices = data.get("choices") or []
    if not choices:
        raise RuntimeError(f"OpenRouter no choices: {str(data)[:160]}")
    text = (choices[0].get("message", {}).get("content") or "").strip()
    if not text:
        raise RuntimeError("OpenRouter returned empty text")
    return text


# ── Gemini (REST) ─────────────────────────────────────────────────────────────

def _gemini_complete(messages, temperature, max_tokens, json_mode, key) -> str:
    # Gemini separates the system instruction from the turn contents.
    system_parts = [m["content"] for m in messages if m["role"] == "system"]
    contents = []
    for m in messages:
        if m["role"] == "system":
            continue
        role = "user" if m["role"] == "user" else "model"
        contents.append({"role": role, "parts": [{"text": m["content"]}]})

    gen_cfg = {
        "temperature": temperature,
        "maxOutputTokens": max_tokens,
    }
    if GEMINI_MODEL.startswith("gemini-2.5-flash"):
        gen_cfg["thinkingConfig"] = {"thinkingBudget": 0}
    elif "flash-lite" in GEMINI_MODEL:
        gen_cfg["thinkingConfig"] = {"thinkingLevel": "MINIMAL"}
        gen_cfg["maxOutputTokens"] = max(max_tokens, 512)
    else:
        # Current Flash models use thinking levels and count thinking in the output cap.
        gen_cfg["thinkingConfig"] = {"thinkingLevel": "LOW"}
        gen_cfg["maxOutputTokens"] = max(max_tokens, 1024)
    if json_mode:
        gen_cfg["responseMimeType"] = "application/json"

    body = {"contents": contents, "generationConfig": gen_cfg}
    if system_parts:
        body["systemInstruction"] = {"parts": [{"text": "\n\n".join(system_parts)}]}

    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/"
        f"{GEMINI_MODEL}:generateContent"
    )
    resp = requests.post(url, headers={"x-goog-api-key": key}, json=body, timeout=(10, 45))
    resp.raise_for_status()
    data = resp.json()

    candidates = data.get("candidates") or []
    if not candidates:
        raise RuntimeError(f"Gemini returned no candidates: {str(data)[:160]}")
    if candidates[0].get("finishReason") not in (None, "STOP"):
        raise RuntimeError("Gemini returned an incomplete or blocked response")
    parts = candidates[0].get("content", {}).get("parts") or []
    text = "".join(p.get("text", "") for p in parts if not p.get("thought")).strip()
    if not text:
        raise RuntimeError("Gemini returned empty text")
    return text


# ── Groq (SDK) ────────────────────────────────────────────────────────────────

def _get_groq():
    global _groq_client
    if _groq_client is None:
        from groq import Groq
        key = os.environ.get("GROQ_API_KEY")
        if not key:
            raise RuntimeError("GROQ_API_KEY not set in .env")
        _groq_client = Groq(api_key=key)
    return _groq_client


def _groq_complete(messages, temperature, max_tokens, json_mode) -> str:
    kwargs = {}
    if json_mode:
        kwargs["response_format"] = {"type": "json_object"}
    resp = _get_groq().chat.completions.create(
        model=GROQ_MODEL,
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
        **kwargs,
    )
    return resp.choices[0].message.content.strip()

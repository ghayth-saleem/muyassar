"""One place every agent calls the language model from.

    from muyassar.llm import ask
    text = ask(system="...", user="...")

MUYASSAR_LLM picks the provider:
- anthropic (default): Claude Sonnet 5.5, key from ANTHROPIC_API_KEY in .env.
- ollama: the local qwen2.5 model, for when cloud credit is late or the
  network is down (a risk the plan names). Answers are weaker in Arabic.

Run `python -m muyassar.llm` to check the setup without printing the key.
"""
import json
import os
import sys

from dotenv import load_dotenv

from muyassar import ROOT

load_dotenv(ROOT / ".env")

PROVIDER = os.environ.get("MUYASSAR_LLM", "anthropic")
# Sonnet for cost ($2/$10 per MTok vs Opus $4/$20). Set MUYASSAR_CLAUDE_MODEL=claude-opus-5-5
# for a route that needs more judgment, e.g. the policy agent's gap analysis.
CLAUDE_MODEL = os.environ.get("MUYASSAR_CLAUDE_MODEL", "claude-sonnet-5-5")
OLLAMA_MODEL = os.environ.get("MUYASSAR_OLLAMA_MODEL", "qwen2.5:7b-instruct-q4_K_M")
EFFORT = os.environ.get("MUYASSAR_EFFORT", "medium")

_client = None


def _claude():
    global _client
    if _client is None:
        import anthropic

        if not os.environ.get("ANTHROPIC_API_KEY"):
            raise RuntimeError("ANTHROPIC_API_KEY مش موجود. حطه في ملف .env بجذر المشروع (شوف .env.example).")
        _client = anthropic.Anthropic()
    return _client


def ask(system: str, user: str, max_tokens: int = 16000, schema: dict | None = None):
    """Model reply as text, or as a dict matching `schema` (a JSON Schema) when given."""
    if PROVIDER == "ollama":
        import ollama

        reply = ollama.chat(
            model=OLLAMA_MODEL,
            messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
            format=schema,
        )
        text = reply["message"]["content"]
        return json.loads(text) if schema else text

    output_config = {"effort": EFFORT}
    if schema:
        output_config["format"] = {"type": "json_schema", "schema": schema}

    # fallbacks="default": if a safety classifier declines (e.g. a medical
    # detail in a disability-card request), the API retries on a fallback
    # model inside the same call instead of returning nothing.
    response = _claude().beta.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": user}],
        output_config=output_config,
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",
    )
    if response.stop_reason == "refusal":
        raise RuntimeError(f"النموذج رفض الطلب: {response.stop_details}")
    text = "".join(b.text for b in response.content if b.type == "text")
    return json.loads(text) if schema else text


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    if PROVIDER == "anthropic":
        key = os.environ.get("ANTHROPIC_API_KEY", "")
        source = "من .env" if (ROOT / ".env").is_file() else "من متغيرات البيئة"
        print(f"المزوّد: Claude ({CLAUDE_MODEL})، المفتاح {'موجود ' + source if key else 'مش موجود'}")
    else:
        print(f"المزوّد: Ollama ({OLLAMA_MODEL})")
    print(ask("جاوب بجملة وحدة.", "شو اسم القانون رقم 24 لسنة 2023 في الأردن؟", max_tokens=2000))


if __name__ == "__main__":
    main()

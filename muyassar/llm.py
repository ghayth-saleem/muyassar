"""One place every agent calls the language model from.

    from muyassar.llm import ask
    text = ask(system="...", user="...")

The model itself is a provider (muyassar/providers.py), picked by
MUYASSAR_LLM in .env: anthropic (default), gemini or ollama. Tests and demos
swap it with use(), for example for a ReplayProvider that answers from a
logged run without any API call.

Run `python -m muyassar.llm` to check the setup without printing the key.
This sends one short request, so it uses credit.
"""
import os
import sys

from dotenv import load_dotenv

from muyassar import ROOT
from muyassar.providers import Provider, from_env

load_dotenv(ROOT / ".env")

_provider: Provider | None = None


def provider() -> Provider:
    global _provider
    if _provider is None:
        _provider = from_env()
    return _provider


def use(p: Provider | None) -> None:
    """Replace the provider (None goes back to the one .env names)."""
    global _provider
    _provider = p


def model_name() -> str:
    return provider().name


def ask(system: str, user: str, max_tokens: int = 16000, schema: dict | None = None):
    """Model reply as text, or as a dict matching `schema` (a JSON Schema) when given."""
    return provider().ask(system, user, max_tokens=max_tokens, schema=schema)


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    name = os.environ.get("MUYASSAR_LLM", "anthropic")
    keys = {"anthropic": "ANTHROPIC_API_KEY", "gemini": "GEMINI_API_KEY"}
    if name in keys:
        print(f"المزوّد: {name} ({model_name()})، المفتاح {'موجود' if os.environ.get(keys[name]) else 'مش موجود'}")
    else:
        print(f"المزوّد: {model_name()}")
    print(ask("جاوب بجملة وحدة.", "شو اسم القانون رقم 24 لسنة 2023 في الأردن؟", max_tokens=2000))


if __name__ == "__main__":
    main()

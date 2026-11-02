"""Model providers behind one interface, so the agents never name a vendor.

Every provider has `name` (written to the audit log) and
`ask(system, user, max_tokens, schema) -> str | dict`: text, or a dict
matching `schema` (a JSON Schema) when one is given.

MUYASSAR_LLM picks one:
- anthropic (default): Claude, key ANTHROPIC_API_KEY.
- gemini: Google Gemini, key GEMINI_API_KEY (or GOOGLE_API_KEY). Written
  against the google-genai SDK docs and not yet run against the API.
- ollama: a local model, for when the network or credit is out. Weaker Arabic.
- replay: answers from a logged run instead of a model; for tests and demos
  without a key. See ReplayProvider.

MUYASSAR_LLM_FALLBACK (gemini or ollama) names a second provider, used when
the first fails: credit out, network down, API error. A refusal is the model's
answer and does not fall through. `name` follows the provider that answered,
so the audit log says which model wrote each step.
"""
import json
import os
import sys
from typing import Protocol


class ModelRefused(RuntimeError):
    """The model declined to answer; another model must not be asked instead."""


class Provider(Protocol):
    name: str

    def ask(self, system: str, user: str, max_tokens: int = 16000, schema: dict | None = None): ...


class AnthropicProvider:
    def __init__(self, model: str | None = None, effort: str | None = None):
        # Sonnet for cost ($2/$10 per MTok vs Opus $4/$20); MUYASSAR_CLAUDE_MODEL overrides.
        self.model = model or os.environ.get("MUYASSAR_CLAUDE_MODEL", "claude-sonnet-5-5")
        self.effort = effort or os.environ.get("MUYASSAR_EFFORT", "medium")
        self.name = self.model
        self._client = None

    def _claude(self):
        if self._client is None:
            import anthropic

            if not os.environ.get("ANTHROPIC_API_KEY"):
                raise RuntimeError("ANTHROPIC_API_KEY مش موجود. حطه في ملف .env بجذر المشروع (شوف .env.example).")
            self._client = anthropic.Anthropic()
        return self._client

    def ask(self, system, user, max_tokens=16000, schema=None):
        output_config = {"effort": self.effort}
        if schema:
            output_config["format"] = {"type": "json_schema", "schema": schema}
        # fallbacks="default": if a safety classifier declines (e.g. a medical
        # detail in a disability-card request), the API retries on a fallback
        # model inside the same call instead of returning nothing.
        response = self._claude().beta.messages.create(
            model=self.model,
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": user}],
            output_config=output_config,
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
        )
        if response.stop_reason == "refusal":
            raise ModelRefused(f"النموذج رفض الطلب: {response.stop_details}")
        text = "".join(b.text for b in response.content if b.type == "text")
        return json.loads(text) if schema else text


class FallbackProvider:
    def __init__(self, primary: Provider, backup: Provider):
        self.primary, self.backup = primary, backup
        self.name = primary.name

    def ask(self, system, user, max_tokens=16000, schema=None):
        try:
            reply = self.primary.ask(system, user, max_tokens=max_tokens, schema=schema)
            self.name = self.primary.name
        except ModelRefused:
            raise
        except Exception as e:
            print(f"{self.primary.name} ما رد ({type(e).__name__})، بنكمل على {self.backup.name}", file=sys.stderr)
            reply = self.backup.ask(system, user, max_tokens=max_tokens, schema=schema)
            self.name = self.backup.name
        return reply


class GeminiProvider:
    def __init__(self, model: str | None = None):
        self.model = model or os.environ.get("MUYASSAR_GEMINI_MODEL", "gemini-flash-latest")
        self.name = self.model
        self._client = None

    def _gemini(self):
        if self._client is None:
            from google import genai  # pip install google-genai

            if not (os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")):
                raise RuntimeError("GEMINI_API_KEY مش موجود. حطه في ملف .env بجذر المشروع.")
            self._client = genai.Client()  # reads GEMINI_API_KEY / GOOGLE_API_KEY
        return self._client

    def ask(self, system, user, max_tokens=16000, schema=None):
        from google.genai import types

        config = types.GenerateContentConfig(system_instruction=system, max_output_tokens=max_tokens)
        if schema:
            config.response_mime_type = "application/json"
            config.response_json_schema = schema
        response = self._gemini().models.generate_content(model=self.model, contents=user, config=config)
        text = response.text or ""
        return json.loads(text) if schema else text


class OllamaProvider:
    def __init__(self, model: str | None = None):
        self.model = model or os.environ.get("MUYASSAR_OLLAMA_MODEL", "qwen2.5:7b-instruct-q4_K_M")
        self.name = f"ollama {self.model}"

    def ask(self, system, user, max_tokens=16000, schema=None):
        import ollama

        reply = ollama.chat(
            model=self.model,
            messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
            format=schema,
        )
        text = reply["message"]["content"]
        return json.loads(text) if schema else text


class ReplayProvider:
    """Answers each agent's call with what that agent answered in a logged run.

    steps: the logged steps of one run (logs/scenarios.jsonl lines). Calls are
    matched to agents by their system prompt and served in order, so the
    engine, the citation rule and the conflict rule run for real on top of
    replies the model once gave. The reply is rebuilt as the model sent it:
    citations the rule dropped are put back, and the orchestrator's own
    sensitive flag is separated from one the code added.
    """

    def __init__(self, steps: list[dict]):
        self.name = "replay"
        self.queues: dict[str, list[dict]] = {}
        for s in steps:
            if s["agent"] != "human":
                self.queues.setdefault(s["agent"], []).append(s)
        self.calls: list[str] = []

    def _agent_for(self, system: str) -> str:
        from muyassar.agents import AGENTS, ORCHESTRATOR_SYSTEM

        if system == ORCHESTRATOR_SYSTEM:
            return "orchestrator"
        for key, agent in AGENTS.items():
            if agent.system == system:
                return key
        raise LookupError("system prompt لا يطابق أي وكيل")

    def ask(self, system, user, max_tokens=16000, schema=None):
        key = self._agent_for(system)
        if not self.queues.get(key):
            raise LookupError(f"ما في رد مسجّل باقي للوكيل {key}")
        step = self.queues[key].pop(0)
        self.calls.append(key)
        cited = list(step.get("cited", [])) + list(step.get("dropped_citations", []))
        if key == "orchestrator":
            return {
                "steps": step.get("steps", []),
                "conflicts": step.get("conflicts", []),
                "citizen_reply": step.get("citizen_reply", ""),
                "staff_note": step.get("staff_note", ""),
                "decision": step["decision"],
                "confidence": step["confidence"],
                "cited": cited,
                # only the model's own call; the rule and the agents' flags are re-applied by the code
                "sensitive": step.get("sensitive_by", "model" if step["sensitive"] else None) == "model",
                "sensitive_reason": step.get("sensitive_reason", "") if step.get("sensitive_by") == "model" else "",
            }
        return {
            "steps": step.get("steps", []),
            "finding": step.get("finding", ""),
            "decision": step["decision"],
            "confidence": step["confidence"],
            "cited": cited,
            "sensitive": step["sensitive"],
            "sensitive_reason": step.get("sensitive_reason", ""),
            "contradicts_guide": step.get("contradicts_guide", False),
            "contradicted_id": step.get("contradicted_id", ""),
            "gap_title": step.get("gap_title", ""),
            "gap": step.get("gap", ""),
            "global_example_id": step.get("global_example_id", ""),
            "global_example": step.get("global_example", ""),
        }


def _named(name: str) -> Provider:
    if name == "anthropic":
        return AnthropicProvider()
    if name == "gemini":
        return GeminiProvider()
    if name == "ollama":
        return OllamaProvider()
    raise ValueError(f"المزوّد {name!r} مش معروف (anthropic أو gemini أو ollama)")


def from_env() -> Provider:
    main = _named(os.environ.get("MUYASSAR_LLM", "anthropic"))
    backup = os.environ.get("MUYASSAR_LLM_FALLBACK")
    return FallbackProvider(main, _named(backup)) if backup else main

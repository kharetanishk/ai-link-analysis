import asyncio
import logging
import time
from dataclasses import dataclass, field

from pydantic import ValidationError

from app.config import Settings
from app.errors import LLMConfigError, LLMOutputError, LLMUnavailableError
from app.schemas import LLMAnalysis, TokenUsage

log = logging.getLogger("app.llm")


@dataclass
class LLMResult:
    data: LLMAnalysis
    model: str
    latency_ms: int
    usage: TokenUsage
    citations: list[str] = field(default_factory=list)


class LLMService:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.schema = response_schema()
        self._semaphore = asyncio.Semaphore(settings.llm_max_concurrency)
        self._client = None
        if settings.gemini_api_key:
            from google import genai

            self._client = genai.Client(api_key=settings.gemini_api_key.get_secret_value())

    @property
    def configured(self) -> bool:
        return self._client is not None

    async def analyze(self, system_prompt: str, user_prompt: str) -> LLMResult:
        if not self._client:
            raise LLMConfigError()
        models = list(dict.fromkeys([self.settings.gemini_model, self.settings.gemini_fallback_model]))
        output_error = False
        async with self._semaphore:
            for model in models:
                # invalid JSON aaye to same model ek baar retry, API fail ho to seedha fallback model
                for attempt in (1, 2):
                    try:
                        return await self._generate(model, system_prompt, user_prompt)
                    except (ValidationError, ValueError) as exc:
                        output_error = True
                        log.warning("invalid output model=%s attempt=%s: %s", model, attempt, str(exc)[:300])
                    except LLMConfigError:
                        raise
                    except Exception as exc:  # noqa: BLE001 - provider SDK errors ka koi stable base class nahi
                        log.warning("llm call failed model=%s: %s: %s", model, type(exc).__name__, str(exc)[:300])
                        break
        raise LLMOutputError() if output_error else LLMUnavailableError()

    async def _generate(self, model: str, system_prompt: str, user_prompt: str) -> LLMResult:
        body = {
            "model": model,
            "input": user_prompt,
            "system_instruction": system_prompt,
            "response_format": {"type": "text", "mime_type": "application/json", "schema": self.schema},
            "generation_config": {
                "thinking_level": self.settings.gemini_thinking_level,
                "max_output_tokens": self.settings.gemini_max_output_tokens,
            },
            "store": False,
        }
        if self.settings.enable_search_grounding:
            body["tools"] = [{"type": "google_search"}]

        started = time.perf_counter()
        try:
            interaction = await asyncio.wait_for(
                self._client.aio.interactions.create(**body, timeout=self.settings.llm_timeout_seconds),
                timeout=self.settings.llm_timeout_seconds + 5,
            )
        except Exception as exc:
            if (getattr(exc, "status_code", None) or getattr(exc, "code", None)) in (401, 403):
                raise LLMConfigError("The AI service rejected the server's API key.") from exc
            raise
        latency_ms = int((time.perf_counter() - started) * 1000)

        if interaction.status != "completed":
            raise ValueError(f"interaction status {interaction.status}")
        data = LLMAnalysis.model_validate_json(interaction.output_text or "")
        usage = interaction.usage
        tokens = TokenUsage(
            input=(usage.total_input_tokens or 0) if usage else 0,
            output=(usage.total_output_tokens or 0) if usage else 0,
            thinking=(usage.total_thought_tokens or 0) if usage else 0,
        )
        log.info("llm ok model=%s latency_ms=%s tokens=%s", model, latency_ms, tokens.model_dump())
        return LLMResult(data, model, latency_ms, tokens, _collect_urls(interaction.model_dump()))

    def estimate_cost(self, usage: TokenUsage) -> float:
        s = self.settings
        cost = usage.input * s.price_input_per_million + (usage.output + usage.thinking) * s.price_output_per_million
        return round(cost / 1_000_000, 6)


def response_schema() -> dict:
    # Gemini ko flat schema chahiye: $ref inline karo, title/default hata do
    raw = LLMAnalysis.model_json_schema()
    defs = raw.pop("$defs", {})

    def walk(node):
        if isinstance(node, dict):
            if "$ref" in node:
                return walk(defs[node["$ref"].split("/")[-1]])
            return {k: walk(v) for k, v in node.items() if k not in ("title", "default")}
        if isinstance(node, list):
            return [walk(v) for v in node]
        return node

    return walk(raw)


def _collect_urls(node, found: list[str] | None = None) -> list[str]:
    found = [] if found is None else found
    if isinstance(node, dict):
        url = node.get("url")
        if isinstance(url, str) and url.startswith("http") and url not in found:
            found.append(url)
        for value in node.values():
            _collect_urls(value, found)
    elif isinstance(node, list):
        for value in node:
            _collect_urls(value, found)
    return found

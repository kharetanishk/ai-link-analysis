import asyncio
import logging
import time
from dataclasses import dataclass, field

from pydantic import BaseModel, ValidationError

from app.config import Settings
from app.errors import AIQuotaExhaustedError, AppError, LLMConfigError, LLMOutputError, LLMUnavailableError
from app.schemas import LLMAnalysis, MarketAnalysis, SiteAnalysis, TokenUsage
from app.utils.progress import Progress, noop

log = logging.getLogger("app.llm")

# do chhote parallel calls ek bade call se ~2x fast hote hain; input tokens thode badhte hain
PARTS: tuple[tuple[type[BaseModel], str], ...] = (
    (MarketAnalysis, "Return ONLY: brand, competitor_analysis and target_search_queries."),
    (SiteAnalysis, "Return ONLY: seo_improvements, top_services and target_audience."),
)
PART_DONE = {
    MarketAnalysis: ("market_ready", "Competitors & search queries ready"),
    SiteAnalysis: ("site_ready", "SEO, services & audience ready"),
}
QUOTA_STATUS = {402, 429}
ERROR_PRIORITY = (LLMConfigError, AIQuotaExhaustedError, LLMOutputError)


@dataclass
class LLMResult:
    data: LLMAnalysis
    model: str
    latency_ms: int
    usage: TokenUsage
    citations: list[str] = field(default_factory=list)


@dataclass
class _Part:
    data: BaseModel
    model: str
    latency_ms: int
    usage: TokenUsage
    citations: list[str]


class LLMService:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.schemas = {part: response_schema(part) for part, _ in PARTS}
        self._semaphore = asyncio.Semaphore(settings.llm_max_concurrency)
        self._client = None
        if settings.gemini_api_key:
            from google import genai

            self._client = genai.Client(api_key=settings.gemini_api_key.get_secret_value())

    @property
    def configured(self) -> bool:
        return self._client is not None

    async def analyze(self, system_prompt: str, user_prompt: str, progress: Progress = noop) -> LLMResult:
        if not self._client:
            raise LLMConfigError()
        done = 0

        async def run(part: type[BaseModel], hint: str) -> _Part:
            nonlocal done
            result = await self._run_part(part, f"{user_prompt}\n\n{hint}", system_prompt, progress)
            done += 1
            progress(PART_DONE[part][0], 40 + 25 * done, PART_DONE[part][1])
            return result

        async with self._semaphore:
            results = await asyncio.gather(*(run(part, hint) for part, hint in PARTS), return_exceptions=True)
        errors = [r for r in results if isinstance(r, BaseException)]
        if errors:
            # sabse "actionable" error user ko dikhao
            raise next((e for kind in ERROR_PRIORITY for e in errors if isinstance(e, kind)), errors[0])

        merged = {k: v for r in results for k, v in r.data}
        return LLMResult(
            data=LLMAnalysis.model_validate(merged),
            model=", ".join(dict.fromkeys(r.model for r in results)),
            latency_ms=max(r.latency_ms for r in results),
            usage=TokenUsage(
                input=sum(r.usage.input for r in results),
                output=sum(r.usage.output for r in results),
                thinking=sum(r.usage.thinking for r in results),
            ),
            citations=[u for r in results for u in r.citations],
        )

    async def _run_part(
        self, part: type[BaseModel], user_prompt: str, system_prompt: str, progress: Progress = noop
    ) -> _Part:
        models = list(dict.fromkeys([self.settings.gemini_model, self.settings.gemini_fallback_model]))
        output_error = quota_hit = False
        for index, model in enumerate(models):
            if index:
                progress("fallback", None, "Primary model is busy, switching to the backup model")
            # invalid JSON aaye to same model ek baar retry, API fail ho to seedha fallback model
            for attempt in (1, 2):
                try:
                    return await self._generate(model, part, system_prompt, user_prompt)
                except (ValidationError, ValueError) as exc:
                    output_error = True
                    log.warning(
                        "invalid output model=%s part=%s attempt=%s: %s", model, part.__name__, attempt, str(exc)[:300]
                    )
                except AppError:
                    raise
                except Exception as exc:  # noqa: BLE001 - provider SDK errors ka koi stable base class nahi
                    log.warning(
                        "llm call failed model=%s part=%s: %s: %s",
                        model,
                        part.__name__,
                        type(exc).__name__,
                        str(exc)[:300],
                    )
                    quota_hit = quota_hit or _is_quota_error(exc)
                    break
        if quota_hit:
            raise AIQuotaExhaustedError()
        raise LLMOutputError() if output_error else LLMUnavailableError()

    async def _generate(self, model: str, part: type[BaseModel], system_prompt: str, user_prompt: str) -> _Part:
        body = {
            "model": model,
            "input": user_prompt,
            "system_instruction": system_prompt,
            "response_format": {"type": "text", "mime_type": "application/json", "schema": self.schemas[part]},
            "generation_config": {
                "thinking_level": self.settings.gemini_thinking_level,
                "max_output_tokens": self.settings.gemini_max_output_tokens,
            },
            "store": False,
        }
        if self.settings.enable_search_grounding and part is MarketAnalysis:
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
        data = part.model_validate_json(interaction.output_text or "")
        usage = interaction.usage
        tokens = TokenUsage(
            input=(usage.total_input_tokens or 0) if usage else 0,
            output=(usage.total_output_tokens or 0) if usage else 0,
            thinking=(usage.total_thought_tokens or 0) if usage else 0,
        )
        log.info(
            "llm ok model=%s part=%s latency_ms=%s tokens=%s", model, part.__name__, latency_ms, tokens.model_dump()
        )
        return _Part(data, model, latency_ms, tokens, _collect_urls(interaction.model_dump()))

    def estimate_cost(self, usage: TokenUsage) -> float:
        s = self.settings
        cost = usage.input * s.price_input_per_million + (usage.output + usage.thinking) * s.price_output_per_million
        return round(cost / 1_000_000, 6)


def _is_quota_error(exc: Exception) -> bool:
    status = getattr(exc, "status_code", None) or getattr(exc, "code", None)
    return status in QUOTA_STATUS or "RESOURCE_EXHAUSTED" in str(exc)


def response_schema(model: type[BaseModel] = LLMAnalysis) -> dict:
    # Gemini ko flat schema chahiye: $ref inline karo, title/default hata do
    raw = model.model_json_schema()
    defs = raw.pop("$defs", {})

    def walk(node, is_properties=False):
        if isinstance(node, dict):
            if "$ref" in node:
                return walk(defs[node["$ref"].split("/")[-1]])
            # "properties" ke andar key field ka naam hai (jaise "title"), metadata nahi
            return {
                k: walk(v, k == "properties" and not is_properties)
                for k, v in node.items()
                if is_properties or k not in ("title", "default")
            }
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

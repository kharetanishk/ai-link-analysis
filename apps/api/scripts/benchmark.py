"""LLM benchmark: har model ko same websites par chala ke latency, tokens, cost aur quality checks measure karta hai.

Usage (apps/api se):  .venv/bin/python -m scripts.benchmark --models gemini-3.5-flash-lite gemini-3.8-flash
"""

import argparse
import asyncio
import json
import statistics
import time
from datetime import UTC, datetime
from pathlib import Path

import httpx

from app.config import get_settings
from app.errors import AppError
from app.services.analysis_service import SYSTEM_PROMPT, build_prompt
from app.services.llm_service import LLMService
from app.services.website_extractor import WebsiteExtractor
from app.utils.validators import normalize_url

SITES = ["stripe.com", "zerodha.com", "hubspot.com", "bluetokaicoffee.com", "python.org"]
# USD per 1M tokens (input, output) - AI Studio pricing page, Nov 2026
PRICES = {
    "gemini-3.5-flash-lite": (0.30, 2.50),
    "gemini-3.1-flash-lite": (0.25, 1.50),
    "gemini-3.8-flash": (0.75, 3.75),
    "gemini-3-flash-preview": (0.50, 3.00),
}


def quality(data) -> dict:
    seo = data.seo_improvements
    return {
        "competitors": len(data.competitor_analysis.competitors),
        "services_from_site": sum(s.source == "website" for s in data.top_services),
        "title_len_ok": 30 <= len(seo.recommended_title) <= 65,
        "meta_len_ok": 120 <= len(seo.meta_description) <= 165,
        "platforms_used": len({p for q in data.target_search_queries for p in q.platforms}),
    }


async def run(models: list[str], sites: list[str], out: Path) -> None:
    base = get_settings()
    rows = []
    async with httpx.AsyncClient(timeout=base.fetch_timeout_seconds, follow_redirects=False) as client:
        extractor = WebsiteExtractor(client, base)
        prompts = {}
        for site in sites:
            try:
                prompts[site] = build_prompt(await extractor.extract(normalize_url(site)), base.content_char_budget)
            except AppError as exc:
                print(f"skip {site}: {exc.code}")

        for model in models:
            settings = base.model_copy(update={"gemini_model": model, "gemini_fallback_model": model})
            llm = LLMService(settings)
            price_in, price_out = PRICES.get(model, (base.price_input_per_million, base.price_output_per_million))
            for site, prompt in prompts.items():
                started = time.perf_counter()
                try:
                    result = await llm.analyze(SYSTEM_PROMPT, prompt)
                except AppError as exc:
                    rows.append({"model": model, "site": site, "ok": False, "error": exc.code})
                    print(f"{model:24} {site:22} FAIL {exc.code}")
                    continue
                u = result.usage
                cost = (u.input * price_in + (u.output + u.thinking) * price_out) / 1_000_000
                row = {
                    "model": model,
                    "site": site,
                    "ok": True,
                    "latency_s": round(time.perf_counter() - started, 2),
                    "input_tokens": u.input,
                    "output_tokens": u.output,
                    "thinking_tokens": u.thinking,
                    "cost_usd": round(cost, 5),
                    "brand": result.data.brand.name,
                    **quality(result.data),
                    "competitor_names": [c.name for c in result.data.competitor_analysis.competitors],
                }
                rows.append(row)
                print(f"{model:24} {site:22} {row['latency_s']:6.2f}s  ${cost:.5f}  {row['competitor_names']}")

    out.write_text(json.dumps({"run_at": datetime.now(UTC).isoformat(), "rows": rows}, indent=2))
    print("\n| Model | Success | Median latency | p-max latency | Avg input tok | Avg output tok | Avg cost |")
    print("|---|---|---|---|---|---|---|")
    for model in models:
        ok = [r for r in rows if r["model"] == model and r["ok"]]
        total = sum(1 for r in rows if r["model"] == model)
        if not ok:
            print(f"| {model} | 0/{total} | - | - | - | - | - |")
            continue
        lat = [r["latency_s"] for r in ok]
        avg = {
            k: statistics.mean(r[k] for r in ok)
            for k in ("input_tokens", "output_tokens", "thinking_tokens", "cost_usd")
        }
        print(
            f"| {model} | {len(ok)}/{total} | {statistics.median(lat):.1f}s | {max(lat):.1f}s | "
            f"{avg['input_tokens']:,.0f} | {avg['output_tokens'] + avg['thinking_tokens']:,.0f} | "
            f"${avg['cost_usd']:.4f} |"
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--models", nargs="+", default=list(PRICES))
    parser.add_argument("--sites", nargs="+", default=SITES)
    parser.add_argument("--out", type=Path, default=Path("benchmark_results.json"))
    args = parser.parse_args()
    asyncio.run(run(args.models, args.sites, args.out))

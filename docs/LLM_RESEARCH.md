# LLM Platform & Model Research

**Goal:** choose the LLM that gives the best balance of **accuracy, response speed, API cost and reliable structured JSON** for website link analysis.

**How to read this document.** Every number is tagged:

- **[Measured]**: produced by this project's benchmark script or by live production requests, on 18–19 Nov 2026.
- **[Official]**: taken from the provider's pricing or model documentation (Nov 2026).
- **[Estimate]**: calculated from our measured token profile × official prices. Not tested.

No model is claimed to have "maximum accuracy". Accuracy is described from what we observed on real websites.

---

## 1. Workload profile [Measured]

One analysis = **2 parallel LLM calls** (brand + competitors + queries, and SEO + services + audience) with the cleaned website text (homepage plus up to 3 sub-pages, capped at ~24k characters).

| Metric | Value |
|---|---|
| Input tokens per analysis | **~7,200 average** (6,000–8,700) |
| Output tokens per analysis (visible + thinking) | **~4,900 average** with `gemini-3.1-flash-lite` |
| Output format | Strict JSON schema, ~70 fields, nested lists |
| Calls per analysis | 2, in parallel (+1 retry or fallback only on failure) |

This profile is the basis for every estimate below.

---

## 2. Platform comparison (A)

Prices are USD per 1M tokens, standard tier.

| Provider | Model | Input / Output price [Official] | Context window [Official] | Structured JSON [Official] | Est. cost / analysis | Speed | Suitability |
|---|---|---|---|---|---|---|---|
| **Google** | **gemini-3.1-flash-lite** | $0.25 / $1.50 | 1M class¹ | Native JSON-schema output | **$0.0092 [Measured]** | **Median 15.7s [Measured]** | ✅ **Recommended** |
| Google | gemini-3.5-flash-lite | $0.30 / $2.50 | 1,048,576 in / 65,536 out | Native JSON schema + Search grounding | **$0.0087 [Measured]** | Median 44.7s, max 110.7s [Measured] | ✅ Fallback |
| Google | gemini-3.8-flash | $0.75 / $3.75 (doubles on 1 Jan 2027) | 1M class¹ | Native JSON schema | ~$0.024 [Estimate] | 0/5 completed within 120s; 503 "high demand" [Measured] | ⚠️ Capable, but slow and unavailable during tests |
| Anthropic | claude-haiku-5-5 | $0.10 / $0.50 (≤100K prompt) | 1M | Structured outputs (`output_config.format`) | ~$0.0032 [Estimate] | Not measured | 🔬 Strong candidate: cheapest on paper |
| Anthropic | claude-sonnet-5-5 | $2.00 / $10.00 | 1M | Structured outputs | ~$0.064 [Estimate] | Not measured | Too expensive for this task |
| OpenAI | gpt-5-mini | $0.25 / $2.00 | Not listed on pricing page | Structured Outputs (JSON schema) | ~$0.012 [Estimate] | Not measured | 🔬 Viable alternative |
| OpenAI | gpt-6-luna | $0.10 / $0.50 | Not listed on pricing page | Not stated on pricing page | ~$0.0032 [Estimate] | Not measured | 🔬 Cheap; verify JSON support |
| DeepSeek | deepseek-flash (V4.1) | $0.15 / $0.60 off-peak · $0.30 / $1.20 peak | 1M in / 384K out | JSON output mode | ~$0.004–0.008 [Estimate] | Not measured | 🔬 Cheap; JSON mode is looser than schema enforcement |

¹ The AI Studio models page lists context limits only for some models. `gemini-3.5-flash-lite` is documented at 1,048,576 tokens. The other Gemini 3.x Flash models belong to the same 1M-context family. Our prompts (<10k tokens) are far below any limit.

**Why only Gemini was benchmarked.** The benchmark harness needs a live API key per provider, and only a Gemini key was available for this test. Other providers are compared on official pricing and documented capabilities, and are marked as estimates.

---

## 3. Benchmark results [Measured]

**Method:** `apps/api/scripts/benchmark.py` extracts 5 real websites once, then sends the **identical prompt** to each model. Thinking level is `low`, the timeout is 120s per call, and there is no fallback, so each model is measured alone. Raw data: [`benchmark_results.json`](benchmark_results.json).

Sites: `stripe.com` (fintech), `zerodha.com` (Indian broker), `hubspot.com` (SaaS CRM), `bluetokaicoffee.com` (D2C coffee brand), `python.org` (non-profit / open source).

| Model | Success | Median latency | Max latency | Avg input tok | Avg output tok (incl. thinking) | Avg cost |
|---|---|---|---|---|---|---|
| **gemini-3.1-flash-lite** | **4/5** | **15.7s** | 43.0s | 7,153 | 4,918 | **$0.0092** |
| gemini-3.5-flash-lite | 4/5 | 44.7s | 110.7s | 7,153 | 2,636 | $0.0087 |
| gemini-3.8-flash | 0/5 | – | – | – | – | – |

All failures were **provider timeouts or 503 "high demand" responses**. There were **zero JSON or schema-validation failures** across every completed call. In production the fallback model absorbs these timeouts: the same request retries on the other model.

Additional single-call measurements (before the 2-call split):

| Model | Thinking | One combined call, stripe.com |
|---|---|---|
| gemini-3.5-flash-lite | `low` | 54.5s |
| gemini-3.5-flash-lite | `minimal` | 168.6s |
| gemini-3.1-flash-lite | `low` | 11.2s |

Live production requests: stripe.com **18.9s / $0.0112**, stripe.com (fresh) **13.3s**, zerodha.com **40.8s** (one part fell back to the second model).

### Accuracy observations [Measured, qualitative]

Competitors returned by the recommended model:

| Site | Competitors identified | Assessment |
|---|---|---|
| zerodha.com | Upstox, Groww, Angel One | ✅ Correct, India-specific discount brokers |
| hubspot.com | Salesforce, Zoho CRM, Pipedrive, ActiveCampaign | ✅ Correct CRM / marketing-automation peers |
| bluetokaicoffee.com | Sleepy Owl Coffee, Third Wave Coffee, Devans South Indian Coffee | ✅ Correct Indian specialty-coffee peers |
| python.org | Java (Oracle), Node.js, Ruby | ✅ Sensible for a programming-language foundation |
| stripe.com (live) | Razorpay, Adyen, Braintree (PayPal), Square | ✅ Picked up the India market (`stripe.com/in`) |

Other checks: the brand name and category were correct on every site; services were tagged `website` when they appeared in the page text; recommended titles and descriptions landed within or within 2 characters of the target length ranges.

---

## 4. Best model selection (B)

**Selected: `gemini-3.1-flash-lite` (primary) + `gemini-3.5-flash-lite` (fallback).**

| Criterion | Assessment |
|---|---|
| 1. Accuracy on website content | Correct brand, category, services and market-aware competitors on all 5 test sites |
| 2. Fast response | Fastest measured: median 15.7s, about 3× faster than 3.5-flash-lite on the same prompt |
| 3. Low API cost | ~$0.009 per analysis. 1,000 analyses ≈ **$9** |
| 4. Reliable structured JSON | Native schema enforcement; 0 validation failures |
| 5. Competitor and SEO insight quality | Specific, regional and non-generic (see table above) |
| 6. Large website content | 1M-class context; we send <10k tokens after cleaning |

**Fallback:** `gemini-3.5-flash-lite`. It uses the same provider, key and code path, costs about the same, and is slower but reliable. It supports Google Search grounding for verified competitors.

**Next candidate to benchmark:** `claude-haiku-5-5`. It is about 3× cheaper on paper, has a 1M context and enforces structured output. The benchmark script is model-agnostic, so it can be compared on exactly the same 5 sites once a key is available.

---

## 5. Cost optimization (C)

What is **already implemented**, roughly in order of impact:

| Technique | Effect |
|---|---|
| **HTML cleaning**: strip `script`, `style`, `svg`, `nav`, forms and hidden elements | Removes most raw-HTML tokens before the LLM sees them |
| **De-duplication** of repeated lines (menus, footers, repeated CTAs) | Typically removes a large share of the remaining text |
| **Content budget** (`CONTENT_CHAR_BUDGET=24000`, ~6k tokens), 60% homepage / 40% sub-pages | Hard ceiling on input cost, even for huge sites |
| **Only 3 high-value sub-pages** chosen by URL/link keywords (about, services, products…) | Better context without crawling the whole site |
| **Output caps** (`maxItems` on every list in the schema) | Bounds output tokens, which cost 6× more than input here |
| **Deterministic SEO audit** (title length, H1s, canonical, alt text…) computed in Python | 11 checks at **$0**, and more accurate than asking the AI |
| **24h cache + request coalescing** | Repeat URLs cost $0, and simultaneous duplicates make one call |
| **Smallest capable model** (flash-lite tier) | ~3–7× cheaper than flash or pro tiers |
| **Thinking level `low`** | Lower thinking-token spend than default levels |
| **One retry, then fallback** (never unbounded retries) | Bounded worst case: at most 4 calls per analysis |
| `store: false` | No server-side conversation storage |

Further levers, **not enabled** (trade-offs noted):

- **Context caching** of the fixed system prompt. It saves little, because the prompt is short.
- **Batch mode** for bulk or offline analyses. Roughly 50% cheaper, but asynchronous.
- **Model per task**: a nano-class model for simple extraction (brand, services) and a stronger one for competitors. That adds complexity, and the current single flash-lite model already meets quality.
- **Search grounding only when needed**: `ENABLE_SEARCH_GROUNDING=true` gives verified competitors but costs **$14 per 1,000 searches after 5,000 free per month** [Official], about +$0.03–0.07 per analysis [Estimate].

---

## 6. Final recommendation (D)

| Item | Recommendation |
|---|---|
| **Recommended provider** | Google Gemini (AI Studio API) |
| **Recommended model** | `gemini-3.1-flash-lite` |
| **Estimated input tokens** | ~7,200 per analysis [Measured average] |
| **Estimated output tokens** | ~4,900 per analysis incl. thinking [Measured average] |
| **Estimated cost per analysis** | **~$0.009** (range $0.008–0.011) [Measured] |
| **Expected response time** | 13–20s typical, median 15.7s [Measured]; peaks up to ~45s under provider load |
| **Reason** | Fastest measured model, lowest cost tier with no quality loss, strict JSON schema with zero failures, 1M-class context |
| **Fallback model** | `gemini-3.5-flash-lite` (same key, same code path) |
| **Balancing approach** | Clean and trim input aggressively. Cap output size. Split the work into 2 parallel calls for speed. Use a cheap fast model with a same-provider fallback. Do deterministic work (SEO checks) in code. Cache everything. Benchmark before switching models. |

**Monthly cost examples** [Estimate, from the measured average]:

| Analyses per month | Cost (fresh analyses) |
|---|---|
| 1,000 | ~$9 |
| 10,000 | ~$92 |
| 100,000 | ~$920 (less with caching of repeat URLs) |

---

### Reproduce the benchmark

```bash
cd apps/api
.venv/bin/python -m scripts.benchmark \
  --models gemini-3.1-flash-lite gemini-3.5-flash-lite gemini-3.8-flash \
  --out ../../docs/benchmark_results.json
```

Sources: Google AI Studio pricing and models pages (aistudio.google.com/docs/pricing, /docs/models, /docs/structured-output, /docs/google-search), OpenAI pricing (developers.openai.com/api/docs/pricing), Anthropic model table (platform.claude.com), DeepSeek pricing (api-docs.deepseek.com/quick_start/pricing). All were accessed 18 Nov 2026.

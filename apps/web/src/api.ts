export type Platform = "Google" | "Facebook" | "Instagram" | "LinkedIn" | "X";

export interface Brand {
  name: string;
  category: string;
  summary: string;
}

export interface Competitor {
  name: string;
  website: string | null;
  main_service: string;
  target_market: string;
  strengths: string[];
  weaknesses: string[];
  source: "ai_suggested" | "web_grounded";
  source_urls: string[];
}

export interface CompetitorAnalysis {
  brand_overview: string;
  business_category: string;
  products_and_services: string[];
  your_target_market: string;
  your_key_strength: string;
  competitors: Competitor[];
  strengths: string[];
  opportunities: string[];
  disclaimer: string;
}

export interface SearchQuery {
  query: string;
  platforms: Platform[];
  intent: string;
  business_relevance: string;
  target_audience: string;
}

export interface SEOIssue {
  check: string;
  status: "pass" | "warn" | "fail";
  finding: string;
  recommendation: string | null;
}

export interface SEOImprovements {
  primary_keyword: string;
  secondary_keywords: string[];
  long_tail_keywords: string[];
  business_keywords: string[];
  recommended_title: string;
  title_structure: string;
  meta_description: string;
  supporting_content: { type: string; title: string; purpose: string }[];
  current_title: string;
  current_meta_description: string;
  technical_audit: SEOIssue[];
}

export interface Service {
  name: string;
  description: string;
  target_industry: string;
  target_customer: string;
  main_benefit: string;
  source: "website" | "inferred";
}

export interface TargetAudience {
  primary_audience: string[];
  secondary_audience: string[];
  industries: string[];
  business_types: string[];
  customer_profiles: string[];
  geographic_focus: string | null;
  customer_needs: string[];
  challenges: string[];
  interests: string[];
  recommended_segments: { segment: string; business_type: string; requirement: string }[];
}

export interface AnalysisResponse {
  success: true;
  website: string;
  brand: Brand;
  analysis: {
    competitor_analysis: CompetitorAnalysis;
    target_search_queries: SearchQuery[];
    search_queries_note: { search_volume: string; reason: string };
    seo_improvements: SEOImprovements;
    top_services: Service[];
    target_audience: TargetAudience;
  };
  meta: {
    model: string;
    cached: boolean;
    latency_ms: number;
    llm_latency_ms: number;
    tokens: { input: number; output: number; thinking: number };
    estimated_cost_usd: number;
    pages_analyzed: string[];
    warnings: string[];
    analyzed_at: string;
  };
}

export interface ProgressEvent {
  stage: string;
  percent: number | null;
  message: string;
}

export class ApiError extends Error {
  constructor(
    public code: string,
    message: string,
    public requestId?: string,
    public details: Record<string, unknown> = {},
  ) {
    super(message);
  }
}

const TIMEOUT_MS = 150_000;

function toApiError(body: any, status: number): ApiError {
  const err = body?.error;
  return new ApiError(
    err?.code ?? `http_${status}`,
    err?.message ?? (status === 429 ? "Too many requests. Please wait a moment and try again." : "Something went wrong. Please try again."),
    err?.request_id,
    err?.details ?? {},
  );
}

// SSE stream padho: progress events aate rahenge, end me ek result ya error
export async function analyzeStream(
  url: string,
  signal: AbortSignal,
  onProgress: (event: ProgressEvent) => void,
): Promise<AnalysisResponse> {
  const timeout = AbortSignal.timeout(TIMEOUT_MS);
  let res: Response;
  try {
    res = await fetch("/link-analysis/stream", {
      method: "POST",
      headers: { "Content-Type": "application/json", Accept: "text/event-stream" },
      body: JSON.stringify({ url }),
      signal: AbortSignal.any([signal, timeout]),
    });
  } catch (err) {
    if (signal.aborted) throw err;
    if (timeout.aborted) throw new ApiError("client_timeout", "The analysis took too long. Please try again.");
    throw new ApiError("network_error", "Could not reach the server. Check your internet connection.");
  }

  if (!res.ok || !res.body || !res.headers.get("content-type")?.includes("text/event-stream")) {
    throw toApiError(await res.json().catch(() => null), res.status);
  }

  const reader = res.body.pipeThrough(new TextDecoderStream()).getReader();
  let buffer = "";
  try {
    for (;;) {
      const { value, done } = await reader.read();
      if (done) break;
      buffer += value;
      let split: number;
      while ((split = buffer.indexOf("\n\n")) !== -1) {
        const block = buffer.slice(0, split);
        buffer = buffer.slice(split + 2);
        let event = "message";
        let data = "";
        for (const line of block.split("\n")) {
          if (line.startsWith("event: ")) event = line.slice(7);
          else if (line.startsWith("data: ")) data += line.slice(6);
        }
        if (!data) continue;
        const payload = JSON.parse(data);
        if (event === "progress") onProgress(payload as ProgressEvent);
        else if (event === "result") return payload as AnalysisResponse;
        else if (event === "error") throw toApiError(payload, 500);
      }
    }
  } catch (err) {
    if (err instanceof ApiError || signal.aborted) throw err;
    if (timeout.aborted) throw new ApiError("client_timeout", "The analysis took too long. Please try again.");
    throw new ApiError("network_error", "The connection was interrupted. Please try again.");
  } finally {
    reader.releaseLock();
  }
  throw new ApiError("network_error", "The connection was interrupted. Please try again.");
}

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Platform = Literal["Google", "Facebook", "Instagram", "LinkedIn", "X"]
ContentType = Literal["service_page", "industry_page", "faq", "blog_topic", "location_page", "article", "case_study"]


class LinkAnalysisRequest(BaseModel):
    model_config = ConfigDict(json_schema_extra={"examples": [{"url": "https://stripe.com"}]})

    url: str = Field(min_length=1, max_length=2048, description="Website address to analyze")


# ---- LLM output contract (Gemini ko yahi schema bheja jata hai) ----


class Brand(BaseModel):
    name: str
    category: str = Field(description="Main business category")
    summary: str = Field(description="1-2 sentence plain-language business summary")


class Competitor(BaseModel):
    name: str
    website: str | None = Field(default=None, description="Homepage URL if confidently known, else null")
    main_service: str
    target_market: str
    strengths: list[str] = Field(max_length=3)
    weaknesses: list[str] = Field(max_length=3, description="Gaps or weaknesses relative to the analyzed brand")


class CompetitorAnalysis(BaseModel):
    brand_overview: str
    business_category: str
    products_and_services: list[str] = Field(max_length=8)
    your_target_market: str
    your_key_strength: str
    competitors: list[Competitor] = Field(max_length=5)
    strengths: list[str] = Field(max_length=5, description="The analyzed brand's competitive advantages")
    opportunities: list[str] = Field(max_length=5, description="Ways to improve market positioning")


class SearchQuery(BaseModel):
    query: str
    platforms: list[Platform] = Field(min_length=1, max_length=5)
    intent: str
    business_relevance: str
    target_audience: str


class SupportingContent(BaseModel):
    type: ContentType
    title: str
    purpose: str


class SEOImprovements(BaseModel):
    primary_keyword: str
    secondary_keywords: list[str] = Field(max_length=8)
    long_tail_keywords: list[str] = Field(max_length=6)
    business_keywords: list[str] = Field(max_length=8)
    recommended_title: str = Field(description="50-60 characters, primary keyword near the start")
    title_structure: str = Field(description="Pattern used, e.g. 'Primary Keyword | Benefit | Brand'")
    meta_description: str = Field(description="140-160 characters, human-friendly, includes primary keyword")
    supporting_content: list[SupportingContent] = Field(max_length=6)


class Service(BaseModel):
    name: str
    description: str
    target_industry: str
    target_customer: str
    main_benefit: str
    source: Literal["website", "inferred"] = Field(
        description="'website' if stated on the site, 'inferred' if it is a recommendation"
    )


class AudienceSegment(BaseModel):
    segment: str
    business_type: str
    requirement: str


class TargetAudience(BaseModel):
    primary_audience: list[str] = Field(max_length=5)
    secondary_audience: list[str] = Field(max_length=5)
    industries: list[str] = Field(max_length=5)
    business_types: list[str] = Field(max_length=5)
    customer_profiles: list[str] = Field(max_length=5)
    geographic_focus: str | None = Field(description="Location focus if evident from the site, else null")
    customer_needs: list[str] = Field(max_length=5)
    challenges: list[str] = Field(max_length=5)
    interests: list[str] = Field(max_length=5)
    recommended_segments: list[AudienceSegment] = Field(max_length=6)


class MarketAnalysis(BaseModel):
    brand: Brand
    competitor_analysis: CompetitorAnalysis
    target_search_queries: list[SearchQuery] = Field(min_length=5, max_length=5)


class SiteAnalysis(BaseModel):
    seo_improvements: SEOImprovements
    top_services: list[Service] = Field(min_length=1, max_length=5)
    target_audience: TargetAudience


class LLMAnalysis(BaseModel):
    brand: Brand
    competitor_analysis: CompetitorAnalysis
    target_search_queries: list[SearchQuery] = Field(min_length=5, max_length=5)
    seo_improvements: SEOImprovements
    top_services: list[Service] = Field(min_length=1, max_length=5)
    target_audience: TargetAudience


# ---- API response ----


class CompetitorOut(Competitor):
    source: Literal["ai_suggested", "web_grounded"]
    source_urls: list[str] = []


class CompetitorAnalysisOut(CompetitorAnalysis):
    competitors: list[CompetitorOut]
    disclaimer: str


class SEOIssue(BaseModel):
    check: str
    status: Literal["pass", "warn", "fail"]
    finding: str
    recommendation: str | None = None


class SEOImprovementsOut(SEOImprovements):
    current_title: str
    current_meta_description: str
    technical_audit: list[SEOIssue]


class SearchQueriesNote(BaseModel):
    search_volume: Literal["not_provided"] = "not_provided"
    reason: str = "No keyword or social search-volume data source is connected, so no volumes are reported."


class Analysis(BaseModel):
    competitor_analysis: CompetitorAnalysisOut
    target_search_queries: list[SearchQuery]
    search_queries_note: SearchQueriesNote = SearchQueriesNote()
    seo_improvements: SEOImprovementsOut
    top_services: list[Service]
    target_audience: TargetAudience


class TokenUsage(BaseModel):
    input: int = 0
    output: int = 0
    thinking: int = 0


class Meta(BaseModel):
    model: str
    cached: bool
    latency_ms: int
    llm_latency_ms: int
    tokens: TokenUsage
    estimated_cost_usd: float
    pages_analyzed: list[str]
    warnings: list[str]
    analyzed_at: datetime


class LinkAnalysisResponse(BaseModel):
    success: Literal[True] = True
    website: str
    brand: Brand
    analysis: Analysis
    meta: Meta


class ErrorBody(BaseModel):
    code: str
    message: str
    request_id: str | None = None
    details: dict | None = None


class ErrorResponse(BaseModel):
    success: Literal[False] = False
    error: ErrorBody

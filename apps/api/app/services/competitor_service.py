import re
from urllib.parse import urlsplit

from app.schemas import Competitor, CompetitorAnalysis, CompetitorAnalysisOut, CompetitorOut

AI_DISCLAIMER = (
    "Competitors are AI-generated suggestions based on the website's content and the model's general "
    "knowledge. Verify them before making business decisions."
)
GROUNDED_DISCLAIMER = (
    "Competitors were identified with live Google Search grounding; source links are attached where available. "
    "Verify them before making business decisions."
)


def refine_competitors(
    analysis: CompetitorAnalysis, brand_name: str, site_url: str, citations: list[str], grounded: bool
) -> tuple[CompetitorAnalysisOut, list[str]]:
    own_host = _host(site_url)
    own_name = _key(brand_name)
    seen: set[str] = set()
    refined: list[CompetitorOut] = []

    for comp in analysis.competitors:
        key = _key(comp.name)
        website = _clean_url(comp.website)
        # brand khud ko competitor na bataye, aur duplicate hata do
        if not key or key == own_name or key in seen or (website and _host(website) == own_host):
            continue
        seen.add(key)
        refined.append(_with_source(comp, website, citations, grounded))

    warnings = []
    if len(refined) < 3:
        warnings.append("Fewer than 3 reliable competitors could be identified for this website.")
    out = CompetitorAnalysisOut(
        **analysis.model_dump(exclude={"competitors"}),
        competitors=refined,
        disclaimer=GROUNDED_DISCLAIMER if grounded and citations else AI_DISCLAIMER,
    )
    return out, warnings


def _with_source(comp: Competitor, website: str | None, citations: list[str], grounded: bool) -> CompetitorOut:
    host, name = (_host(website) if website else ""), _key(comp.name)
    matched = [u for u in citations if (host and host in u.lower()) or (len(name) > 3 and name in _key(u))]
    source = "web_grounded" if grounded and matched else "ai_suggested"
    return CompetitorOut(
        **comp.model_dump(exclude={"website"}), website=website, source=source, source_urls=matched[:3]
    )


def _clean_url(url: str | None) -> str | None:
    if not url:
        return None
    url = url.strip()
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    host = _host(url)
    return url if host and "." in host and " " not in host else None


def _host(url: str) -> str:
    try:
        return (urlsplit(url).hostname or "").lower().removeprefix("www.")
    except ValueError:
        return ""


def _key(text: str) -> str:
    return re.sub(r"[^a-z0-9]", "", (text or "").lower())

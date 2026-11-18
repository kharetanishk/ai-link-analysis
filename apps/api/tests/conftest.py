import json
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from app.schemas import LLMAnalysis, TokenUsage
from app.services.llm_service import LLMResult

PUBLIC_IP = "93.184.216.34"
PRIVATE_HOSTS = {"internal.test": "10.0.0.5", "metadata.test": "169.254.169.254"}

HOME_HTML = """<!doctype html><html lang="en"><head>
<title>Acme Web Studio | Websites for Small Businesses</title>
<meta name="description" content="Acme builds fast, affordable websites and online stores for small businesses in Pune.">
<meta property="og:site_name" content="Acme Web Studio">
<link rel="canonical" href="https://acme.test/">
<meta name="viewport" content="width=device-width">
<script type="application/ld+json">{"@type":"LocalBusiness","name":"Acme Web Studio",
 "address":{"addressLocality":"Pune","addressCountry":"IN"}}</script>
<script>var tracking = "ignore me";</script>
</head><body>
<header><nav><a href="/about">About us</a><a href="/services">Services</a><a href="/blog/post.pdf">PDF</a>
<a href="https://other.test/services">External</a></nav></header>
<main><h1>Websites that grow small businesses</h1>
<h2>Web Development</h2><p>Custom websites built with modern frameworks for local businesses.</p>
<h2>E-commerce Stores</h2><p>Online stores with payments, inventory and shipping integrations.</p>
<p>Custom websites built with modern frameworks for local businesses.</p>
<img src="a.png"><img src="b.png" alt="Team">
</main><footer>Acme Web Studio, Baner Road, Pune, India</footer></body></html>"""

ABOUT_HTML = "<html><head><title>About Acme</title></head><body><main><p>Founded in 2015, Acme has served 300 small businesses.</p></main></body></html>"
SERVICES_HTML = "<html><head><title>Services</title></head><body><main><p>SEO, website maintenance and hosting plans for shops.</p></main></body></html>"


def sample_analysis(brand="Acme Web Studio") -> LLMAnalysis:
    service = {
        "name": "Web Development",
        "description": "Custom websites",
        "target_industry": "Retail",
        "target_customer": "Small business owners",
        "main_benefit": "More leads",
        "source": "website",
    }
    query = {
        "query": "website developer in pune",
        "platforms": ["Google"],
        "intent": "Service Search",
        "business_relevance": "Core service",
        "target_audience": "Local SMBs",
    }
    competitor = {
        "name": "Rival Studio",
        "website": "rival.test",
        "main_service": "Web design",
        "target_market": "SMBs",
        "strengths": ["Brand"],
        "weaknesses": ["Price"],
    }
    return LLMAnalysis.model_validate(
        {
            "brand": {"name": brand, "category": "Web Development", "summary": "Builds websites."},
            "competitor_analysis": {
                "brand_overview": "Acme builds websites.",
                "business_category": "Web Development",
                "products_and_services": ["Websites", "E-commerce"],
                "your_target_market": "Small businesses in Pune",
                "your_key_strength": "Affordable",
                "competitors": [
                    competitor,
                    {**competitor, "name": "rival studio"},
                    {**competitor, "name": brand, "website": "https://acme.test"},
                    {**competitor, "name": "Wix", "website": "https://wix.com"},
                    {**competitor, "name": "Squarespace", "website": None},
                ],
                "strengths": ["Local presence"],
                "opportunities": ["Publish case studies"],
            },
            "target_search_queries": [{**query, "query": f"q{i}"} for i in range(5)],
            "seo_improvements": {
                "primary_keyword": "website development pune",
                "secondary_keywords": ["web design"],
                "long_tail_keywords": ["affordable website for small business pune"],
                "business_keywords": ["ecommerce store"],
                "recommended_title": "Website Development in Pune | Acme Web Studio",
                "title_structure": "Keyword | Brand",
                "meta_description": "Acme builds fast websites.",
                "supporting_content": [{"type": "faq", "title": "Pricing FAQ", "purpose": "Answer cost questions"}],
            },
            "top_services": [service],
            "target_audience": {
                "primary_audience": ["Small businesses"],
                "secondary_audience": ["Startups"],
                "industries": ["Retail"],
                "business_types": ["Shops"],
                "customer_profiles": ["Owner-operators"],
                "geographic_focus": "Pune, India",
                "customer_needs": ["Online presence"],
                "challenges": ["Budget"],
                "interests": ["Growth"],
                "recommended_segments": [{"segment": "A", "business_type": "Retail", "requirement": "E-commerce"}],
            },
        }
    )


class FakeLLM:
    configured = True

    def __init__(self):
        self.calls = 0
        self.last_prompt = ""

    async def analyze(self, system_prompt: str, user_prompt: str, progress=None) -> LLMResult:
        self.calls += 1
        if progress:
            progress("market_ready", 65, "Competitors & search queries ready")
            progress("site_ready", 90, "SEO, services & audience ready")
        self.last_prompt = user_prompt
        return LLMResult(sample_analysis(), "fake-model", 42, TokenUsage(input=1000, output=500))

    def estimate_cost(self, usage: TokenUsage) -> float:
        return 0.0015


@pytest.fixture
def fake_dns(monkeypatch):
    async def resolve(host, port):
        return [PRIVATE_HOSTS.get(host, PUBLIC_IP)]

    monkeypatch.setattr("app.utils.validators._resolve", resolve)


@pytest.fixture
def settings():
    return Settings(_env_file=None, gemini_api_key=None, static_dir="/nonexistent", rate_limit_requests=100)


@pytest.fixture
def client(settings, fake_dns):
    app = create_app(settings)
    with TestClient(app) as c:
        fake = FakeLLM()
        app.state.llm = fake
        app.state.analysis.llm = fake
        c.fake_llm = fake
        yield c


def interaction(payload, status="completed"):
    text = payload if isinstance(payload, str) else json.dumps(payload)
    usage = SimpleNamespace(total_input_tokens=1200, total_output_tokens=800, total_thought_tokens=100)
    return SimpleNamespace(status=status, output_text=text, usage=usage, model_dump=lambda: {})

import json
from types import SimpleNamespace

import httpx
import pytest
import respx
from fastapi.testclient import TestClient

from app.config import Settings
from app.errors import LLMConfigError, LLMOutputError, LLMUnavailableError
from app.main import create_app
from app.services.competitor_service import refine_competitors
from app.services.llm_service import LLMService, response_schema
from tests.conftest import ABOUT_HTML, HOME_HTML, PUBLIC_IP, SERVICES_HTML, interaction, sample_analysis


def mock_site():
    pages = {"/": HOME_HTML, "/about": ABOUT_HTML, "/services": SERVICES_HTML}

    def handler(request):
        body = pages.get(request.url.path)
        return httpx.Response(200, headers={"content-type": "text/html"}, text=body) if body else httpx.Response(404)

    respx.route(host=PUBLIC_IP).mock(side_effect=handler)


@respx.mock
def test_link_analysis_success_and_cache(client):
    mock_site()
    response = client.post("/link-analysis", json={"url": "acme.test"})
    assert response.status_code == 200, response.text
    body = response.json()

    assert body["success"] is True
    assert body["website"] == "https://acme.test/"
    assert set(body["analysis"]) >= {
        "competitor_analysis", "target_search_queries", "seo_improvements", "top_services", "target_audience",
    }
    assert len(body["analysis"]["target_search_queries"]) == 5
    assert body["analysis"]["search_queries_note"]["search_volume"] == "not_provided"
    assert "volume" not in json.dumps(body["analysis"]["target_search_queries"]).lower()

    names = [c["name"] for c in body["analysis"]["competitor_analysis"]["competitors"]]
    assert names == ["Rival Studio", "Wix", "Squarespace"]
    assert all(c["source"] == "ai_suggested" for c in body["analysis"]["competitor_analysis"]["competitors"])

    seo = body["analysis"]["seo_improvements"]
    assert seo["current_title"].startswith("Acme Web Studio")
    assert any(i["check"] == "Image alt text" for i in seo["technical_audit"])
    assert body["meta"]["cached"] is False and body["meta"]["tokens"]["input"] == 1000
    assert response.headers["x-request-id"]

    again = client.post("/link-analysis", json={"url": "https://ACME.test"}).json()
    assert again["meta"]["cached"] is True and again["meta"]["estimated_cost_usd"] == 0
    assert client.fake_llm.calls == 1


@pytest.mark.parametrize(
    ("payload", "status", "code"),
    [
        ({}, 422, "invalid_request"),
        ({"url": ""}, 422, "invalid_request"),
        ({"url": 123}, 422, "invalid_request"),
        ({"url": "ftp://acme.test"}, 422, "invalid_url"),
        ({"url": "http://127.0.0.1"}, 400, "blocked_url"),
        ({"url": "http://internal.test"}, 400, "blocked_url"),
        ({"url": "https://metadata.test/latest"}, 400, "blocked_url"),
    ],
)
def test_bad_input(client, payload, status, code):
    response = client.post("/link-analysis", json=payload)
    assert response.status_code == status
    assert response.json()["success"] is False
    assert response.json()["error"]["code"] == code


def test_malformed_json(client):
    response = client.post("/link-analysis", content=b"{not json", headers={"content-type": "application/json"})
    assert response.status_code == 422 and response.json()["error"]["code"] == "invalid_request"


@respx.mock
def test_site_down_returns_502(client):
    respx.route(host=PUBLIC_IP).mock(side_effect=httpx.ConnectError("refused"))
    response = client.post("/link-analysis", json={"url": "https://acme.test"})
    assert response.status_code == 502 and response.json()["error"]["code"] == "site_unreachable"


@respx.mock
def test_llm_not_configured(settings, fake_dns):
    mock_site()
    with TestClient(create_app(settings)) as c:
        response = c.post("/link-analysis", json={"url": "https://acme.test"})
    assert response.status_code == 503 and response.json()["error"]["code"] == "llm_not_configured"


def test_rate_limit(fake_dns):
    s = Settings(_env_file=None, static_dir="/nonexistent", rate_limit_requests=2)
    with TestClient(create_app(s)) as c:
        codes = [c.post("/link-analysis", json={"url": "http://127.0.0.1"}).status_code for _ in range(3)]
        last = c.post("/link-analysis", json={"url": "http://127.0.0.1"})
    assert codes == [400, 400, 429]
    assert last.headers["retry-after"]


def test_health_and_docs(client):
    assert client.get("/health").json()["status"] == "ok"
    assert client.get("/docs").status_code == 200
    assert "/link-analysis" in client.get("/openapi.json").json()["paths"]


def test_refine_competitors_grounded_sources():
    analysis = sample_analysis().competitor_analysis
    out, warnings = refine_competitors(
        analysis, "Acme Web Studio", "https://acme.test/", ["https://www.wix.com/about"], grounded=True
    )
    by_name = {c.name: c for c in out.competitors}
    assert by_name["Wix"].source == "web_grounded" and by_name["Wix"].source_urls == ["https://www.wix.com/about"]
    assert by_name["Rival Studio"].website == "https://rival.test"
    assert by_name["Squarespace"].source == "ai_suggested"
    assert warnings == []


def test_schema_is_flat():
    assert "$ref" not in json.dumps(response_schema())
    assert "$defs" not in response_schema()


class FakeInteractions:
    def __init__(self, results):
        self.results = list(results)
        self.models = []

    async def create(self, **body):
        self.models.append(body["model"])
        result = self.results.pop(0)
        if isinstance(result, Exception):
            raise result
        return result


def llm_with(results, **overrides):
    service = LLMService(Settings(_env_file=None, gemini_api_key="test", gemini_model="primary",
                                  gemini_fallback_model="backup", **overrides))
    fake = FakeInteractions(results)
    service._client = SimpleNamespace(aio=SimpleNamespace(interactions=fake))
    return service, fake


async def test_llm_retries_invalid_json_then_succeeds():
    good = interaction(sample_analysis().model_dump())
    service, fake = llm_with([interaction("{broken"), good])
    result = await service.analyze("sys", "user")
    assert fake.models == ["primary", "primary"]
    assert result.usage.input == 1200 and result.usage.thinking == 100


async def test_llm_falls_back_on_api_error():
    error = type("RateLimitError", (Exception,), {"status_code": 429})("quota")
    service, fake = llm_with([error, interaction(sample_analysis().model_dump())])
    result = await service.analyze("sys", "user")
    assert fake.models == ["primary", "backup"] and result.model == "backup"


async def test_llm_all_fail():
    error = type("ServerError", (Exception,), {"status_code": 500})("down")
    service, _ = llm_with([error, error])
    with pytest.raises(LLMUnavailableError):
        await service.analyze("sys", "user")


async def test_llm_bad_output_everywhere():
    service, fake = llm_with([interaction('{"x":1}')] * 4)
    with pytest.raises(LLMOutputError):
        await service.analyze("sys", "user")
    assert len(fake.models) == 4


async def test_llm_auth_error_is_not_retried():
    error = type("AuthenticationError", (Exception,), {"status_code": 401})("bad key")
    service, fake = llm_with([error])
    with pytest.raises(LLMConfigError):
        await service.analyze("sys", "user")
    assert fake.models == ["primary"]


async def test_llm_sends_grounding_tool_when_enabled():
    service, _ = llm_with([], enable_search_grounding=True)
    captured = {}

    async def create(**body):
        captured.update(body)
        return interaction(sample_analysis().model_dump())

    service._client.aio.interactions.create = create
    await service.analyze("sys", "user")
    assert captured["tools"] == [{"type": "google_search"}]
    assert captured["response_format"]["mime_type"] == "application/json"
    assert captured["store"] is False


def test_cost_estimate():
    service = LLMService(Settings(_env_file=None, price_input_per_million=0.30, price_output_per_million=2.50))
    from app.schemas import TokenUsage

    assert service.estimate_cost(TokenUsage(input=1_000_000, output=100_000, thinking=100_000)) == 0.8

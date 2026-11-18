import httpx
import pytest
import respx

from app.config import Settings
from app.errors import (
    BlockedURLError,
    InsufficientContentError,
    SiteBlockedError,
    SiteTimeoutError,
    SiteUnreachableError,
    UnsupportedContentError,
)
from app.services.analysis_service import build_prompt, seo_audit
from app.services.website_extractor import WebsiteExtractor
from tests.conftest import ABOUT_HTML, HOME_HTML, PUBLIC_IP, SERVICES_HTML

pytestmark = pytest.mark.usefixtures("fake_dns")


def site(routes: dict):
    """routes: {(host, path): httpx.Response}"""

    def handler(request: httpx.Request):
        key = (request.headers["host"], request.url.path)
        return routes.get(key, httpx.Response(404))

    return handler


@pytest.fixture
async def extractor():
    async with httpx.AsyncClient(follow_redirects=False) as client:
        yield WebsiteExtractor(client, Settings(_env_file=None, fetch_max_bytes=50_000))


def html(body, **kw):
    return httpx.Response(200, headers={"content-type": "text/html; charset=utf-8"}, text=body, **kw)


@respx.mock
async def test_extracts_full_site(extractor):
    route = respx.route(host=PUBLIC_IP).mock(
        side_effect=site({
            ("acme.test", "/"): html(HOME_HTML),
            ("acme.test", "/about"): html(ABOUT_HTML),
            ("acme.test", "/services"): html(SERVICES_HTML),
        })
    )
    result = await extractor.extract("https://acme.test/")

    assert result.title.startswith("Acme Web Studio")
    assert result.organization == {"name": "Acme Web Studio", "address": "Pune, IN"}
    assert result.h1 == ["Websites that grow small businesses"]
    assert "ignore me" not in result.main_text
    assert result.main_text.count("Custom websites built") == 1
    assert {p.url for p in result.pages} == {"https://acme.test/about", "https://acme.test/services"}
    assert "Pune" in result.footer_text
    sent = route.calls[0].request
    assert sent.url.host == PUBLIC_IP and sent.headers["host"] == "acme.test"

    prompt = build_prompt(result, 24_000)
    assert "<website_content>" in prompt and "300 small businesses" in prompt
    audit = {i.check: i.status for i in seo_audit(result)}
    assert audit["Canonical URL"] == "pass" and audit["Image alt text"] == "warn"


@respx.mock
async def test_redirect_to_private_host_is_blocked(extractor):
    respx.route(host=PUBLIC_IP).mock(
        side_effect=site({("acme.test", "/"): httpx.Response(302, headers={"location": "http://internal.test/admin"})})
    )
    with pytest.raises(BlockedURLError):
        await extractor.extract("https://acme.test/")


@respx.mock
async def test_redirect_loop(extractor):
    respx.route(host=PUBLIC_IP).mock(
        side_effect=site({("acme.test", "/"): httpx.Response(301, headers={"location": "/"})})
    )
    with pytest.raises(SiteUnreachableError, match="too many"):
        await extractor.extract("https://acme.test/")


@respx.mock
async def test_follows_safe_redirect(extractor):
    respx.route(host=PUBLIC_IP).mock(
        side_effect=site({
            ("acme.test", "/"): httpx.Response(301, headers={"location": "https://www.acme.test/"}),
            ("www.acme.test", "/"): html(HOME_HTML),
        })
    )
    result = await extractor.extract("https://acme.test/")
    assert result.final_url == "https://www.acme.test/"


@pytest.mark.parametrize(
    ("response", "error"),
    [
        (httpx.Response(403), SiteBlockedError),
        (httpx.Response(429), SiteBlockedError),
        (httpx.Response(404), SiteUnreachableError),
        (httpx.Response(500), SiteUnreachableError),
        (httpx.Response(200, headers={"content-type": "application/pdf"}, content=b"%PDF-1.4"), UnsupportedContentError),
        (html("   "), InsufficientContentError),
        (html("<html><body><p>Hi</p></body></html>"), InsufficientContentError),
    ],
)
@respx.mock
async def test_error_mapping(extractor, response, error):
    respx.route(host=PUBLIC_IP).mock(return_value=response)
    with pytest.raises(error):
        await extractor.extract("https://acme.test/")


@respx.mock
async def test_timeout(extractor):
    respx.route(host=PUBLIC_IP).mock(side_effect=httpx.ReadTimeout("slow"))
    with pytest.raises(SiteTimeoutError):
        await extractor.extract("https://acme.test/")


@respx.mock
async def test_body_size_is_capped(extractor):
    huge = HOME_HTML + "<p>" + "x" * 200_000 + "</p>"
    respx.route(host=PUBLIC_IP).mock(return_value=html(huge))
    page = await extractor.fetch("https://acme.test/")
    assert len(page.html) <= 50_000


@respx.mock
async def test_js_rendered_site_warns(extractor):
    shell = ('<html><head><title>App</title><meta name="description" content="' + "A product platform. " * 10
             + '"></head><body><div id="root"></div></body></html>')
    respx.route(host=PUBLIC_IP).mock(return_value=html(shell))
    result = await extractor.extract("https://acme.test/")
    assert any("JavaScript" in w for w in result.warnings)

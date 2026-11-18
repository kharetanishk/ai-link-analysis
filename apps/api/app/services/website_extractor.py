import asyncio
import json
import logging
import re
from dataclasses import dataclass, field
from urllib.parse import urljoin, urlsplit, urlunsplit

import httpx
from bs4 import BeautifulSoup

from app.config import Settings
from app.errors import (
    AppError,
    InsufficientContentError,
    InvalidURLError,
    SiteBlockedError,
    SiteTimeoutError,
    SiteUnreachableError,
    UnsupportedContentError,
)
from app.utils.validators import SafeTarget, normalize_url, resolve_safe_target

log = logging.getLogger("app.extractor")

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/131.0 Safari/537.36 LinkAnalysisBot/1.0"
    ),
    "Accept": "text/html,application/xhtml+xml;q=0.9,*/*;q=0.5",
    "Accept-Language": "en-US,en;q=0.8",
}
HTML_TYPES = ("text/html", "application/xhtml+xml")
NOISE_TAGS = ["script", "style", "noscript", "svg", "iframe", "template", "canvas", "form", "object", "embed"]
SUBPAGE_HINTS = [
    ("about", 5),
    ("service", 5),
    ("solution", 4),
    ("product", 4),
    ("what-we-do", 4),
    ("offer", 3),
    ("pricing", 3),
    ("industr", 2),
    ("company", 2),
    ("feature", 2),
    ("who-we-are", 4),
    ("platform", 2),
]
SKIP_EXT = re.compile(r"\.(pdf|jpe?g|png|gif|webp|svg|zip|mp4|mp3|docx?|xlsx?|pptx?)$", re.I)
MIN_TEXT_CHARS = 120


@dataclass
class FetchedPage:
    url: str
    html: bytes
    charset: str | None


@dataclass
class PageContent:
    url: str
    title: str
    text: str


@dataclass
class ExtractedSite:
    requested_url: str
    final_url: str
    title: str = ""
    meta_description: str = ""
    meta_keywords: str = ""
    og: dict[str, str] = field(default_factory=dict)
    canonical: str = ""
    lang: str = ""
    h1: list[str] = field(default_factory=list)
    headings: list[str] = field(default_factory=list)
    nav_links: list[str] = field(default_factory=list)
    organization: dict = field(default_factory=dict)
    footer_text: str = ""
    main_text: str = ""
    pages: list[PageContent] = field(default_factory=list)
    seo_signals: dict = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)

    @property
    def pages_analyzed(self) -> list[str]:
        return [self.final_url, *(p.url for p in self.pages)]


class WebsiteExtractor:
    def __init__(self, client: httpx.AsyncClient, settings: Settings):
        self.client = client
        self.settings = settings

    async def extract(self, url: str) -> ExtractedSite:
        page = await self.fetch(url)
        soup = BeautifulSoup(page.html, "lxml", from_encoding=page.charset)
        site = ExtractedSite(requested_url=url, final_url=page.url)
        self._read_head(soup, site)
        site.seo_signals = self._seo_signals(soup, site)
        candidates = self._subpage_candidates(soup, page.url)
        self._read_body(soup, site)

        if self.settings.fetch_extra_pages and candidates:
            results = await asyncio.gather(
                *(self._fetch_text(u) for u in candidates[: self.settings.fetch_extra_pages]),
                return_exceptions=True,
            )
            seen = {site.final_url.rstrip("/")}
            for r in results:
                if isinstance(r, PageContent) and r.text and r.url.rstrip("/") not in seen:
                    seen.add(r.url.rstrip("/"))
                    site.pages.append(r)

        total = len(site.main_text) + sum(len(p.text) for p in site.pages) + len(site.meta_description)
        if total < MIN_TEXT_CHARS:
            raise InsufficientContentError()
        if len(site.main_text) < 400:
            site.warnings.append(
                "The homepage has very little visible text (likely rendered by JavaScript); "
                "analysis relies more on metadata and sub-pages."
            )
        return site

    async def fetch(self, url: str) -> FetchedPage:
        current = url
        for _ in range(self.settings.fetch_max_redirects + 1):
            target = await resolve_safe_target(current)
            try:
                response, body = await self._send(target)
            except httpx.TimeoutException as exc:
                raise SiteTimeoutError() from exc
            except httpx.HTTPError as exc:
                raise SiteUnreachableError(details={"reason": type(exc).__name__}) from exc

            if response.is_redirect:
                location = response.headers.get("location")
                if not location:
                    raise SiteUnreachableError("The website sent a broken redirect.")
                # har redirect hop ko dobara validate karna zaroori hai (SSRF)
                try:
                    current = normalize_url(urljoin(current, location))
                except InvalidURLError as exc:
                    raise SiteUnreachableError("The website redirected to an unsupported address.") from exc
                continue
            return self._accept(response, body, current)
        raise SiteUnreachableError("The website redirected too many times.")

    async def _send(self, target: SafeTarget) -> tuple[httpx.Response, bytes]:
        parts = urlsplit(target.url)
        ip_host = f"[{target.ip}]" if ":" in target.ip else target.ip
        # resolved IP par hi connect karo taaki DNS rebinding na ho; TLS/SNI asli host se
        pinned = urlunsplit((parts.scheme, ip_host, parts.path or "/", parts.query, ""))
        request = self.client.build_request(
            "GET",
            pinned,
            headers={**HEADERS, "Host": target.host},
            extensions={"sni_hostname": target.host},
        )
        response = await self.client.send(request, stream=True)
        try:
            if response.is_redirect or response.status_code >= 400:
                return response, b""
            chunks, size = [], 0
            async for chunk in response.aiter_bytes():
                chunks.append(chunk)
                size += len(chunk)
                if size >= self.settings.fetch_max_bytes:
                    break
            return response, b"".join(chunks)[: self.settings.fetch_max_bytes]
        finally:
            await response.aclose()

    def _accept(self, response: httpx.Response, body: bytes, url: str) -> FetchedPage:
        status = response.status_code
        if status in (401, 403, 407, 429) or (status == 503 and "cloudflare" in response.headers.get("server", "")):
            raise SiteBlockedError(details={"status": status})
        if status == 404:
            raise SiteUnreachableError("This page was not found (404).", details={"status": status})
        if status >= 400:
            raise SiteUnreachableError(details={"status": status})

        content_type = response.headers.get("content-type", "").lower()
        looks_html = b"<html" in body[:4096].lower() or body[:1024].lstrip().lower().startswith(b"<!doctype html")
        if content_type and not content_type.startswith(HTML_TYPES) and not looks_html:
            raise UnsupportedContentError(details={"content_type": content_type.split(";")[0]})
        if not body.strip():
            raise InsufficientContentError("The website returned an empty page.")
        charset = response.charset_encoding if "charset" in content_type else None
        return FetchedPage(url=url, html=body, charset=charset)

    async def _fetch_text(self, url: str) -> PageContent | None:
        try:
            page = await self.fetch(url)
        except AppError as exc:
            log.info("subpage skipped %s: %s", url, exc.code)
            return None
        soup = BeautifulSoup(page.html, "lxml", from_encoding=page.charset)
        title = _clean(soup.title.get_text()) if soup.title else ""
        _strip_noise(soup)
        for tag in soup.find_all(["nav", "header", "footer", "aside"]):
            tag.decompose()
        root = soup.find("main") or soup.body or soup
        return PageContent(url=page.url, title=title, text=_text_blocks(root))

    def _read_head(self, soup: BeautifulSoup, site: ExtractedSite) -> None:
        site.title = _clean(soup.title.get_text()) if soup.title else ""
        site.meta_description = _meta(soup, name="description")
        site.meta_keywords = _meta(soup, name="keywords")
        for key in ("og:site_name", "og:title", "og:description", "og:type", "og:locale"):
            if value := _meta(soup, prop=key):
                site.og[key] = value
        canonical = soup.find("link", rel=lambda v: v and "canonical" in v)
        site.canonical = canonical.get("href", "") if canonical else ""
        html = soup.find("html")
        site.lang = (html.get("lang") or "") if html else ""
        site.organization = _organization(soup)

    def _read_body(self, soup: BeautifulSoup, site: ExtractedSite) -> None:
        _strip_noise(soup)
        site.h1 = _unique(_clean(h.get_text(" ")) for h in soup.find_all("h1"))[:5]
        site.headings = _unique(_clean(h.get_text(" ")) for h in soup.find_all(["h2", "h3"]))[:40]
        nav_texts = []
        for nav in soup.find_all(["nav", "header"]):
            nav_texts += [_clean(a.get_text(" ")) for a in nav.find_all("a")]
        site.nav_links = [t for t in _unique(nav_texts) if 1 < len(t) < 40][:30]
        footer = soup.find("footer")
        site.footer_text = _text_blocks(footer)[:800] if footer else ""
        for tag in soup.find_all(["nav", "header", "footer", "aside"]):
            tag.decompose()
        root = soup.find("main") or soup.body or soup
        site.main_text = _text_blocks(root)

    def _seo_signals(self, soup: BeautifulSoup, site: ExtractedSite) -> dict:
        images = soup.find_all("img")
        robots = _meta(soup, name="robots").lower()
        return {
            "title_length": len(site.title),
            "meta_description_length": len(site.meta_description),
            "h1_count": len(soup.find_all("h1")),
            "has_canonical": bool(site.canonical),
            "has_lang": bool(site.lang),
            "has_viewport": bool(soup.find("meta", attrs={"name": "viewport"})),
            "has_open_graph": bool(site.og),
            "has_structured_data": bool(soup.find("script", type="application/ld+json")),
            "images_total": len(images),
            "images_missing_alt": sum(1 for i in images if not (i.get("alt") or "").strip()),
            "noindex": "noindex" in robots,
            "https": site.final_url.startswith("https://"),
        }

    def _subpage_candidates(self, soup: BeautifulSoup, base_url: str) -> list[str]:
        base_host = _bare_host(urlsplit(base_url).hostname or "")
        scored: dict[str, int] = {}
        for a in soup.find_all("a", href=True):
            href = a["href"].strip()
            if href.startswith(("#", "mailto:", "tel:", "javascript:")):
                continue
            absolute = urljoin(base_url, href).split("#")[0]
            parts = urlsplit(absolute)
            if _bare_host(parts.hostname or "") != base_host or SKIP_EXT.search(parts.path):
                continue
            if parts.path.rstrip("/") in ("", urlsplit(base_url).path.rstrip("/")):
                continue
            haystack = f"{parts.path} {a.get_text(' ')}".lower()
            score = max((w for hint, w in SUBPAGE_HINTS if hint in haystack), default=0)
            if score:
                try:
                    key = normalize_url(urlunsplit((parts.scheme, parts.netloc, parts.path.rstrip("/") or "/", "", "")))
                except AppError:
                    continue
                scored[key] = max(scored.get(key, 0), score - parts.path.count("/"))
        return sorted(scored, key=scored.get, reverse=True)


def _strip_noise(soup: BeautifulSoup) -> None:
    for tag in soup.find_all(NOISE_TAGS):
        tag.decompose()
    for tag in soup.find_all(attrs={"aria-hidden": "true"}):
        tag.decompose()


def _text_blocks(root) -> str:
    lines = (_clean(line) for line in root.get_text("\n").split("\n"))
    return "\n".join(line for line in _unique(lines) if len(line) > 2)


def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def _unique(items) -> list[str]:
    seen, out = set(), []
    for item in items:
        key = item.lower()
        if item and key not in seen:
            seen.add(key)
            out.append(item)
    return out


def _meta(soup: BeautifulSoup, name: str | None = None, prop: str | None = None) -> str:
    tag = soup.find("meta", attrs={"name": re.compile(f"^{name}$", re.I)} if name else {"property": prop})
    return _clean(tag.get("content", "")) if tag else ""


def _bare_host(host: str) -> str:
    return host.lower().removeprefix("www.")


def _organization(soup: BeautifulSoup) -> dict:
    wanted = {"Organization", "Corporation", "LocalBusiness", "ProfessionalService", "Store", "WebSite", "Brand"}
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(script.string or "")
        except (json.JSONDecodeError, TypeError):
            continue
        nodes = data if isinstance(data, list) else data.get("@graph", [data]) if isinstance(data, dict) else []
        for node in nodes:
            if not isinstance(node, dict):
                continue
            types = node.get("@type")
            types = set(types) if isinstance(types, list) else {types}
            if types & wanted or any(str(t).endswith("Business") for t in types):
                address = node.get("address")
                if isinstance(address, dict):
                    address = ", ".join(
                        str(address[k])
                        for k in ("addressLocality", "addressRegion", "addressCountry")
                        if address.get(k) and isinstance(address[k], str)
                    )
                return {
                    k: v
                    for k, v in {
                        "name": node.get("name"),
                        "description": node.get("description"),
                        "address": address if isinstance(address, str) else None,
                        "area_served": node.get("areaServed") if isinstance(node.get("areaServed"), str) else None,
                    }.items()
                    if v
                }
    return {}

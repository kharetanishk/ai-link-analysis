import pytest

from app.errors import BlockedURLError, InvalidURLError
from app.utils import validators
from app.utils.validators import is_public_ip, normalize_url, resolve_safe_target


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("example.com", "https://example.com/"),
        ("  HTTPS://Example.COM/path?q=1#frag ", "https://example.com/path?q=1"),
        ("http://example.com:80/a", "http://example.com/a"),
        ("https://bücher.de", "https://xn--bcher-kva.de/"),
        ("https://example.com.", "https://example.com/"),
    ],
)
def test_normalize_url(raw, expected):
    assert normalize_url(raw) == expected


@pytest.mark.parametrize(
    "raw",
    [
        "",
        "   ",
        "not a url",
        "ftp://example.com",
        "javascript:alert(1)",
        "https://user:pw@example.com",
        "https://intranet",
        "https://" + "a" * 2050 + ".com",
        "http://[::1",
    ],
)
def test_normalize_rejects_invalid(raw):
    with pytest.raises(InvalidURLError):
        normalize_url(raw)


@pytest.mark.parametrize(
    "raw",
    [
        "localhost",
        "http://localhost:80",
        "https://db.internal",
        "https://printer.local",
        "https://example.com:8080",
        "http://example.com:22",
    ],
)
def test_normalize_blocks_internal_and_ports(raw):
    with pytest.raises(BlockedURLError):
        normalize_url(raw)


@pytest.mark.parametrize(
    ("ip", "public"),
    [
        ("8.8.8.8", True),
        ("2606:4700:4700::1111", True),
        ("127.0.0.1", False),
        ("10.1.2.3", False),
        ("172.16.0.1", False),
        ("192.168.1.1", False),
        ("169.254.169.254", False),
        ("100.64.0.1", False),
        ("0.0.0.0", False),
        ("224.0.0.1", False),
        ("::1", False),
        ("fc00::1", False),
        ("fe80::1", False),
        ("::ffff:127.0.0.1", False),
        ("::ffff:10.0.0.1", False),
    ],
)
def test_is_public_ip(ip, public):
    assert is_public_ip(ip) is public


async def test_resolve_blocks_private_literal():
    with pytest.raises(BlockedURLError):
        await resolve_safe_target("http://169.254.169.254/latest/meta-data")


async def test_resolve_blocks_if_any_record_private(monkeypatch):
    async def mixed(host, port):
        return ["93.184.216.34", "10.0.0.1"]

    monkeypatch.setattr(validators, "_resolve", mixed)
    with pytest.raises(BlockedURLError):
        await resolve_safe_target("https://rebind.example.com/")


async def test_resolve_returns_pinned_target(monkeypatch):
    async def public(host, port):
        return ["93.184.216.34"]

    monkeypatch.setattr(validators, "_resolve", public)
    target = await resolve_safe_target("https://example.com/")
    assert (target.host, target.ip, target.port) == ("example.com", "93.184.216.34", 443)

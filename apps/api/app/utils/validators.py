import asyncio
import ipaddress
import socket
from dataclasses import dataclass
from urllib.parse import urlsplit, urlunsplit

from app.errors import BlockedURLError, InvalidURLError

ALLOWED_SCHEMES = {"http", "https"}
DEFAULT_PORTS = {"http": 80, "https": 443}
MAX_URL_LENGTH = 2048
BLOCKED_HOST_SUFFIXES = (".local", ".localhost", ".internal", ".lan", ".home", ".corp", ".intranet")


@dataclass(frozen=True)
class SafeTarget:
    url: str
    host: str
    ip: str
    port: int
    scheme: str


def normalize_url(raw: str) -> str:
    value = (raw or "").strip()
    if not value or len(value) > MAX_URL_LENGTH or any(c.isspace() for c in value):
        raise InvalidURLError()
    # user ne "example.com" likha ho to https maan lo
    if "://" not in value:
        value = "https://" + value.lstrip("/")
    try:
        parts = urlsplit(value)
        port = parts.port
    except ValueError as exc:
        raise InvalidURLError() from exc

    scheme = parts.scheme.lower()
    if scheme not in ALLOWED_SCHEMES:
        raise InvalidURLError("Only http:// and https:// links are supported.")
    if parts.username or parts.password:
        raise InvalidURLError("Links with embedded usernames or passwords are not allowed.")
    host = (parts.hostname or "").rstrip(".")
    if not host:
        raise InvalidURLError()
    try:
        host = host.encode("idna").decode("ascii").lower()
    except UnicodeError as exc:
        raise InvalidURLError() from exc
    if port not in (None, DEFAULT_PORTS[scheme]):
        raise BlockedURLError("Only standard web ports (80 and 443) are allowed.")
    if host == "localhost" or host.endswith(BLOCKED_HOST_SUFFIXES):
        raise BlockedURLError()
    if not _is_ip_literal(host) and "." not in host:
        raise InvalidURLError("Please enter a full domain name, for example example.com")

    netloc = f"[{host}]" if ":" in host else host
    return urlunsplit((scheme, netloc, parts.path or "/", parts.query, ""))


def is_public_ip(ip: str) -> bool:
    addr = ipaddress.ip_address(ip)
    if isinstance(addr, ipaddress.IPv6Address) and addr.ipv4_mapped:
        addr = addr.ipv4_mapped
    return addr.is_global and not addr.is_multicast


async def resolve_safe_target(url: str) -> SafeTarget:
    parts = urlsplit(url)
    host = (parts.hostname or "").lower()
    scheme = parts.scheme.lower()
    port = parts.port or DEFAULT_PORTS.get(scheme, 0)
    if scheme not in ALLOWED_SCHEMES or port != DEFAULT_PORTS[scheme] or parts.username or parts.password:
        raise BlockedURLError()
    if host == "localhost" or host.endswith(BLOCKED_HOST_SUFFIXES):
        raise BlockedURLError()

    if _is_ip_literal(host):
        ips = [host]
    else:
        try:
            ips = await _resolve(host, port)
        except (socket.gaierror, UnicodeError) as exc:
            raise InvalidURLError("This domain does not exist or cannot be resolved.") from exc

    # ek bhi private IP mila to poora host block, DNS tricks se bachne ke liye
    if not ips or not all(is_public_ip(ip) for ip in ips):
        raise BlockedURLError()
    return SafeTarget(url=url, host=host, ip=ips[0], port=port, scheme=scheme)


async def _resolve(host: str, port: int) -> list[str]:
    infos = await asyncio.get_running_loop().getaddrinfo(host, port, type=socket.SOCK_STREAM)
    return list(dict.fromkeys(info[4][0].split("%")[0] for info in infos))


def _is_ip_literal(host: str) -> bool:
    try:
        ipaddress.ip_address(host)
        return True
    except ValueError:
        return False

import asyncio
import hashlib
import io
import ipaddress
import re
import socket
from urllib.parse import urlparse, urlunparse
import httpx
from bs4 import BeautifulSoup
from pypdf import PdfReader
from app.schemas.domain import Source
from app.services.errors import ServiceError

MANUFACTURERS = {
    "lenovo.com": "Lenovo",
    "kingston.com": "Kingston",
    "crucial.com": "Crucial",
    "micron.com": "Micron",
    "dell.com": "Dell",
    "hp.com": "HP",
    "asus.com": "ASUS",
    "acer.com": "Acer",
    "framework.com": "Framework",
    "frame.work": "Framework",
    "corsair.com": "Corsair",
    "samsung.com": "Samsung",
    "msi.com": "MSI",
    "gskill.com": "G.Skill",
    "teamgroupinc.com": "TeamGroup",
}
MAX_BYTES = 8_000_000


def normalize_url(url: str) -> str:
    parsed = urlparse(url)
    if parsed.scheme not in ("https", "http") or not parsed.hostname or parsed.username or parsed.password:
        raise ServiceError("source_url", "This source URL is not supported.")
    if parsed.port not in (None, 80, 443):
        raise ServiceError("source_url", "This source uses an unsupported port.")
    return urlunparse(parsed._replace(fragment=""))


def manufacturer_for(url: str) -> str | None:
    host = (urlparse(url).hostname or "").lower()
    return next(
        (brand for domain, brand in MANUFACTURERS.items() if host == domain or host.endswith("." + domain)),
        None,
    )


def source_from_result(result: dict, search_id=None) -> Source | None:
    try:
        url = normalize_url(result.get("link", ""))
    except (ServiceError, ValueError):
        return None
    brand = manufacturer_for(url)
    return Source(
        url=url,
        title=str(result.get("title") or url)[:300],
        publisher=brand or (urlparse(url).hostname or ""),
        source_type="manufacturer" if brand else "search_result",
        search_id=search_id,
    )


def extract_text(content: bytes, content_type: str) -> str:
    if "pdf" in content_type or content.startswith(b"%PDF"):
        reader = PdfReader(io.BytesIO(content))
        if len(reader.pages) > 160:
            raise ServiceError("document_size", "This document is too large for the investigation.")
        text = "\n".join((page.extract_text() or "") for page in reader.pages)
    else:
        soup = BeautifulSoup(content, "html.parser")
        for tag in soup(["script", "style", "nav", "footer", "noscript"]):
            tag.decompose()
        text = soup.get_text(" ", strip=True)
    return re.sub(r"\s+", " ", text).strip()[:250_000]


async def public_manufacturer_url(url: str):
    normalize_url(url)
    if not manufacturer_for(url):
        raise ServiceError(
            "source_policy", "Automatic document retrieval is limited to recognized manufacturers."
        )
    host = urlparse(url).hostname
    try:
        addresses = await asyncio.to_thread(socket.getaddrinfo, host, None, type=socket.SOCK_STREAM)
    except OSError:
        raise ServiceError("source_unavailable", "The manufacturer source could not be reached.") from None
    if not addresses or any(not ipaddress.ip_address(item[4][0]).is_global for item in addresses):
        raise ServiceError("source_policy", "This source address is not allowed.")


async def fetch_source(source: Source) -> Source:
    current = source.url
    try:
        async with httpx.AsyncClient(timeout=25, follow_redirects=False, trust_env=False) as client:
            for _ in range(4):
                await public_manufacturer_url(current)
                async with client.stream(
                    "GET", current, headers={"User-Agent": "FitProof/0.1 (evidence research)"}
                ) as response:
                    if response.is_redirect:
                        location = response.headers.get("location")
                        if not location:
                            break
                        current = str(response.url.join(location))
                        continue
                    if response.status_code != 200:
                        raise ServiceError("source_unavailable", "The manufacturer document is unavailable.")
                    chunks = []
                    size = 0
                    async for chunk in response.aiter_bytes():
                        size += len(chunk)
                        if size > MAX_BYTES:
                            raise ServiceError("document_size", "This document exceeds the download limit.")
                        chunks.append(chunk)
                    text = await asyncio.to_thread(
                        extract_text, b"".join(chunks), response.headers.get("content-type", "")
                    )
                    if len(text) < 30:
                        raise ServiceError("source_empty", "No readable specification text was available.")
                    source.url = current
                    source.text = text
                    source.content_hash = hashlib.sha256(text.encode()).hexdigest()
                    return source
        raise ServiceError("source_redirect", "The source has too many redirects.")
    except (httpx.HTTPError, ServiceError, ValueError, OSError):
        source.fetch_status = "unavailable"
        source.text = ""
        return source

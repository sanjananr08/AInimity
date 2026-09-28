"""Evidence ingestion for debate runs.

This module deliberately supports explicit user-provided URLs/text instead of
silently scraping arbitrary hosts. It validates URLs, blocks private/local
network targets, limits redirects and response size, and returns provenance
for every extracted source so the Validator can cite or reject it.
"""
from __future__ import annotations

import hashlib
import html
import ipaddress
import re
import socket
from html.parser import HTMLParser
from urllib.parse import urljoin, urlparse

import httpx


MAX_URLS = 8
MAX_SOURCE_BYTES = 1_000_000
MAX_EXTRACTED_CHARS = 8_000
TIMEOUT = httpx.Timeout(8.0, connect=3.0)


class EvidenceError(ValueError):
    pass


class _TextExtractor(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.title_parts: list[str] = []
        self.text_parts: list[str] = []
        self._skip = 0
        self._in_title = False

    def handle_starttag(self, tag, attrs):
        tag = tag.lower()
        if tag in {"script", "style", "noscript", "svg"}:
            self._skip += 1
        if tag == "title":
            self._in_title = True

    def handle_endtag(self, tag):
        tag = tag.lower()
        if tag in {"script", "style", "noscript", "svg"} and self._skip:
            self._skip -= 1
        if tag == "title":
            self._in_title = False

    def handle_data(self, data):
        if self._skip:
            return
        clean = re.sub(r"\s+", " ", data).strip()
        if not clean:
            return
        if self._in_title:
            self.title_parts.append(clean)
        else:
            self.text_parts.append(clean)


def _host_is_public(host: str) -> bool:
    try:
        addresses = {item[4][0] for item in socket.getaddrinfo(host, None)}
    except socket.gaierror as exc:
        raise EvidenceError("The evidence host could not be resolved.") from exc
    for address in addresses:
        ip = ipaddress.ip_address(address)
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast:
            return False
    return True


def validate_url(url: str) -> str:
    value = (url or "").strip()
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise EvidenceError("Evidence URLs must use http or https.")
    if parsed.username or parsed.password:
        raise EvidenceError("Evidence URLs may not contain embedded credentials.")
    if not _host_is_public(parsed.hostname):
        raise EvidenceError("Private, local, and link-local evidence hosts are blocked.")
    return value


def _extract_response(response: httpx.Response, url: str) -> dict:
    content_type = response.headers.get("content-type", "").lower()
    if "text/html" not in content_type and "text/plain" not in content_type:
        raise EvidenceError("Only HTML and plain-text evidence sources are supported.")
    body = response.content[:MAX_SOURCE_BYTES]
    if len(response.content) > MAX_SOURCE_BYTES:
        raise EvidenceError("Evidence source exceeds the 1 MB safety limit.")
    if "text/html" in content_type:
        parser = _TextExtractor()
        parser.feed(body.decode(response.encoding or "utf-8", errors="replace"))
        title = " ".join(parser.title_parts)[:240] or urlparse(url).netloc
        text = " ".join(parser.text_parts)
    else:
        title = urlparse(url).netloc
        text = body.decode("utf-8", errors="replace")
    text = re.sub(r"\s+", " ", html.unescape(text)).strip()[:MAX_EXTRACTED_CHARS]
    if len(text) < 40:
        raise EvidenceError("Evidence source did not contain enough readable text.")
    return {
        "source_id": "src_" + hashlib.sha256(url.encode()).hexdigest()[:12],
        "url": url,
        "title": title,
        "snippet": text,
        "content_sha256": hashlib.sha256(body).hexdigest(),
        "retrieved_at": response.headers.get("date", "") or None,
        "status": "retrieved",
    }


def retrieve_urls(urls: list[str]) -> list[dict]:
    results: list[dict] = []
    for raw_url in urls[:MAX_URLS]:
        try:
            url = validate_url(raw_url)
            with httpx.Client(timeout=TIMEOUT, follow_redirects=False, headers={"User-Agent": "AInimityEvidence/1.0"}) as client:
                current = url
                for _ in range(3):
                    response = client.get(current)
                    if response.is_redirect:
                        location = response.headers.get("location")
                        if not location:
                            raise EvidenceError("Evidence redirect had no destination.")
                        current = validate_url(urljoin(current, location))
                        continue
                    response.raise_for_status()
                    results.append(_extract_response(response, current))
                    break
                else:
                    raise EvidenceError("Evidence source redirected too many times.")
        except Exception as exc:
            results.append({
                "source_id": "src_" + hashlib.sha256(raw_url.encode()).hexdigest()[:12],
                "url": raw_url,
                "title": "Unavailable source",
                "snippet": "",
                "content_sha256": None,
                "retrieved_at": None,
                "status": "error",
                "error": str(exc)[:240],
            })
    return results


def build_evidence_context(sources: list[dict], pasted_text: str = "") -> str:
    blocks = []
    for source in sources:
        if source.get("status") != "retrieved":
            continue
        blocks.append(f"[{source['source_id']}] {source['title']} ({source['url']})\n{source['snippet']}")
    if pasted_text.strip():
        blocks.append("[user_note] " + pasted_text.strip()[:12000])
    return "\n\n".join(blocks) or "No external evidence was supplied. Do not invent citations."

# app/fetcher.py
import asyncio, httpx
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                   "AppleWebKit/537.36 (KHTML, like Gecko) "
                   "Chrome/124.0.0.0 Safari/537.36"),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "es-AR,es;q=0.9,en;q=0.8",
    "Cache-Control": "no-cache",
}
TIMEOUT = httpx.Timeout(connect=10.0, read=20.0, write=10.0, pool=5.0)
SEM = asyncio.Semaphore(4)  # limita concurrencia

def _clean_html(html: str) -> str:
    soup = BeautifulSoup(html, "lxml")
    for tag in soup(["script", "style", "noscript"]): tag.decompose()
    return soup.get_text("\n", strip=True)

async def _get_html(url: str, client: httpx.AsyncClient):
    r = await client.get(url, headers=HEADERS, follow_redirects=True)
    r.raise_for_status()
    if "text/html" not in r.headers.get("content-type", ""):
        raise RuntimeError(f"content-type no soportado: {r.headers.get('content-type')}")
    return r.text

async def fetch_text(url: str, client: httpx.AsyncClient):
    try:
        html = await _get_html(url, client)
        return {"url": url, "ok": True, "text": _clean_html(html), "error": None}
    except Exception as e:
        # Fallback lector público (convierte la página en texto plano)
        try:
            r = await client.get(f"https://r.jina.ai/http://{url}", timeout=TIMEOUT)
            r.raise_for_status()
            return {"url": url, "ok": True, "text": r.text, "error": f"fallback: {e}"}
        except Exception as e2:
            return {"url": url, "ok": False, "text": "", "error": f"{e} | fallback: {e2}"}

async def fetch_many(urls: list[str]):
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        async def worker(u: str):
            async with SEM:
                return await fetch_text(u, client)
        return await asyncio.gather(*(worker(u) for u in urls))

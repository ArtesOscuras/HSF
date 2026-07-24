import re
import html2text
import requests
import urllib3
from html.parser import HTMLParser

from src.llm.mcp import call as _mcp_call

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


MAX_RESPONSE_SIZE = 5 * 1024 * 1024
DEFAULT_TIMEOUT = 30

_EXA_MCP = "https://mcp.exa.ai/mcp"
_EXA_TOOL = "web_search_exa"

_CHROME_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/143.0.0.0 Safari/537.36"
)
_HSF_UA = "opencode/HSF"

_DDG_URL = "https://lite.duckduckgo.com/lite/"


class _TextExtractor(HTMLParser):
    def __init__(self):
        super().__init__()
        self._text = []
        self._skip = 0
        self._skip_tags = {"script", "style", "noscript", "iframe", "object", "embed"}

    def handle_starttag(self, tag, attrs):
        if self._skip > 0 or tag in self._skip_tags:
            self._skip += 1

    def handle_endtag(self, tag):
        if self._skip > 0:
            self._skip -= 1

    def handle_data(self, data):
        if self._skip == 0:
            self._text.append(data)

    def get_text(self):
        return " ".join(self._text).strip()


def _extract_text(html):
    parser = _TextExtractor()
    parser.feed(html)
    return parser.get_text()


def _html_to_markdown(html):
    h = html2text.HTML2Text()
    h.ignore_links = False
    h.ignore_images = True
    h.body_width = 0
    return h.handle(html)


_SKIP_TAGS = {"nav", "footer", "aside", "script", "style", "noscript", "iframe", "object", "embed"}
_SKIP_CLASSES = {"cookie", "cookies", "consent", "gdpr", "banner", "popup", "sidebar", "cookie-banner", "cookie-consent", "cookie-notice"}


class _HTMLCleaner(HTMLParser):
    def __init__(self):
        super().__init__()
        self._out = []
        self._skip_depth = 0

    def handle_starttag(self, tag, attrs):
        if self._skip_depth > 0:
            self._skip_depth += 1
            return
        if tag in _SKIP_TAGS:
            self._skip_depth = 1
            return
        cls = dict(attrs).get("class", "").lower()
        if cls:
            for sc in _SKIP_CLASSES:
                if sc in cls:
                    self._skip_depth = 1
                    return
        if dict(attrs).get("id", "").lower() in {"sidebar", "cookie-banner", "cookie-consent"}:
            self._skip_depth = 1
            return
        if attrs:
            attr_str = "".join(f' {k}="{v}"' for k, v in attrs)
            self._out.append(f"<{tag}{attr_str}>")
        else:
            self._out.append(f"<{tag}>")

    def handle_endtag(self, tag):
        if self._skip_depth > 0:
            self._skip_depth -= 1
            return
        self._out.append(f"</{tag}>")

    def handle_data(self, data):
        if self._skip_depth > 0:
            return
        self._out.append(data)

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)

    def handle_entityref(self, name):
        if self._skip_depth > 0:
            return
        self._out.append(f"&{name};")

    def handle_charref(self, name):
        if self._skip_depth > 0:
            return
        self._out.append(f"&#{name};")

    def get_html(self):
        return "".join(self._out)


def _strip_html_non_content(html):
    parser = _HTMLCleaner()
    parser.feed(html)
    parser.close()
    return parser.get_html()


def _fetch_raw(url, timeout):
    headers = {"User-Agent": _CHROME_UA}
    resp = requests.get(url, headers=headers, timeout=timeout, stream=True, verify=False)
    if resp.status_code == 403 and resp.headers.get("cf-mitigated") == "challenge":
        resp.close()
        headers = {"User-Agent": _HSF_UA}
        resp = requests.get(url, headers=headers, timeout=timeout, stream=True, verify=False)

    content_type = resp.headers.get("content-type", "").lower()
    _text_types = ("text/", "application/json", "application/xml",
                   "application/javascript", "application/xhtml+xml",
                   "application/ld+json", "application/rss+xml",
                   "application/atom+xml")
    if not any(content_type.startswith(t) for t in _text_types):
        resp.close()
        return f"[non-text content skipped: {content_type}]", content_type

    chunks = []
    total = 0
    for chunk in resp.iter_content(chunk_size=8192):
        if chunk:
            total += len(chunk)
            if total > MAX_RESPONSE_SIZE:
                resp.close()
                raise RuntimeError(f"Response too large (exceeds {MAX_RESPONSE_SIZE // (1024*1024)}MB limit)")
            chunks.append(chunk)
    resp.close()
    body = b"".join(chunks)
    try:
        text = body.decode("utf-8")
    except UnicodeDecodeError:
        text = body.decode("latin-1", errors="replace")
    return text, content_type


def fetch_url(url, format="markdown", timeout=DEFAULT_TIMEOUT, offset=1, limit=None):
    if not url.startswith("http://") and not url.startswith("https://"):
        url = "https://" + url

    try:
        content, content_type = _fetch_raw(url, timeout)
    except Exception as e:
        return f"Error fetching URL: {e}"

    is_html = "text/html" in content_type or "<html" in content[:200].lower()

    if format == "text":
        if is_html:
            content = _strip_html_non_content(content)
            content = _extract_text(content)
    elif format == "markdown":
        if is_html:
            content = _strip_html_non_content(content)
            content = _html_to_markdown(content)
    else:
        pass

    if offset > 1 or limit is not None:
        lines = content.splitlines(keepends=True)
        total = len(lines)
        start = max(0, offset - 1)
        end = start + limit if limit else total
        sliced = lines[start:end]
        shown = len(sliced)
        shown_end = offset + shown - 1 if shown > 0 else offset
        header = f"[{total} lines total, showing lines {offset}-{shown_end}]"
        return header + "\n" + "".join(sliced)

    return content


def web_search(query, num_results=10):
    result = _exa_search(query, num_results)
    if result is not None:
        return result
    import time
    html = _ddg_search(query)
    if html is None:
        return f"Search failed for '{query}'. Try again later."
    results = _parse_ddg_results(html, num_results)
    if not results:
        return f"No results found for '{query}'."
    lines = [f"Web search results for '{query}':"]
    for i, r in enumerate(results, 1):
        lines.append(f"\n{i}. {r['title']}")
        if r.get("snippet"):
            lines.append(f"   {r['snippet']}")
        lines.append(f"   {r['url']}")
    return "\n".join(lines)


def _parse_exa_results(text):
    results = []
    for block in text.split("\n---"):
        block = block.strip()
        if not block:
            continue
        title = ""
        url = ""
        snippet_parts = []
        in_highlights = False
        for line in block.split("\n"):
            stripped = line.strip()
            if stripped.startswith("Title:"):
                title = stripped[6:].strip()
            elif stripped.startswith("URL:"):
                url = stripped[4:].strip()
            elif stripped.startswith("Published:") or stripped.startswith("Author:"):
                continue
            elif stripped.startswith("Highlights:"):
                in_highlights = True
            elif in_highlights:
                hl = stripped
                if hl.startswith(">"):
                    hl = hl[1:].strip()
                if hl == "...":
                    continue
                if hl:
                    snippet_parts.append(hl)
        if not title or not url:
            continue
        snippet = " ".join(snippet_parts[:3])
        snippet = snippet.replace("--", " ").replace("#", " ")
        if snippet.lower().startswith(title.lower()):
            snippet = snippet[len(title):].strip()
        snippet = " ".join(snippet.split())[:150].strip()
        results.append({"title": title, "url": url, "snippet": snippet})
    return results


def _exa_search(query, num_results):
    text = _mcp_call(_EXA_MCP, _EXA_TOOL, {
        "query": query,
        "type": "auto",
        "numResults": num_results,
        "livecrawl": "fallback",
    })
    if not text:
        return None
    results = _parse_exa_results(text)
    if not results:
        return None
    lines = [f"Web search results for '{query}':\n"]
    for i, r in enumerate(results, 1):
        if r["snippet"]:
            lines.append(f"{i}. {r['title']}\n   {r['snippet']}\n   {r['url']}\n")
        else:
            lines.append(f"{i}. {r['title']}\n   {r['url']}\n")
            lines.append(f"\n{i}. {r['title']}\n   {r['url']}")
    return "\n".join(lines)


def _ddg_search(query, retries=2):
    import time
    user_agents = [
        _CHROME_UA,
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36",
        _HSF_UA,
    ]
    for attempt in range(retries):
        ua = user_agents[attempt % len(user_agents)]
        try:
            resp = requests.post(
                _DDG_URL,
                data={"q": query},
                headers={
                    "User-Agent": ua,
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                    "Accept-Language": "en-US,en;q=0.5",
                },
                timeout=15,
            )
        except Exception:
            if attempt < retries - 1:
                time.sleep(2)
            continue
        if resp.status_code in (200, 202) and hasattr(resp, "text"):
            html = resp.text
            if '<a rel="nofollow"' in html or "result-link" in html or "result-snippet" in html:
                return html
            if '<td class="result-snippet"' in html or '<td class=\'result-snippet\'>' in html:
                return html
            if resp.status_code == 202 and "anomaly-modal" in html:
                if attempt < retries - 1:
                    time.sleep(3)
                    continue
        if attempt < retries - 1:
            time.sleep(2)
    return None


def _parse_ddg_results(html, max_results):
    results = []
    links = re.findall(
        r'''<a[^>]*rel=["']nofollow["'][^>]*href=["'](https?://[^"']+)["'][^>]*>(.*?)</a>''',
        html,
        re.DOTALL,
    )
    snippets = re.findall(
        r"""<td class=["']result-snippet["']>(.*?)</td>""",
        html,
        re.DOTALL,
    )

    for i, (url, title) in enumerate(links):
        if len(results) >= max_results:
            break
        title = re.sub(r"<[^>]+>", "", title).strip()
        snippet = ""
        if i < len(snippets):
            snippet = re.sub(r"<[^>]+>", "", snippets[i]).strip()
        results.append({"title": title, "url": url, "snippet": snippet})

    return results

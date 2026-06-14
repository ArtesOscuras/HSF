import json
import os
from datetime import datetime


def _ensure_dir(target_dir):
    os.makedirs(target_dir, exist_ok=True)


def save_session_meta(target_dir, target, browser):
    _ensure_dir(target_dir)
    meta = {
        "target": target,
        "browser": browser,
        "started_at": datetime.now().isoformat(),
        "request_count": 0,
    }
    with open(os.path.join(target_dir, "session.json"), "w") as f:
        json.dump(meta, f, indent=2)
    return meta


def update_session_count(target_dir, count):
    path = os.path.join(target_dir, "session.json")
    if os.path.isfile(path):
        with open(path) as f:
            meta = json.load(f)
        meta["request_count"] = count
        meta["ended_at"] = datetime.now().isoformat()
        with open(path, "w") as f:
            json.dump(meta, f, indent=2)


def save_request(target_dir, index, req_data, resp_data, body):
    _ensure_dir(target_dir)
    method = req_data.get("method", "GET")
    path_part = req_data.get("url", "").rstrip("/").rsplit("/", 1)[-1] or "root"
    safe_path = "".join(c if c.isalnum() or c in "._-" else "_" for c in path_part)[:40]
    name = f"{index:04d}_{method}_{safe_path}"

    req_dir = os.path.join(target_dir, name)
    _ensure_dir(req_dir)

    with open(os.path.join(req_dir, "request.json"), "w") as f:
        json.dump(req_data, f, indent=2)
    with open(os.path.join(req_dir, "response.json"), "w") as f:
        json.dump(resp_data, f, indent=2)

    if body:
        body_path = os.path.join(req_dir, "body.html")
        try:
            with open(body_path, "wb") as f:
                f.write(body if isinstance(body, bytes) else body.encode(errors="replace"))
        except Exception:
            pass


_LLM_GUIDE = """# For LLM Analysis — How This Evidence Was Recorded

## Recording Method

This evidence was captured using the **Chrome DevTools Protocol (CDP)** via
the HSF WebRecorder tool. The recorder launches a Chromium-based browser with
the `--remote-debugging-port` flag and connects to it over a WebSocket
connection. All network traffic is intercepted at the browser level — meaning
every HTTP request and response, including headers, cookies, request bodies,
and response bodies, is captured before it leaves the browser.

This is **not** a network-level packet capture (pcap). It is a browser-level
recording that gives the same visibility that the browser's own DevTools
Network tab provides.

## How the Recorder Captures Traffic (Code Fragment)

The recorder subscribes to CDP network events. Each request goes through
this lifecycle:

```python
# 1. Request is about to be sent
if method == "Network.requestWillBeSent":
    req = params.get("request", {})
    requests[req_id] = {
        "url":    req.get("url", ""),
        "method": req.get("method", "GET"),
        "headers": dict(req.get("headers", {})),
        "postData": req.get("postData", ""),   # form or JSON body
        "cookies": [],
    }

# 2. Extra request info arrives (cookies sent)
elif method == "Network.requestWillBeSentExtraInfo":
    headers = dict(params.get("headers", {}))
    requests[req_id]["cookies"] = parse_cookies(headers["Cookie"])

# 3. Response received (status, headers, SSL certificate info)
elif method == "Network.responseReceived":
    resp = params.get("response", {})
    requests[req_id]["status"] = resp.get("status", 0)
    requests[req_id]["respHeaders"] = dict(resp.get("headers", {}))
    requests[req_id]["mimeType"] = resp.get("mimeType", "")

# 4. Response finished loading -> fetch full response body and save to disk
elif method == "Network.loadingFinished":
    body = cdp.call("Network.getResponseBody", {"requestId": req_id})
    save_request(tdir, index,
        {"url": r["url"], "method": r["method"],
         "headers": r["headers"], "postData": r["postData"],
         "cookies": r["cookies"]},
        {"status": r["status"], "headers": r["respHeaders"],
         "mimeType": r["mimeType"], "cookies": r["respCookies"]},
        body)
```

Each request is saved to a subdirectory containing:
- `request.json`  — method, URL, headers, postData, cookies
- `response.json` — status code, response headers, MIME type
- `body.html`     — full response body (truncated at 50KB in the viewer)

The session metadata is stored in `session.json`.

## Purpose of This Recording

This evidence was recorded for **software fingerprinting and vulnerability
assessment**. Your task is to analyze the captured HTTP traffic and identify
the following:

### Server Software — Confirmed vs Probable

**Confirmed** means the software is explicitly stated in a response header
(e.g. `Server: Apache/2.4.58`).

**Probable** means there is indirect evidence such as URL patterns, file
extensions, cookie naming conventions, HTML structure, POST data transmitted,
suggesting specific Ruby libraries, or for example an Active Directory software
running in backend, or JavaScript artifacts that strongly suggest a particular
technology. Examples:

- URLs ending in `.php` → PHP backend (probable)
- Cookie named `JSESSIONID` → Java/Tomcat (probable)
- Directory listing format matching Apache → Apache (probable)
- `/wp-content/` paths → WordPress (probable)
- GraphQL endpoint `/graphql` → GraphQL API (probable)

### Reporting Format

Please structure your findings as follows:

```
## Software Identification

### Confirmed
| Software | Version | Evidence |
|---|---|---|
| Apache httpd | 2.4.58 | Server header |
| Python | 3.8.5 | X-Powered-By / Werkzeug |

### Probable
| Software | Confidence | Evidence |
|---|---|---|
| Flask | High | Werkzeug server + Python + session cookie format |
| Bootstrap 5 | High | CSS class names + CDN URL |
| SQLite | Medium | Lightweight app, no heavy DB headers |
```

### Vulnerability Assessment

Based on the identified software versions and configurations, identify:

1. Known web vulnerabilities and misconfigurations that are probable
2. Sensitive data exposure
3. Insecure cookie settings
4. Outdated libraries
5. Any other relevant security-related information


### Evidence Directory Structure

```
{evidence_name}/
├── session.json                    # Recording metadata (target, browser, timestamps)
├── 0001_GET_root/                  # Each HTTP request is a subdirectory
│   ├── request.json                #   Request data (method, URL, headers, postData, cookies)
│   ├── response.json               #   Response data (status, headers, cookies)
│   └── body.html                   #   Full response body
├── 0002_POST_login/
│   └── ...
└── ...
```
"""


def save_llm_guide(target_dir):
    _ensure_dir(target_dir)
    path = os.path.join(target_dir, "For LLM analisis.md")
    with open(path, "w") as f:
        f.write(_LLM_GUIDE)


def sanitize_name(target):
    return "".join(c if c.isalnum() or c in "._-" else "_" for c in target)


def target_dir(target):
    base = os.path.join(os.path.dirname(__file__), "..", "..", "..", "evidence")
    base = os.path.abspath(base)
    return os.path.join(base, sanitize_name(target))

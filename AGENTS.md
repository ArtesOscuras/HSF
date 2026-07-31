# AGENTS.md

# HSF (Hack Station Framework)

## Project Overview

HSF (Hack Station Framework) is a Python-based penetration testing platform that provides both a command-line interface and a graphical user interface within the same application.

The application is intended to assist security professionals during assessments by combining interactive workflows, evidence collection, and structured data visualization.

The project must remain maintainable, portable, and suitable for installation through `pipx`.

---

## Core Principles

* Prioritize simplicity and maintainability.
* Minimize external dependencies whenever possible.
* Avoid introducing heavy frameworks unless there is a clear and justified benefit.
* Preserve backward compatibility unless explicitly instructed otherwise.
* Favor explicit, readable code over clever implementations.
* Keep the project compatible with Python 3.11 or newer.

---

## Architecture Overview

The application consists of two major UI areas:

### Lower Section: Interactive Console

The bottom portion of the interface contains an interactive console.

This console allows users to operate HSF through command-line interactions while the graphical interface remains active.

Features implemented for the GUI should not break console-based workflows, and vice versa.

---

### Upper Section: Views

The upper portion of the interface displays graphical views.

These views present information that HSF has collected and stored in its databases during operation.

Views should primarily act as visual representations of persisted data rather than independent sources of truth.

---

### Navigation Bar

The navigation bar is implemented in:

```
src/gui/views/nav.py
```

It is located at the top of the views section.

When modifying navigation behavior:

* Preserve consistency across all views.
* Avoid introducing view-specific hacks.
* Keep navigation logic centralized whenever possible.

---

### Mouse and Clickable Elements

HSF uses a **hover-only** interaction model. The mouse cursor never changes (`cursor` is always the system default, never `"hand2"`). Clickability is communicated through visual hover effects:

**Clickable text** (nav links, machine names, domain links, hash types, etc.):
- Normal state: no underline, `fg="#ffffff"` (bright) or `fg="#888888"` (muted)
- Hover state: **underline** + slightly lighter color
- Pattern: `<Enter>` sets `font=(..., "underline")`, `<Leave>` restores

```python
btn.bind("<Enter>", lambda e: btn.config(font=fonts.view_font_bold_under(11)))
btn.bind("<Leave>", lambda e: btn.config(font=fonts.view_font_bold(11)))
```

**Buttons** (clickable Labels styled as buttons):
- Normal state: `bg="#222222"`
- Hover state: `bg="#333333"` (subtle lightening)
- Pattern: `<Enter>` sets `bg="#333333"`, `<Leave>` restores `bg="#222222"`

```python
btn.bind("<Enter>", lambda e: btn.config(bg="#333333"))
btn.bind("<Leave>", lambda e: btn.config(bg="#222222"))
```

**Rules:**
- Never set `cursor="hand2"` or any custom cursor.
- Do not change font weight on hover (bold stays bold, regular stays regular).
- For underlined hover on bold text, use `view_font_bold_under(size)` which preserves `"bold"` weight while adding underline.
- All text widgets (non-clickable) set `cursor=""` explicitly to prevent I-beam on disabled widgets.

---

### Event Bus (`src/event_bus.py`)

The event bus decouples background threads (scanner, tools) from the GUI main thread.

* Background threads call `event_bus.submit({"type": "...", ...})` without touching tkinter.
* The `EventAggregator` drains events from a thread-safe queue and delivers them to the main thread in batches via `root.after()`.
* Default flush interval: 300ms (configurable). If the queue fills, flushes every 10ms with a max of 15 events per batch to prevent Tcl bridge saturation.
* All GUI callbacks (`_process_scanner_events`) run exclusively in the main thread.

Future tools (hydra, hashcat) should follow the same pattern: submit events to the bus, never call `after()` or touch tkinter from worker threads/processes.

---

### Named Fonts and Zoom (`src/gui/fonts.py`)

The application uses **named tkinter fonts** for all view components. This enables live zoom via named font reconfiguration — when `fonts.set_view_scale(factor)` is called, ALL widgets using `view_font(N)` or `view_font_bold(N)` update their font size instantly without requiring widget re-creation.

Key functions:

* `view_font(size)` / `view_font_bold(size)` — return named `tkinter.font.Font` objects.
* `view_font_under(size)` / `view_font_bold_under(size)` — underlined variants for hover effects.
* `set_view_scale(factor)` — reconfigures all named fonts. Clamped to [0.5, 4.0].
* `set_root(root)` — must be called once after `tk.Tk()` is created, before any view is instantiated.

When adding new views, **always use `view_font` / `view_font_bold` instead of raw font tuples**. This ensures the view responds to zoom without additional work.

---

### GUI Layout Stability on macOS Aqua

Tkinter on macOS Aqua has a known issue where `Label` widgets created before their parent window is fully mapped cache incorrect font metrics. This causes navigation bars, view titles, and other `Label`-based components to render with compressed or incorrect sizing. The layout corrects itself only when an explicit widget reconfiguration (e.g., font change on hover) triggers a full re-measurement.

**Symptoms:**

* Navigation bar buttons appear compressed (too close together) and spread apart only when the mouse hovers over them.
* View titles appear clipped or truncated.
* The problem occurs on every application startup and every GUI resize.
* Switching away from the window and back (alt+tab) temporarily fixes the layout, as does pressing Tab or clicking a nav button.

**Root Cause:**

All views are constructed during `_register_views()` (called from `App.__init__`). At construction time, each view calls `_build_ui()` which creates its widget tree — including the nav bar and title labels — but the view has not yet been gridded into the visualizer. The parent widget width is 1 pixel.

`tk.Label` (and the underlying Tcl `label` widget) calculates its preferred size using CoreText font metrics. On macOS, these metrics may be computed differently when the parent is unmapped or has a degenerate width. The cached preferred size persists even after the view is later gridded at its real width, because `Label` does not re-measure unless explicitly reconfigured (e.g., via `config(font=...)`).

When the user hovers over a nav button, the `<Enter>` handler calls `btn.config(font=hover_font)`, which triggers a full re-measurement of the Label. The new preferred size is correct (computed against the now-mapped parent), and the `pack` layout manager recalculates positions. This is why the layout "fixes itself" on hover.

After `set_initial_zoom()` (which calls `fonts.set_view_scale()`), all named fonts are reconfigured with new sizes. This triggers a resize of all Labels using those fonts, but the Labels again use potentially-stale metrics from before the view was properly mapped.

**Solution (implemented in `src/gui/visualizer.py`):**

After every view activation (`activate_view()`), and after the initial zoom configuration in `App.__init__`, force all `Label` widgets in the active view to re-measure by calling a recursive `_refresh_labels()` helper, then process pending geometry with `update_idletasks()`.

```python
# visualizer.py - activate_view()
self._active_view.grid(row=0, column=0, sticky="nsew")
self._active_view.on_activate()
self.winfo_toplevel().update_idletasks()
self._active_view.update_idletasks()
self._refresh_labels(self._active_view)
self.winfo_toplevel().update_idletasks()
```

```python
# visualizer.py - _refresh_labels (static method)
@staticmethod
def _refresh_labels(widget):
    if isinstance(widget, tk.Label):
        try:
            f = widget.cget("font")
            if f:
                widget.config(font=f)  # idempotent, forces re-measurement
        except Exception:
            pass
    for child in widget.winfo_children():
        Visualizer._refresh_labels(child)
```

The same `_refresh_labels()` call is made in `App.__init__` after `set_initial_zoom()` to handle the startup zoom configuration:

```python
# app.py - after set_initial_zoom()
self.visualizer.winfo_toplevel().update_idletasks()
self.visualizer._refresh_labels(self.visualizer.get_active_view())
self.visualizer.winfo_toplevel().update_idletasks()
```

**Rules for future development:**

* Do NOT modify the navigation bar layout from `pack` to `grid` or vice versa — the original `pack`-based centering with expandable springs is correct and must be preserved.
* Do NOT add `<Configure>` event handlers to nav bar frames as a workaround — these fire unpredictably on macOS and cause multiple redundant layout passes.
* When adding new views with `Label`-based components (titles, nav bars, headers), the `_refresh_labels` mechanism in `activate_view()` handles them automatically — no per-view workaround is needed.
* If a new view is constructed AFTER the initial `activate_view("tools")` call (e.g., lazy-created detail views), it will be built when the visualizer is already mapped, so its Labels will have correct metrics from the start. Only views created during startup registration are affected.

---

### Modal Dialogs and Cross-Platform `grab_set()`

When opening a `tk.Toplevel` dialog that uses `grab_set()` (modal behavior), always call `self.wait_visibility()` before `self.grab_set()`. Without this, Linux X11/Wayland window managers may not have finished mapping the window, causing `tkinter.TclError: grab failed: window not viewable`.

**Correct pattern:**

```python
self.transient(parent)
self.wait_visibility()   # must precede grab_set on Linux
self.grab_set()
```

This pattern is already used in `HashcatDialog`, `InitDialog`, `_CredentialGenerator`, `SettingsDialog`, `_AddUserDialog`, `_AddPersonDialog`, `_UserEditDialog`, `_PersonEditDialog`, and others. New dialogs must follow it.

---

### Path Centralization (`src/hsf_paths.py`)

All filesystem paths are defined in a single module. Never use `os.path.dirname(__file__)` to locate resources.

* **Package data** (bundled with pipx): `fonts_dir()`, `icons_dir()`, `hashcat_db()`, `logs_dir()`
* **Runtime data** (user's home): `databases_dir()`, `credentials_dir()`, `evidence_dir()`, `chrome_profile_dir()`, `lst_dir()`, `settings_file()`
* Runtime directories are created lazily with `os.makedirs(exist_ok=True)`.
* Override runtime root via `HSF_HOME` environment variable.

---

## Database and Data Representation

The application stores operational data that is later displayed by the views.

General rules:

* Persist information before presenting it in the GUI.
* Treat databases as the canonical source of application state.
* Avoid duplicating state unnecessarily.
* Ensure database interactions are explicit and easy to trace.

---

## Settings Persistence (`src/settings.py`)

User preferences (console font size, view zoom level) are persisted to `~/.local/share/hsf/settings.json`.

* `load()` / `save()` — read/write JSON with thread-safe I/O.
* `get(key, default)` / `set(key, value)` — access in-memory dict, thread-safe.
* Settings are loaded once at startup (`App.__init__`) and saved on every font/zoom change and on graceful shutdown (`_on_close`).

---

## Debugging Logs

The following location is reserved for debugging purposes:

```
src/logs/debugging_logs
```

Multiple modules define a `_dbg()` helper that writes timestamped lines to this file. The `_dbg()` implementations silently ignore `PermissionError` and `OSError` — in a pipx installation, the log file at `site-packages/src/logs/` will be non-writable, and logging is automatically suppressed.

Guidelines:

* Use debugging logs only when they provide meaningful diagnostic value.
* Avoid excessive logging.
* Ensure sensitive information is not unnecessarily recorded.
* Temporary debugging mechanisms should be removable once issues are resolved.
* In development, logs go to `src/logs/debugging_logs`. In production (pipx), they fail silently.

---

## Fonts

HSF must not depend on fonts provided by the operating system.

The application uses its own bundled fonts located at:

```
src/fonts/
```

Requirements:

* Always use the bundled fonts.
* Do not rely on platform-specific font availability.
* Maintain a consistent appearance across operating systems.

---

## Packaging and Distribution

HSF is intended to be installed using:

```
pipx
```

Requirements:

* The application must function correctly when installed through pipx.
* Avoid assumptions about editable installations.
* Ensure packaged resources are correctly included.
* Verify that non-code assets remain accessible after installation.

---

## Python Compatibility

Target environment:

* Python 3.11 or newer.
* Tcl/Tk 8.6 or newer (included with Python).

Requirements:

* Do not introduce features that require versions older than 3.11.
* Do not rely on unreleased Python functionality.
* Maintain compatibility across supported Python versions.

---

## Dependency Policy

Dependencies must be kept to an absolute minimum.

Before adding a dependency:

1. Determine whether the functionality can be implemented using the Python standard library.
2. Evaluate the maintenance and portability costs.
3. Justify why the dependency is necessary.
4. **Test the dependency in the pipx environment** — some libraries (e.g., `python-nmap`) use `subprocess` with `shell=True` which triggers `fork()` on macOS and corrupts the CoreFoundation event loop used by Tk Aqua, causing 3-6 second GUI freezes.

Avoid introducing large dependency trees.

---

## External Binary Dependencies

HSF may rely on external security tools that are expected to exist on the host system.

Examples include:

* `nmap`
* `hashcat`

Guidelines:

* Detect the presence of required binaries gracefully.
* Provide clear error messages when binaries are unavailable.
* Do not bundle these binaries.
* Do not assume fixed installation paths.
* Support standard discovery mechanisms (e.g., PATH resolution).

---

## Evidence Collection

HSF includes mechanisms for recording and preserving evidence generated during assessments.

Evidence is stored under:

```
~/.local/share/hsf/evidence/
```

Purpose:

* Preserve artifacts generated during operations.
* Support later analysis by Large Language Models (LLMs).
* Maintain a reproducible assessment trail.

Guidelines:

* Store evidence in a structured and consistent manner.
* Prefer machine-readable formats when practical.
* Avoid modifying existing evidence unless explicitly required.
* Preserve timestamps and contextual metadata whenever possible.

---

### LLM Integration (`src/llm/`)

HSF integrates with LLMs via an extensible provider system supporting any OpenAI-compatible API (OpenAI, Anthropic, DeepSeek, Ollama, OpenRouter, etc.).

**Architecture:**

* `config.py` — Persists provider configs to `~/.local/share/hsf/llm.json`. Per-provider `base_url`, `api_key`, `models`. Active model is per-provider (`active_models` dict, not global — avoids cross-provider model confusion). System prompts stored in `prompts` dict (deep-merged from defaults on load).
* `client.py` — `LLMClient` wraps `openai.OpenAI`. `chat()` / `chat_stream()`. Prepends purpose-specific system prompt unless messages already contain a `system` role. Timeout: 300s.
* `settings.py` — Settings dialog: **Models** tab (provider cards, click to edit/set active) + **Prompts** tab (editable system prompts per purpose).

**Console integration:**

* `consultor` — enters LLM mode (prompt changes to yellow `Consultor>`). All input sent to LLM. Full conversation history maintained. `exit` leaves mode. Responses stream line-by-line.
* `consultor <prompt>` — one-shot query without entering mode.
* `settings` — opens LLM configuration dialog.

**Evidence analysis:**

* `_ModelAnalysisDialog` — opens from any evidence detail view. Reads all files from the evidence directory as context. Sends to LLM with the `evidence_analysis` system prompt. Chat input below output for follow-up questions (accumulated conversation history).

**Rules:**

* All LLM calls run in daemon threads. Output dispatched to main thread via `self.after(0, ...)`.
* The `openai` library is used for all providers by setting a custom `base_url`.
* System prompts are configurable per purpose (`consultor`, `evidence_analysis`, `agent`).

### Agent Tool-Calling (`src/llm/client.py` → `chat_with_tools()`)

The agent mode gives the LLM the ability to call **57 tools** that read and modify application state and trigger network operations. It is activated via the `agent` console command or `agent <one-shot prompt>`.

**Tool-calling loop**:
...

The tool-calling phase does **not** stream — only the final assistant response is streamed.

**Method signature:**

```python
def chat_with_tools(self, messages, on_tool=None, model=None, tool_context=None, on_text=None, stop_event=None, on_warning=None):
```

- `on_tool(name, args, result)` — callback invoked after each tool execution (used for console logging).
- `on_text(text)` — callback invoked when the model emits text alongside tool calls.
- `stop_event` — `threading.Event` to cancel tool-calling loop cleanly.
- `on_warning(msg)` — callback invoked when the model outputs invalid XML tool call syntax (corrected via system message injection).
- `tool_context` — passed through to tool handlers. In agent mode this is the `App` instance.

### Tool Definitions (`src/llm/tools.py`)

Tools are defined as a list of OpenAI function-calling schemas in the `TOOLS` variable. Each entry follows the `{"type": "function", "function": {...}}` format with `name`, `description`, and `parameters` (JSON Schema).

**57 tools** in seven categories:

**Data tools** (23) — query and manipulate inventory, no `tool_context` needed:

**Query tools:**

| Tool | Description |
|---|---|
| `check_status` | Get current HSF state summary: all machine IPs with hostname, domain, device type, and port counts; all domain names; plus counts of users, credentials, passwords, hashes, evidence sessions, shell sessions |
| `check_machine` | Get all known info about a machine (IP, hostname, IPv6, MAC, model, device type, OS, domain, timestamps, ports, banners, web services, users) |
| `check_domain` | Get all known info about a domain (subdomains, directories, web services, machines) |
| `check_inventory` | Get full inventory: users, credentials, passwords, hashes, people, tickets, dictionaries, rules |
| `check_hash` | List all hashes (truncated). With `hash_id`: return full hash value and details |
| `check_shells` | List all shell sessions with ID, type, status, active flag, IP, ports, OS, timestamps |
| `check_evidences` | List evidence sessions with metadata, filenames, request directories (no file contents) |
| `check_fuzz_results` | Retrieve fuzz results for a machine: saved directories and subdomains discovered via fuzzing. Uses offset/limit pagination (default: 60 entries per section). |

**Mutation tools:**

| Tool | Description |
|---|---|
| `add_user` | Add a user to inventory (`username`, `utype`, `machine`, `domain`, `origin`) |
| `delete_user` | Delete a user by username |
| `add_machine` | Add a machine (IP) to network inventory |
| `add_domain` | Add a domain to inventory |
| `add_subdomain` | Add a subdomain to an existing domain (`domain`, `subdomain`) |
| `add_credential` | Add credential (username + password or 32-char NT hash). Auto-detects NT hash vs plaintext; computes NTLM hash for plaintext passwords |
| `add_hash` | Add hash entry to inventory (`hash_type`, `hash_value`, `hascat_mode` optional) |
| `delete_hash` | Delete hash by ID |
| `add_password` | Add password to inventory |
| `delete_credential` | Delete credential by username |
| `delete_machine` | Delete machine by IP or ID |
| `delete_domain` | Delete domain by name |
| `delete_password` | Delete password from inventory |
| `add_person` | Add a person to the people inventory (`first_name`, `last_name`, `company`, `domain`, `username`, `role`, `linkedin_url`, `source`, `interests`) |
| `delete_person` | Delete a person by ID |

**Network tools** (10) — trigger operations, require `tool_context` (App instance):

| Tool | Description |
|---|---|
| `list_interfaces` | List available network interfaces (skips `lo0`) |
| `scan_interface` | Scan local network on an interface (`iface`). Long-running async — results arrive via event bus |
| `scan_ip` | Scan a specific IP for OS/device identification. Synchronous — returns result directly |
| `stop_scan` | Stop the active network scan |
| `port_scan` | Scan TCP or UDP ports on an IP (method: "tcp" or "udp"). Returns common ports immediately; full 65535 scan continues in background (results via `check_machine`) |
| `ping` | Ping an IP address. Synchronous — returns time + TTL directly |
| `nslookup` | DNS lookup on a hostname. Synchronous — returns resolved addresses directly |
| `port_inspector` | Inspect a TCP port by sending service-specific probes. Synchronous — returns identified service banners directly |
| `bannergrab` | Open a raw TCP connection to an IP:port and wait up to 2s for a banner/response. Synchronous — returns received data directly |
| `nmap` | Run custom nmap scan with arbitrary arguments against a target. Returns raw output and auto-saves open ports to machine inventory. |

**Web tools** (3) — fetch URLs, search the web, and browse GitHub repos, no `tool_context` needed:

| Tool | Description |
|---|---|
| `webfetch` | Fetch a URL as markdown or raw (`url`, optional `format`, `method`, `body`, `content_type`, `headers`). Default GET; use POST only when submitting data with explicit content_type. Use headers for custom HTTP headers (Cookie, Authorization, etc.). Ignores self-signed TLS certificates. Markdown auto-strips navigation, footers, and cookie banners. Raw format returns HTTP status, all headers, and first 60 lines of untouched body (full body saved to cache). Auto-saves URL path to `directories` table if the host matches a known machine or domain. |
| `websearch` | Search the web via Exa MCP (primary) or DuckDuckGo Lite (fallback) and return results with title, URL, and snippet (`query`, optional `num_results`) |
| `list_repo` | List files and directories in a public GitHub repository using the GitHub REST API (`owner`, `repo`, optional `path`). Returns file names, sizes, and raw download URLs. No authentication needed. |

**DICMA tools** (4) — generate wordlists and rules, no `tool_context` needed:

| Tool | Description |
|---|---|
| `dicma_generate_users` | Generate username permutations from a person's full name (`full_name`, optional `output_name`) |
| `dicma_find_related` | Find semantically related words via LLM expansion (`words`, optional `n1`/`n2`/`n3`, `output_name`). Uses active LLM config from HSF settings |
| `dicma_generate_passwords` | Generate password permutations from seed words (`words`, optional `mode`, `output_name`) |
| `dicma_generate_rules` | Generate hashcat rules from built-in patterns or a custom dictionary (`dictionary` optional, `mode`, `output_name`) |

**Attack tools** (3) — trigger attacks, require `tool_context`:

| Tool | Description |
|---|---|
| `hashcat_crack` | Crack a hash with hashcat (`hash_value` must be in inventory, `wordlist`) |
| `bruteforce_start` | Start a brute force attack (`protocol`, `target`, optional `port`) |
| `fuzz_start` | Start directory/vhost/DNS fuzzing (`method`, `target`, `wordlist`, optional `port`, `scheme`, `skip_codes`, `hide_size`, `workers`). Performs wildcard detection before scanning — aborts if catch-all found. Runs asynchronously — results are saved to the `directories` and `subdomains` tables. Use `check_fuzz_results` to retrieve them. |

**Infrastructure tools** (10) — manage services, files, evidence, and shell sessions:

| Tool | Description |
|---|---|
| `listener` | Start or stop a background service (action: "start" or "stop", service: "shells-listener" or "mdns-listener"). Requires `tool_context` |
| `list_files` | List available files by type: dictionary, rule, poc, or cache |
| `delete_file` | Delete a dictionary, rule, POC, or cache file (`file_type`, `filename`) |
| `read_cache` | Read a cached tool output file from `cache/` with optional offset/limit pagination, or regex search with context lines (`regex`, `context_before`, `context_after`) |
| `delete_evidence` | Delete an evidence session by name, or `"all"` |
| `delete_shell` | Delete a shell session by ID, or `"all"` |
| `shell_exec` | Send a command to a shell session and wait for output |
| `shell_wait` | Wait for more output from a running shell command |
| `shell_interrupt` | Interrupt a running shell command (sends Ctrl+C) |
| `connect` | Connect to a remote machine via SSH, SFTP, FTP, or WinRM using stored credentials (protocol arg) |

**POC tools** (4) — create, read, edit, and execute proof-of-concept scripts in the `pocs/` directory, no `tool_context` needed:

| Tool | Description |
|---|---|
| `poc_write` | Create or overwrite a `.py` file in the `pocs/` directory (`filename`, `content`). Rejects filenames without `.py` extension. Path-traversal protected via `_resolve_poc_path()`. |
| `poc_read` | Read a POC file from the `pocs/` directory (`filename`, optional `offset`/`limit`). Returns content with line count header. Maximum 50,000 chars per read. |
| `poc_edit` | Edit a POC file by exact string replacement (`filename`, `old_string`, `new_string`, optional `replace_all`, optional `new_filename` to rename the file). If `old_string` is not found, returns an error with instructions. If multiple matches found without `replace_all=true`, returns the count and asks for more context. Path-traversal protected. |
| `poc_exec` | Execute a POC Python script (`filename`) and return its output. Output truncated to last 5000 chars if too large. Respects the "Agent can execute POCs" safety setting. |

**POC system overview:**

POCs (Proof of Concept) are Python scripts generated by the LLM agent to demonstrate security vulnerabilities or exploit techniques. They are stored in the `pocs/` directory under `~/.local/share/hsf/pocs/`.

**Directory and path resolution:**
- `src/hsf_paths.py` — `pocs_dir()` returns `Path` to `~/.local/share/hsf/pocs/`, created lazily with `os.makedirs(exist_ok=True)`.
- Unlike `lst_dir()` and `rules_dir()`, `pocs_dir()` does not seed initial files from the package — POCs are created on-demand by the agent.

**GUI integration:**
- `PocsView` (`src/gui/views/pocs.py`) — lists POC files with icon (`poc.png`), size, and delete button. Same poll-based pattern as `DictionarysView` and `RulesView`.
- `PocDialog` (`src/gui/views/file_detail.py`) — modal dialog (`tk.Toplevel`) opened via `open_file_search(..., file_type="poc")`. Features:
  - **Line numbers** — left panel synced with editor scroll via a single `Scrollbar`. `yscrollcommand` uses `yview_moveto(float)` for cross-platform compatibility.
  - **Editable code** — `Text` widget with undo/redo (max 100 levels), full content shown.
  - **Search bar** — regex toggle, Prev/Next with match counter, Go to line. Supports `Ctrl+F` shortcut.
  - **Draggable divider** — `tk.PanedWindow(orient=tk.VERTICAL)` with `stretch="always"` between code and output panels. Initial output height is 120px.
  - **Execute button** — runs `python3 <file>` in a background thread. Output streams stdout (white) and stderr (red) in real-time. Stop button sends `SIGTERM`.
  - **Auto-save** — saves on Execute if dirty, and on Close if dirty. Dirty indicator (`•`) in info bar.
  - **Keyboard shortcuts** — `Ctrl+F` (search), `Ctrl+S` (save), `F5` (execute), `Esc` (focus editor).
  - **Cross-platform** — `wait_visibility()` before `grab_set()`. Synced scroll uses `_on_editor_scroll` / `_on_scrollbar_move` separation to avoid recursion. `yview_moveto` used for line numbers because `yview(float)` without `moveto` fails on some Tk versions.

**Inventory integration:**
- Added as a category in `InventoryView` (`src/gui/views/inventory.py`): `{"name": "Pocs", "action": "pocs", "icon": "poc.png", "enabled": True}`
- Clicking "Pocs" navigates to `PocsView`, which lists files in the `pocs/` directory.

**Console commands:**
- `view poc` — shows the `PocsView` listing
- `view poc <filename>` — opens the POC in `PocDialog`
- `delete poc <filename|all>` — deletes POC files

**Context injection:**
- `check_status` tool provides a machine/domain overview and inventory counts.
- `check_inventory` tool provides full user, credential, password, hash, people, dictionary, and POC listings. Lists POC files alongside other inventory items.

**System prompt:**
- POC generation rules (Python 3.11+, standard library, global variables, no dedicated listener, filename comment) are part of the main `system` prompt in `src/llm/config.py`. The agent receives them automatically.

**Path traversal protection:**
- `_resolve_poc_path(filename)` in `tools.py` validates that the resolved path is within the `pocs/` directory, rejecting `../` attacks.

**Implementation details for POC tools** (`src/llm/tools.py`):

- `fetch_url()` uses `requests` (already a dependency) with a Chrome 143 User-Agent.
- On Cloudflare 403 challenges (`cf-mitigated: challenge` header), retries with `"opencode/HSF"` User-Agent.
- TLS certificate verification is disabled (`verify=False`) to support self-signed certificates on internal targets. `urllib3.disable_warnings()` suppresses insecure request warnings.
- HTML content is converted to markdown via `html2text` or to plain text via `html.parser` (stdlib).
- Response size is capped at 5MB; timeout defaults to 30 seconds.
- `web_search()` uses Exa MCP (`mcp.exa.ai`) as primary, with DuckDuckGo Lite as fallback on failure.
- Exa MCP is called via JSON-RPC 2.0 over HTTP (see `src/llm/mcp.py`), with Server-Sent Events (SSE) response parsing. No API key required — Exa's MCP endpoint has an unauthenticated free tier (same approach as opencode).
- Both handlers are synchronous (blocking HTTP calls) — they run inside the agent's daemon thread.
- `webfetch` automatically saves the URL path to the `directories` table when the host matches a known machine or domain in the inventory.

### Context Management & Compaction

HSF automatically manages LLM context to prevent overflow during long agent or consultor sessions.

**Automatic Compaction:**
- Triggers when estimated tokens exceed `context_limit - 20,000` (configurable buffer via `DEFAULT_BUFFER` in `src/llm/compaction.py`)
- Calls the LLM to generate an incremental summary of old messages using a structured template
- Replaces summarized messages with a single compaction message (`_is_compaction: true`) that includes the summary text and recent verbatim messages
- Recent messages (~8K tokens worth, configurable via `DEFAULT_KEEP_TOKENS`) are preserved intact
- Subsequent compactions update the existing summary (anchored incremental summarization)
- Limits summary output to 4,096 tokens (`SUMMARY_OUTPUT_TOKENS`)
- Manual compaction available via `compact` command in Agent and Consultor modes (forces compaction regardless of overflow)

**Compaction Summary Template** (sections preserved across all compactions):
```
## Goal
## Constraints & Preferences
## Targets Discovered
## Credentials & Access
## Progress (Done, In Progress, Blocked)
## Key Findings
## Previously Fetched URLs
## Search Queries Made
## Cache Files Available
## Next Steps
```

The summarizer receives the current cache file listing (with associated URLs where available) to ensure the model knows what resources are available after compaction.

**Tool Output Bounding (`_bound_tool_output`):**
- All tool results pass through `_bound_tool_output()` in `src/llm/tools.py` before entering context
- Checks two thresholds: byte limit and line limit
- Per-tool byte limits in `TOOL_BYTE_LIMITS`; per-tool line limits in `TOOL_LINE_LIMITS`
- If output exceeds limits, full content is saved to `~/.local/share/hsf/cache/` and a truncated preview is returned
- The truncation marker includes the exact `read_cache("filename")` command to expand
- Preview format: first half of lines (head) + truncation marker + last half of lines (tail)

**Current Tool Limits:**

| Tool | Byte Limit | Line Limit | Rationale |
|------|:---:|:---:|---|
| poc_exec | 1,000 | default (2,000) | POC output is often repetitive; full file available in `pocs/` |
| port_inspector | 2,000 | default | Service probes return verbose protocol banners |
| websearch | 8,000 | default | ~20 results at ~300 bytes each; larger searches cache automatically |
| check_machine | 3,000 | default | Machine info with banners; full data via `check_machine` again |
| webfetch | 3,000 | 60 | Pages after HTML cleaning are compact; 30 head + 29 tail lines |
| Other tools | 50,000 | 2,000 | Default; most tool outputs fit comfortably |

**Tool Output Truncation in Compaction:**
- During compaction serialization, tool outputs are truncated to 2,000 chars (`TOOL_OUTPUT_MAX_CHARS`) to keep the summary prompt manageable
- This is compression for summarization only — the original tool results in current messages are preserved

**Cache System:**
- Directory: `~/.local/share/hsf/cache/` (created lazily)
- Files named `tool_{timestamp}_{tool_name}.txt`
- Cleaned on `reset` command or `delete cache`
- Tools: `list_files(cache)` to list, `read_cache(filename, offset=1, limit=500)` to read, or `read_cache(filename, regex="pattern", context_before=2, context_after=10)` to search within cached files. Use `delete cache` or `delete_file(cache, filename)` to remove.

**Webfetch HTML Cleaning:**
- Before HTML-to-markdown conversion, non-content elements are stripped via `_strip_html_non_content()` in `src/llm/web.py`
- Removed: `<nav>`, `<footer>`, `<aside>`, and elements with cookie-consent classes (`cookie`, `consent`, `gdpr`, `banner`, `popup`, `sidebar`)
- Preserved: `<header>` (may contain business/title info), `<main>`, `<article>`, `<section>`, and all text content
- If the server responds with a `Set-Cookie` header, the cookie is shown to the model at the top of the output in markdown mode (already visible in raw mode headers)
- The cleaned markdown focuses on page content without navigation noise, menus, or cookie banners
- If the full original page is needed, the uncached raw response is not available (design tradeoff for cleaner context)

**Websearch Exa Response Cleaning:**
- Exa MCP returns raw highlight text that includes verbose metadata and formatting artifacts
- `_parse_exa_results()` in `src/llm/web.py` extracts only title, URL, and compact snippets
- Strips `Published: N/A`, `Author: N/A`, `>` prefix, and `...` separators from highlights
- Snippet duplicates of the page title are removed from snippet text
- Snippets capped at 150 chars; `--` and `#` artifacts cleaned

**Context Repair:**
- When the API returns a 400 error about `tool_calls`/`tool_call_id` mismatch, `_repair_messages()` automatically cleans orphaned tool messages
- Walks backwards through messages to find the last structurally valid conversation boundary
- Logs the repair operation for debugging via `ctx_debug.log`

**Registration pattern** — decorator-based with a `_HANDLERS` dict:

```python
_HANDLERS = {}

def register(name):
    def decorator(fn):
        _HANDLERS[name] = fn
        return fn
    return decorator

def execute(name, args_dict, tool_context=None):
    handler = _HANDLERS.get(name)
    if not handler:
        return f"Unknown tool: {name}"
    try:
        return handler(args_dict, tool_context)
    except Exception as e:
        return f"Tool error: {e}"

@register("add_user")
def _add_user(args, ctx=None):
    from src.machines.credential_db import save_user
    save_user(..., origin="agent")
    return f"User '{args.get('username')}' added."
```

**Rules for adding new tools:**

1. Add the OpenAI function schema to the `TOOLS` list with `name`, `description`, and `parameters` (including `required` fields).
2. Write a handler using `@register("tool_name")` decorator. Signature: `def _handler(args, ctx=None):`.
3. Handlers must **always return a string** — this becomes the tool result sent back to the LLM.
4. Data tools use `origin="agent"` to mark agent-created records.
5. Network tools check `if not ctx: return "Cannot X: no tool context available."` — this guards against usage outside agent mode.
6. Network tools call existing App methods (`ctx._scan_interface(iface)`, `ctx._cmd_tcpscan([ip])`, etc.) — do not duplicate scan logic in tool handlers.
7. Tools that are inherently slow (full port scan, network scanning, fuzzing) should run asynchronously and store results in the database for later retrieval via query tools. Tools that complete quickly (<5s) may run synchronously and return results directly to the LLM (e.g., `ping`, `nslookup`, `port_inspector`, `scan_ip`). Mixed-mode tools (e.g., `port_scan`) return common-port results immediately and continue full scan in background.

### Agent Mode in `app.py`

The agent mode is a **console mode handler**, similar to `consultor`. The `App` class manages the full lifecycle:

**State variables** (initialized in `App.__init__`):

```python
self._agent_mode = False
self._agent_stop_event = None
self._agent_consecutive_xml_errors = 0
self._llm_messages = []        # shared conversation history (agent + consultor)
self._context_injected = False # one-shot: injected on first prompt only
```

**Console command registration:**

```python
self.console.register_command("agent", self._cmd_agent, "Enter LLM agent mode")
```

**Lifecycle:**

```python
# Entry: `agent` (interactive) or `agent <prompt>` (one-shot)
def _cmd_agent(self, args):
    if not args:
        self._enter_agent_mode()    # sets prompt to blue "Agent>"
        return
    prompt = " ".join(args)
    self._agent_ask(prompt)          # one-shot, stays in HSF> prompt

# Interactive handler — all console input routed here
def _agent_handler(self, text):
    if text.strip().lower() == "exit":
        self._leave_agent_mode()     # restores "HSF> " prompt
        return
    self._agent_ask(text)

# Core request — runs in daemon thread, dispatches to main via after()
def _agent_ask(self, prompt, _retry=False):
    self._inject_context()           # injects context on first call only
    self._llm_messages.append({"role": "user", "content": prompt})
    def _run():
        client = LLMClient(purpose="agent")   # uses "agent" system prompt
        def _on_tool(name, args, result):
            self.console.after(0, lambda: ...)
        stream = client.chat_with_tools(
            self._llm_messages, on_tool=_on_tool, tool_context=self,
            on_warning=lambda msg: self.console.warning(msg),
            stop_event=stop)
        # ... stream and append assistant response to _llm_messages
    threading.Thread(target=_run, daemon=True).start()
```

### Context Injection (`_inject_context`, `_build_model_context`)

On the **first** agent or consultor call of a session, a lightweight state summary is injected at position 0 of `_llm_messages`:

```
HSF state: Machines: #1 10.0.0.1, #2 10.0.0.2. Domains: acme.local.
Use check_status for details, check_inventory for inventory.
```

This gives the LLM a snapshot of available targets. After the first injection, `_context_injected` is set to `True` and `_inject_context()` returns immediately on all subsequent calls — zero overhead.

**`_build_model_context()`** now returns only machine IPs/IDs and domain names in a single line (~50-200 tokens). The heavy per-machine SQLite queries (ports, banners, web services) and inventory details (users, credentials, hashes, evidence, shells, dictionaries, rules, POCs) are no longer injected — the LLM uses tools (`check_status`, `check_inventory`, `check_machine`, `check_domain`) to query them on demand.

The `reset` command clears `_llm_messages` and resets `_context_injected = False`, so the next prompt re-injects the current state snapshot.

**Comparison with previous design:**

| Aspect | Old design | New design |
|---|---|---|
| Injection timing | Every agent/consultor call | First call only |
| Context size | ~800-2000 tokens | ~50-200 tokens |
| MD5 hashing | Yes, on every call | Removed |
| Delta messages | Computed via `difflib`, appended | Removed |
| SQLite queries per injection | ~100+ (N+1 per machine/domain) | 1 (in-memory `store.get_all()` + `os.listdir`) |
| Duplicate delta filtering | List comprehension on every change | Not needed |

**`check_status`** (new tool) provides the detailed state overview that `_build_model_context()` used to include: machine IPs with hostname, device type, domain, and port counts; all domain names; inventory counts (users, credentials, passwords, hashes); evidence sessions; shell sessions; dictionary/rule/POC file counts. Use `check_machine` or `check_domain` for per-target details.

This mechanism is **shared** between agent and consultor modes via the shared `self._llm_messages` list.

### Agent vs Consultor Comparison

| Feature | **Agent** mode | **Consultor** mode |
|---|---|---|
| Command | `agent` | `consultor` |
| Purpose | `"agent"` | `"consultor"` |
| System prompt | Penetration testing agent, concise | Helpful assistant, brief responses |
| Tool calling | **Yes** — `chat_with_tools()` | **No** — `chat_stream()` |
| Prompt color | Blue (`#5ba3ec`) | Yellow (`#e6b422`) |
| Context injection | Yes | Yes |
| Shared history | Yes (`self._llm_messages`) | Yes (`self._llm_messages`) |
| Context % display | Yes (`Agent (45%)>`) | Yes (`Consultor (45%)>`) |
| Spinner while processing | Yes | Yes |
| Commands | `exit`, `stop`, `reset`, `menu` | `exit`, `reset`, `menu` |
| Tab mode cycle | Cycles without interrupting agent | Cycles without interrupting consultor |

**Rules for agent development:**

- All tool handlers must be in `src/llm/tools.py`. Do not scatter tool logic across the codebase.
- Tool definitions and handlers are statically registered at import time via the `@register` decorator — no dynamic registration needed.
- `tool_context` is always the `App` instance. Tool handlers should only call methods that are safe to invoke from a background thread (scanner start methods, CRUD operations on databases).
- New tools that perform network operations MUST trigger async processes and return immediately — never block the daemon thread.
- Web tools (`webfetch`, `websearch`) are exceptions: they run synchronously inside the daemon thread because the LLM needs the fetched content to reason about it. HTTP requests complete quickly (timeout ≤ 30s).
- Tool results are strings returned to the LLM. Keep them concise and factual.
- The `_llm_messages` list accumulates the full conversation including tool call/result messages. It is reset on each new `agent` or `consultor` session entry (not on each prompt within a session).
- When the LLM outputs invalid XML tool call syntax (e.g. `<invoke>`, `<function_calls>`) instead of proper function calling, the system detects it via regex (`<[^>]*DSML`), warns the model, and retries. A consecutive error counter (`_agent_consecutive_xml_errors`, max 5 followed by abort) prevents infinite loops.
- Pressing Tab with empty input cycles through Normal → Consultor → Agent without interrupting the currently running agent thread. A braille spinner (⠋⠙⠹...) appears next to the prompt while the LLM is processing, visible in all modes.
- The prompt shows context usage percentage for both agent and consultor (e.g. `Agent (45%)>`, `Consultor (45%)>`), updated via `_update_mode_prompt()`.

---

## Guidelines for AI Agents

When modifying this project:

* Understand the existing architecture before making changes.
* Prefer incremental modifications over large rewrites.
* Respect the separation between console functionality and GUI functionality.
* Preserve the relationship between persisted data and views.
* Keep debugging additions isolated and purposeful.
* Minimize dependencies.
* Maintain pipx compatibility.
* Ensure bundled assets continue to work after packaging.
* Write code suitable for real-world penetration testing workflows.
* Favor reliability, traceability, and portability.
* **Always test installed code via `pipx install --force .`** — running from the project root with `python main.py` does not exercise the same code paths (package data, paths, permissions).

If uncertain about a design decision, choose the approach that is simpler, more maintainable, and introduces the least amount of unnecessary complexity.

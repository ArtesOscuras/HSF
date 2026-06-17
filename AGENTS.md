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

## Command System

The console provides a structured command system with subcommand routing, argument autocomplete, and help sections. All commands are registered imperatively via two methods on the `Console` instance.

### Registration

Commands are registered in `src/gui/app.py` → `_register_commands()` and in `src/gui/console.py` → `Console.__init__()` (built-in commands).

```python
# Register a command with subcommands (autocomplete popup)
self.console.register_command("delete", self._cmd_delete, "Delete stored data")
self.console.set_subcommands("delete", ["dbs", "credential", "evidence", "hash",
                                          "machine", "domain", "user", "password", "shell"])

# Register a command without subcommands
self.console.register_command("help", self._cmd_help, "Show this help message")
```

**Key methods:**
- `register_command(name, handler, help_text)` — registers a command. `handler` receives `(args: list[str])`.
- `set_subcommands(name, items)` — registers the argument-1 autocomplete list for a command. Items are simple strings.
- `add_help_section(title, items)` — adds a documentation-only section to the `help` output.

### Argument Parsing

In `_execute(raw)` (console.py), the input line is split by whitespace: `cmd = parts[0].lower()`, `args = parts[1:]`. Each handler is responsible for its own validation and routing. For commands with subcommands, a common pattern is:

```python
def _cmd_delete(self, args):
    if not args:
        self.console.body("Usage: delete <...>")
        return
    sub = args[0].lower()
    rest = args[1:]
    if sub == "dbs":
        self._cmd_delete_dbs(rest)
    elif sub == "credential":
        self._cmd_delete_credential(rest)
    ...
```

### Target Resolution

Many handlers accept targets that can be an IP, a numeric machine ID, or a domain name. A helper `_resolve_target(target)` in app.py returns `(ip, machine)` by checking:

1. IP regex → returns target as IP.
2. Numeric ID → looks up `store.get_all()` for matching machine ID.
3. IP lookup → `store.get(target)`.
4. Domain lookup → `domain_db.list_all()` for matching domain name.

Use `_resolve_to_ip(target)` when DNS resolution should be attempted for unknown targets (e.g., `use scanner <domain>` adds the domain+IP to the inventory via `socket.getaddrinfo`).

### Autocomplete System

Defined in `src/gui/console.py`. Supports **two-stage autocomplete**:

- **Command popup** — shows matching command names as the user types. Positioned above the console separator, growing upward.
- **Argument popup** — appears to the right of the command popup when the user types a space after a command that has registered subcommands. Filters subcommands by the typed prefix. Uses `set_subcommands()` data.

Key methods:
- `_filter_autocomplete()` — debounced (80ms), handles two-token input.
- `_show_autocomplete(matches)` / `_show_or_update(matches)` — create/update the command popup.
- `_show_arg_popup(items)` — create/update the argument popup (in-place, no blink).
- `_on_tab()` — cycles selections or auto-fills when only one match.

Popup dimensions are calculated using `tkfont.Font` metrics (`f.measure()` for width, `f.metrics("linespace")` for height), never `update_idletasks()`.

### Command Taxonomy

#### `add` — Add items to the inventory

Defined in `src/gui/app.py` → `_cmd_add()`.

| Subcommand | Args | Behaviour |
|---|---|---|
| `machine` | `<ip>` | Validates IP format, adds to store |
| `domain` | `<domain>` | Resolves DNS, creates machine if needed, saves domain |
| `credential` | `<username> <password\|nt_hash>` | Detects NT hash (32 hex chars) vs password |
| `user` | `<username>` | Adds to user list |
| `password` | `<password>` | Adds to password list |
| `hash` | `<type> <hash>` | Adds hash entry |

#### `delete` — Delete items or groups

Defined in `src/gui/app.py` → `_cmd_delete()`.

| Subcommand | Args | `all` support? | Behaviour |
|---|---|---|---|
| `dbs` | — | N/A | Wipes all databases |
| `credential` | `<username\|all>` | Yes | Deletes matching credential or all |
| `evidence` | `<name\|all>` | Yes | Deletes one evidence session or all |
| `hash` | `<hash\|id\|all>` | Yes | Deletes by hash value, ID, or all |
| `machine` | `<ip\|id\|all>` | Yes | Deletes one machine or all |
| `domain` | `<domain\|all>` | Yes | Deletes one domain or all |
| `user` | `<username\|all>` | Yes | Deletes one user or all |
| `password` | `<password\|all>` | Yes | Deletes one password or all |
| `shell` | `<ip\|id\|all>` | Yes | Closes one shell session or all |

All item-level subcommands try **specific value first, then numeric ID fallback** (e.g., `delete machine` tries IP lookup, then ID lookup). `all` deletes everything of that type.

#### `view` — Switch views

Defined in `src/gui/app.py` → `_cmd_view()`.

| Subcommand | Args | Behaviour |
|---|---|---|
| `list` | — | Lists all available views |
| `tools`, `machines`, `domains`, `shells`, `credentials`, `hashes`, `evidences` | — | Activate the list view |
| `users`, `passwords` | — | Activate `user-pass` view |
| `machine` | `<id\|ip>` | Open machine detail view (IP-first, then ID fallback) |
| `domain` | `<name>` | Open domain detail view |
| `shell` | `<id\|ip>` | Open shell detail view (IP-first, then ID fallback) |
| `credential` | `<username>` | Open credential detail view by username |
| `hash` | `<hash\|id>` | Open hash detail view by hash value or ID |
| `evidence` | `<name>` | Open evidence detail view |

#### `use` — Run tools

Defined in `src/gui/app.py` → `_cmd_use()`. Replaces old standalone commands (`scan`, `tcpscan`, `whatweb`, `bannergrab`, `ping`, `nslookup`, `fuzz`, `webrecorder`, `ftp`).

| Subcommand | Args | Behaviour |
|---|---|---|
| `scanner` | `[ip\|id\|domain]` | Active scan. No args → opens scan dialog |
| `bannergrab` | `<ip\|id> <port>` | Multi-probe banner grab |
| `fuzzer` | — | Opens Fuzz dialog |
| `webrecorder` | — | Opens WebRecorder dialog |
| `nslookup` | `<ip\|id\|domain>` | DNS lookup |
| `ping` | `<ip\|id\|domain>` | ICMP or system ping |
| `tcpscan` | `[ip\|id]` | TCP port scan (opens dialog if no args) |
| `udpscan` | `[ip\|id]` | UDP port scan (opens dialog if no args) |
| `whatweb` | `<ip\|id\|domain> [port]` | Web technology scan |
| `ftp` | `<...>` | FTP/SFTP connection |

#### `start` / `stop` — Service listeners

Defined in `src/gui/app.py` → `_cmd_start()` / `_cmd_stop()`.

| Command | Subcommand | Args | Behaviour |
|---|---|---|---|
| `start` | `shells-listener` | `[port]` | Start reverse shell listener (default 443/8443) |
| `start` | `mdns-listener` | — | Start passive mDNS scanner |
| `stop` | `shells-listener` | — | Stop reverse shell listener |
| `stop` | `mdns-listener` | — | Stop passive mDNS scanner |

### Adding a New Command

1. **Add the handler** in `src/gui/app.py`:
   ```python
   def _cmd_foo(self, args):
       if not args:
           self.console.body("Usage: foo <bar|baz>")
           return
       sub = args[0].lower()
       rest = args[1:]
       if sub == "bar":
           ...
   ```

2. **Register it** in `_register_commands()`:
   ```python
   self.console.register_command("foo", self._cmd_foo, "Description")
   self.console.set_subcommands("foo", ["bar", "baz"])
   ```

3. **If the command changes views**, update `add_help_section("Views", ...)`.

4. **Test** with `pipx install --force . ; hsf ; pipx uninstall hsf`.

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

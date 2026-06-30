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
* System prompts are configurable per purpose (`consultor`, `evidence_analysis`).
* Future: agent tool-calling, context injection from inventory (machines, credentials).

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

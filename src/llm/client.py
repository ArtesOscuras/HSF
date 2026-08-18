import re as _re
from openai import OpenAI

_XML_TOOL_PATTERN = _re.compile(r'<[^>]*DSML', _re.IGNORECASE)


class LLMClient:
    def __init__(self, config=None, purpose="consultor"):
        import src.llm.config as _cfg
        if config is None:
            config = _cfg.load()
        self._config = config

        pid = config.get("active_provider", "")
        provider = _cfg.get_provider(config, pid)
        self._base_url = provider.get("base_url", "")
        self._api_key = provider.get("api_key", "")
        self._model = _cfg.get_active_model(config)
        self._purpose = purpose
        self._system_prompt = config.get("prompts", {}).get("system", "")
        self._client = None
        self.last_prompt_tokens = 0

        if not pid or not provider:
            raise RuntimeError(
                "No LLM provider configured. "
                "Use 'settings' to add a provider."
            )
        if not self._model:
            raise RuntimeError(
                "No active model selected for provider "
                f"'{pid}'. Use 'settings' to configure it."
            )

    def _ensure_client(self):
        if self._client is None:
            self._client = OpenAI(
                base_url=self._base_url,
                api_key=self._api_key,
                timeout=300,
            )

    def _messages(self, messages):
        result = []
        if self._system_prompt:
            result.append(
                {"role": "system", "content": self._system_prompt})
        if self._purpose == "agent":
            result.append({"role": "system", "content": "[MODE: AGENT] You may use tools via the function calling API. Never use XML or markup to invoke tools."})
        else:
            result.append({"role": "system", "content": (
                "[MODE: CONSULTOR] You may use only read-only tools for research and "
                "inspection: check_status, check_machine, check_domain, check_inventory, "
                "check_hash, check_shells, check_evidences, check_fuzz_results, webfetch, "
                "websearch, list_repo, read_cache, list_files, poc_read, nslookup, "
                "list_interfaces, ping, dicma_generate_users, dicma_find_related, "
                "dicma_generate_passwords, dicma_generate_rules. All mutation, scanning, "
                "and attack tools are disabled — do NOT attempt to call them."
            )})
        result.extend(messages)
        return result

    def chat(self, messages, model=None, stream=False, **kwargs):
        self._ensure_client()
        m = model or self._model
        return self._client.chat.completions.create(
            model=m,
            messages=self._messages(messages),
            stream=stream,
            **kwargs,
        )

    def chat_stream(self, messages, model=None):
        self._ensure_client()
        m = model or self._model
        return self._client.chat.completions.create(
            model=m,
            messages=self._messages(messages),
            stream=True,
        )

    def chat_with_tools(self, messages, on_tool=None, model=None, tool_context=None, on_text=None, stop_event=None, on_warning=None, allowed_tools=None, on_flush=None):
        from src.llm.tools import TOOLS as _TOOLS, execute as _execute

        self._ensure_client()
        m = model or self._model
        consecutive_xml_errors = 0
        self._safe_len = len(messages) - 1

        def _persist():
            if tool_context and hasattr(tool_context, '_save_session'):
                try:
                    tool_context._save_session()
                except Exception:
                    pass

        def _abort(stream):
            try:
                stream.close()
            except Exception:
                pass

        while True:
            if stop_event and stop_event.is_set():
                return None
            try:
                stream = self._client.chat.completions.create(
                    model=m,
                    messages=self._messages(messages),
                    tools=_TOOLS,
                    stream=True,
                    stream_options={"include_usage": True},
                )
            except Exception:
                stream = self._client.chat.completions.create(
                    model=m,
                    messages=self._messages(messages),
                    tools=_TOOLS,
                    stream=True,
                )
            content_parts = []
            tool_calls = {}
            finish_reason = None
            for chunk in stream:
                if stop_event and stop_event.is_set():
                    _abort(stream)
                    return None
                if getattr(chunk, 'usage', None):
                    self.last_prompt_tokens = chunk.usage.prompt_tokens
                    if tool_context and not getattr(tool_context, '_closing', False):
                        tool_context._total_api_tokens = chunk.usage.prompt_tokens
                        try:
                            tool_context.after(0, tool_context._update_mode_prompt)
                        except RuntimeError:
                            pass
                if not chunk.choices:
                    continue
                choice = chunk.choices[0]
                delta = choice.delta
                if delta is not None:
                    if delta.content:
                        content_parts.append(delta.content)
                        if on_text:
                            try:
                                on_text(delta.content)
                            except RuntimeError:
                                pass
                    if delta.tool_calls:
                        for tc in delta.tool_calls:
                            acc = tool_calls.setdefault(tc.index, {"id": "", "name": "", "arguments": ""})
                            if tc.id:
                                acc["id"] = tc.id
                            if tc.function is not None:
                                if tc.function.name:
                                    acc["name"] += tc.function.name
                                if tc.function.arguments:
                                    acc["arguments"] += tc.function.arguments
                if choice.finish_reason:
                    finish_reason = choice.finish_reason

            content = "".join(content_parts)
            if on_flush:
                try:
                    on_flush()
                except RuntimeError:
                    pass

            if finish_reason == "tool_calls" and tool_calls:
                if stop_event and stop_event.is_set():
                    return None
                consecutive_xml_errors = 0
                tool_calls_list = [
                    {
                        "id": tool_calls[i]["id"],
                        "type": "function",
                        "function": {
                            "name": tool_calls[i]["name"],
                            "arguments": tool_calls[i]["arguments"],
                        },
                    }
                    for i in sorted(tool_calls)
                ]
                messages.append({
                    "role": "assistant",
                    "content": content or None,
                    "tool_calls": tool_calls_list,
                })
                _persist()
                for i in sorted(tool_calls):
                    tc = tool_calls[i]
                    args = {}
                    try:
                        import json
                        args = json.loads(tc["arguments"])
                    except Exception:
                        pass
                    if allowed_tools is None or tc["name"] in allowed_tools:
                        result = _execute(tc["name"], args, tool_context)
                    else:
                        result = f"Tool '{tc['name']}' is not available in consultor mode (read-only tools only)."
                    if on_tool:
                        on_tool(tc["name"], args, result)
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tc["id"],
                        "content": result,
                    })
                    _persist()
                self._safe_len = len(messages)
                if tool_context and hasattr(tool_context, '_compact_if_needed'):
                    try:
                        if tool_context._compact_if_needed():
                            self._safe_len = len(messages)
                    except Exception:
                        pass
                continue

            if not content:
                return None

            if _XML_TOOL_PATTERN.search(content):
                consecutive_xml_errors += 1
                if on_warning:
                    try:
                        on_warning("Tool calling error")
                    except RuntimeError:
                        pass
                if consecutive_xml_errors >= 5:
                    return content
                messages.append({"role": "assistant", "content": content})
                messages.append({
                    "role": "system",
                    "content": (
                        "INVALID TOOL CALL FORMAT. You used XML tags like "
                        "<invoke> which is not supported. You MUST use the "
                        "proper function calling mechanism to invoke tools. "
                        "The tool was NOT executed — nothing happened. "
                        "Do NOT emit raw XML. Retry your tool calls correctly."
                    ),
                })
                _persist()
                continue

            consecutive_xml_errors = 0
            return content

    @property
    def model(self):
        return self._model

    @property
    def base_url(self):
        return self._base_url

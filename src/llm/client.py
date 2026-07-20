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
            result.append({"role": "system", "content": "[MODE: CONSULTOR] Do NOT use tools. Provide analysis and advice only."})
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

    def chat_with_tools(self, messages, on_tool=None, model=None, tool_context=None, on_text=None, stop_event=None, on_warning=None):
        from src.llm.tools import TOOLS as _TOOLS, execute as _execute

        self._ensure_client()
        m = model or self._model
        consecutive_xml_errors = 0
        self._safe_len = len(messages) - 1

        while True:
            if stop_event and stop_event.is_set():
                return None
            resp = self._client.chat.completions.create(
                model=m,
                messages=self._messages(messages),
                tools=_TOOLS,
            )
            if hasattr(resp, 'usage') and resp.usage:
                self.last_prompt_tokens = resp.usage.prompt_tokens
                if tool_context:
                    tool_context._total_api_tokens = resp.usage.prompt_tokens
                    try:
                        tool_context.after(0, tool_context._update_mode_prompt)
                    except RuntimeError:
                        pass
            choice = resp.choices[0]
            if choice.finish_reason == "tool_calls" and choice.message.tool_calls:
                consecutive_xml_errors = 0
                if choice.message.content and on_text:
                    try:
                        on_text(choice.message.content)
                    except RuntimeError:
                        pass
                messages.append(choice.message)
                for tc in choice.message.tool_calls:
                    args = {}
                    try:
                        import json
                        args = json.loads(tc.function.arguments)
                    except Exception:
                        pass
                    result = _execute(tc.function.name, args, tool_context)
                    if on_tool:
                        on_tool(tc.function.name, args, result)
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": result,
                    })
                self._safe_len = len(messages)
                continue
            if choice.message.content:
                if _XML_TOOL_PATTERN.search(choice.message.content):
                    consecutive_xml_errors += 1
                    if on_warning:
                        try:
                            on_warning("Tool calling error")
                        except RuntimeError:
                            pass
                    if consecutive_xml_errors >= 5:
                        stream = self._client.chat.completions.create(
                            model=m,
                            messages=self._messages(messages),
                            stream=True,
                        )
                        return stream
                    messages.append(choice.message)
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
                    continue
                consecutive_xml_errors = 0
                stream = self._client.chat.completions.create(
                    model=m,
                    messages=self._messages(messages),
                    stream=True,
                )
                return stream
            return None

    @property
    def model(self):
        return self._model

    @property
    def base_url(self):
        return self._base_url

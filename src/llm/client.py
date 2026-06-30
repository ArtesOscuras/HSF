from openai import OpenAI


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
        self._system_prompt = config.get("prompts", {}).get(purpose, "")
        self._client = None

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

    def chat_with_tools(self, messages, on_tool=None, model=None, tool_context=None):
        from src.llm.tools import TOOLS as _TOOLS, execute as _execute

        self._ensure_client()
        m = model or self._model
        current = list(messages)

        for _ in range(35):
            resp = self._client.chat.completions.create(
                model=m,
                messages=self._messages(current),
                tools=_TOOLS,
            )
            choice = resp.choices[0]
            if choice.finish_reason == "tool_calls" and choice.message.tool_calls:
                current.append(choice.message)
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
                    current.append({
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": result,
                    })
                continue
            if choice.message.content:
                stream = self._client.chat.completions.create(
                    model=m,
                    messages=self._messages(current),
                    stream=True,
                )
                return stream
            return None

        raise RuntimeError("Too many tool-calling iterations.")

    @property
    def model(self):
        return self._model

    @property
    def base_url(self):
        return self._base_url

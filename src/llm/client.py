from openai import OpenAI


class LLMClient:
    def __init__(self, config=None):
        import src.llm.config as _cfg
        if config is None:
            config = _cfg.load()
        self._config = config

        provider = _cfg.get_provider(config)
        self._base_url = provider.get("base_url", "")
        self._api_key = provider.get("api_key", "")
        self._model = _cfg.get_active_model(config)
        self._system_prompt = config.get("prompts", {}).get("consultor", "")
        self._client = None

    def _ensure_client(self):
        if self._client is None:
            self._client = OpenAI(
                base_url=self._base_url,
                api_key=self._api_key,
                timeout=300,
            )

    def _messages(self, messages):
        if self._system_prompt and not any(
                m.get("role") == "system" for m in messages):
            return [{"role": "system", "content": self._system_prompt}] + list(messages)
        return list(messages)

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

    @property
    def model(self):
        return self._model

    @property
    def base_url(self):
        return self._base_url

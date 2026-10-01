"""LLM provider package — factory entry point."""

from __future__ import annotations

import logging
import time

from mira.config import LLMConfig
from mira.exceptions import NonRetriableLLMError
from mira.llm.base import LLMProviderProtocol

logger = logging.getLogger(__name__)

# Model-id prefixes routed to a signed-in subscription account instead of config.provider,
# so one deployment can mix API-key and ChatGPT/Claude subscription models per purpose.
SUBSCRIPTION_PREFIXES = {"chatgpt/": "chatgpt", "claude/": "anthropic"}

# A model that failed with a retriable error (quota, outage) is tried last for this long.
CHAIN_COOLDOWN_SECONDS = 300
# ponytail: per-process cooldown map; share via the DB if Mira ever runs multiple replicas.
_cooling_until: dict[str, float] = {}


class ModelChain:
    """Try each model in order until one answers. Models can use different providers."""

    def __init__(self, models: list[str], providers: list[LLMProviderProtocol]) -> None:
        self.models = models
        self.providers = providers
        self.config = providers[0].config  # type: ignore[attr-defined]
        self.supports_json_mode = providers[0].supports_json_mode
        self.supports_tool_calling = all(p.supports_tool_calling for p in providers)

    @property
    def total_prompt_tokens(self) -> int:
        return sum(p.total_prompt_tokens for p in self.providers)

    @property
    def total_completion_tokens(self) -> int:
        return sum(p.total_completion_tokens for p in self.providers)

    @property
    def usage(self) -> dict[str, int]:
        prompt, completion = self.total_prompt_tokens, self.total_completion_tokens
        return {
            "prompt_tokens": prompt,
            "completion_tokens": completion,
            "total_tokens": prompt + completion,
        }

    def count_tokens(self, text: str) -> int:
        return self.providers[0].count_tokens(text)

    async def _run(self, method: str, *args, **kwargs):  # type: ignore[no-untyped-def]
        now = time.time()
        # Stable sort: healthy models keep their order, recently failed ones go last.
        order = sorted(
            range(len(self.models)), key=lambda i: _cooling_until.get(self.models[i], 0) > now
        )
        last: Exception | None = None
        for i in order:
            try:
                return await getattr(self.providers[i], method)(*args, **kwargs)
            except Exception as exc:
                last = exc
                if not isinstance(exc, NonRetriableLLMError):
                    _cooling_until[self.models[i]] = time.time() + CHAIN_COOLDOWN_SECONDS
                logger.warning("Model %s failed (%s); trying the next model", self.models[i], exc)
        assert last is not None
        raise last

    async def complete(self, *args, **kwargs):  # type: ignore[no-untyped-def]
        return await self._run("complete", *args, **kwargs)

    async def complete_with_tools(self, *args, **kwargs):  # type: ignore[no-untyped-def]
        return await self._run("complete_with_tools", *args, **kwargs)

    async def complete_agentic(self, *args, **kwargs):  # type: ignore[no-untyped-def]
        return await self._run("complete_agentic", *args, **kwargs)

    async def review(self, *args, **kwargs):  # type: ignore[no-untyped-def]
        return await self._run("review", *args, **kwargs)

    async def walkthrough(self, *args, **kwargs):  # type: ignore[no-untyped-def]
        return await self._run("walkthrough", *args, **kwargs)


def create_llm(config: LLMConfig) -> LLMProviderProtocol:
    """Create the provider for config.model, wrapped in a ModelChain when fallbacks are set."""
    extra = [config.fallback_model] if config.fallback_model else []
    models = list(dict.fromkeys([config.model, *config.fallback_models, *extra]))
    if len(models) == 1:
        return _create_one(config)
    single = {"fallback_model": None, "fallback_models": []}
    return ModelChain(
        models, [_create_one(config.model_copy(update={**single, "model": m})) for m in models]
    )


def _create_one(config: LLMConfig) -> LLMProviderProtocol:
    for prefix, account in SUBSCRIPTION_PREFIXES.items():
        if config.model.startswith(prefix):
            sub = config.model_copy(update={"model": config.model.removeprefix(prefix)})
            if account == "anthropic":
                from mira.llm.anthropic_oauth import AnthropicOAuthProvider

                return AnthropicOAuthProvider(sub)
            from mira.llm.chatgpt_oauth import ChatGPTOAuthProvider

            return ChatGPTOAuthProvider(sub)

    if config.model.startswith("@"):
        return _create_connected(config)

    if config.provider == "bedrock":
        from mira.llm.bedrock import BedrockProvider

        return BedrockProvider(config)

    if config.provider in {"codex-cli", "codex_cli", "codex"}:
        from mira.llm.codex_cli import CodexCLIProvider

        return CodexCLIProvider(config)

    if config.api_style == "responses":
        from mira.llm.responses import ResponsesProvider

        return ResponsesProvider(config)

    # Default: OpenAI-compatible endpoint (OpenRouter, vLLM, Ollama, etc.)
    from mira.llm.provider import LLMProvider

    return LLMProvider(config)


def _create_connected(config: LLMConfig) -> LLMProviderProtocol:
    """`@<id>/<model>` runs on a provider connected in Settings → Providers."""
    from mira.llm import api_providers
    from mira.llm import provider_profiles as profiles
    from mira.llm.provider import LLMProvider

    pid, _, model = config.model[1:].partition("/")
    provider = api_providers.get(pid)
    if provider is None:
        raise NonRetriableLLMError("provider_not_connected", provider=pid)
    key = provider.get("api_key") or None
    # The client strips the first "vendor/" segment unless the endpoint's profile keeps it
    # (OpenRouter); prefix with the id so the provider gets its own model id unchanged.
    if profiles.resolve(provider["base_url"]).get("model_prefix") != "keep":
        model = f"{pid}/{model}"
    return LLMProvider(
        config.model_copy(
            update={
                "model": model,
                "base_url": provider["base_url"],
                "api_key": key,
                "api_key_env": config.api_key_env if key else "",
                "api_style": "chat",
            }
        )
    )

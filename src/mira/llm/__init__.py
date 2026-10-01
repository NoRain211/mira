"""LLM provider package — factory entry point."""

from __future__ import annotations

from mira.config import LLMConfig
from mira.llm.base import LLMProviderProtocol

# Model-id prefixes routed to a signed-in subscription account instead of config.provider,
# so one deployment can mix API-key and ChatGPT/Claude subscription models per purpose.
SUBSCRIPTION_PREFIXES = {"chatgpt/": "chatgpt", "claude/": "anthropic"}


def create_llm(config: LLMConfig) -> LLMProviderProtocol:
    """Create the appropriate LLM provider based on config.provider.

    Returns an instance satisfying LLMProviderProtocol.
    """
    for prefix, account in SUBSCRIPTION_PREFIXES.items():
        if config.model.startswith(prefix):
            # A fallback model belongs to config.provider, which this transport can't reach.
            sub = config.model_copy(
                update={"model": config.model.removeprefix(prefix), "fallback_model": None}
            )
            if account == "anthropic":
                from mira.llm.anthropic_oauth import AnthropicOAuthProvider

                return AnthropicOAuthProvider(sub)
            from mira.llm.chatgpt_oauth import ChatGPTOAuthProvider

            return ChatGPTOAuthProvider(sub)

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

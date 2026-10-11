"""Groq chat model, resolved per session and cached per distinct key."""

from functools import lru_cache

from langchain_groq import ChatGroq

from src.config.session import require, resolve_groq_api_key
from src.config.settings import GROQ_MODEL


@lru_cache(maxsize=8)
def _build_llm(model: str, api_key: str) -> ChatGroq:
    llm = ChatGroq(model=model, api_key=api_key)

    # Groq's free tier enforces tokens-per-minute limits, and one trip
    # request fires several LLM calls back-to-back (one per agent), so
    # a brief 429 here is expected, not a bug. Retry with backoff
    # instead of failing the whole request.
    return llm.with_retry(
        stop_after_attempt=4,
        wait_exponential_jitter=True,
    )


def get_llm() -> ChatGroq:
    """
    The key comes from the current session if one supplied it, otherwise
    from the server's .env. One client is reused per distinct key.
    """

    require("GROQ_API_KEY")

    return _build_llm(GROQ_MODEL, resolve_groq_api_key())

"""
Embedders for Recall

Provides a pluggable embedder factory. Supports:
- openai (default) — uses OpenAI SDK
- phi (local Ollama) — uses `ollama embed phi:latest` or OLLAMA_PROXY_URL fallback
- nomic (local Ollama embedding model) — uses Ollama HTTP /api/embed for `nomic-embed-text`

Usage: from recall.tools.embedder import get_embedder; embed = get_embedder(); vec = embed(text)
"""
from functools import lru_cache
import json
import os
import shlex
import subprocess
import logging
from typing import Callable, List

logger = logging.getLogger(__name__)

# Defaults
OLLAMA_PROXY_URL = os.getenv("OLLAMA_PROXY_URL", "http://host.docker.internal:5001/phi_embed")
OLLAMA_PROXY_NOMIC_URL = os.getenv("OLLAMA_PROXY_NOMIC_URL", "http://host.docker.internal:5001/nomic_embed")
OLLAMA_HTTP_EMBED_URL = os.getenv("OLLAMA_HTTP_EMBED_URL", "http://host.docker.internal:11434/api/embed")
EMBEDDER_PROVIDER = os.getenv("EMBEDDER_PROVIDER", os.getenv("MODEL_EMBEDDER", "openai")).lower()


def _ollama_embed_cli(text: str, model: str = "phi:latest") -> List[float]:
    """Call local `ollama embed <model> <text>` and parse JSON output."""
    try:
        proc = subprocess.run(["ollama", "embed", model, text], capture_output=True, text=True, timeout=30)
        if proc.returncode != 0:
            raise RuntimeError(proc.stderr.strip() or f"ollama exited {proc.returncode}")
        out = proc.stdout.strip()
        return json.loads(out)
    except FileNotFoundError as e:
        raise RuntimeError("ollama CLI not found") from e


def _ollama_embed_proxy(text: str) -> List[float]:
    """Call the host OLLAMA proxy to get embeddings (used when running inside container)."""
    import requests

    resp = requests.post(OLLAMA_PROXY_URL, json={"text": text}, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    if "embedding" in data:
        return data["embedding"]
    if isinstance(data, list):
        return data
    raise RuntimeError("invalid response from ollama proxy")


def _nomic_embed_http(text: str) -> List[float]:
    """Call the Ollama HTTP embed API for nomic-embed-text."""
    import requests

    resp = requests.post(OLLAMA_HTTP_EMBED_URL, json={"model": "nomic-embed-text", "input": text}, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    # Ollama API may return the raw array or an object containing 'embedding'
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        # Ollama HTTP API returns {'model':..., 'embeddings': [[...]]}
        if "embeddings" in data and isinstance(data["embeddings"], list) and data["embeddings"]:
            return data["embeddings"][0]
        if "embedding" in data:
            return data["embedding"]
        # some APIs return 'data': [{ 'embedding': [...] }]
        if "data" in data and isinstance(data["data"], list) and "embedding" in data["data"][0]:
            return data["data"][0]["embedding"]
    raise RuntimeError("invalid response from Ollama HTTP embed API")


def _nomic_embed_proxy(text: str) -> List[float]:
    """Fallback to the host proxy for nomic embeddings."""
    import requests

    resp = requests.post(OLLAMA_PROXY_NOMIC_URL, json={"text": text}, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    if "embedding" in data:
        return data["embedding"]
    if isinstance(data, list):
        return data
    raise RuntimeError("invalid response from ollama proxy (nomic)")


def _openai_embed(text: str) -> List[float]:
    """OpenAI embeddings (uses openai.OpenAI client)."""
    try:
        from openai import OpenAI
    except Exception as e:  # pragma: no cover - import-time
        raise RuntimeError("OpenAI SDK not available") from e

    client = OpenAI()
    resp = client.embeddings.create(model="text-embedding-3-small", input=text)
    return resp.data[0].embedding


class _EmbedderWrapper:
    """Wrap a simple embedding function and expose a `.dimensions` attr required by PgVector.

    Backwards-compatible helpers implemented so `agno`'s embedding callers (which may expect
    methods such as `get_embedding_and_usage`) will work with this lightweight wrapper.
    """
    def __init__(self, fn: Callable[[str], List[float]], dimensions: int, provider: str | None = None):
        self._fn = fn
        self.dimensions = dimensions
        self.provider = provider or "custom"

    def __call__(self, text: str) -> List[float]:
        return self._fn(text)

    # Compatibility helpers commonly used by upstream embedder interfaces
    def get_embedding(self, text: str) -> List[float]:
        return self._fn(text)

    def get_embedding_and_usage(self, text: str):
        embedding = self._fn(text)
        # return a small usage-like dict for compatibility
        usage = {"model": self.provider, "tokens": None}
        return embedding, usage

    def get_embeddings(self, texts: list[str]) -> list[list[float]]:
        return [self._fn(t) for t in texts]

    def get_embeddings_and_usage(self, texts: list[str]):
        embeddings = [self._fn(t) for t in texts]
        usage = {"model": self.provider, "count": len(texts)}
        return embeddings, usage

@lru_cache(maxsize=1)
def get_embedder(provider: str | None = None) -> _EmbedderWrapper:
    """Return an Embedder wrapper for the requested provider.

    provider: 'openai' (default), 'phi', or 'nomic'. If provider is None, uses env EMBEDDER_PROVIDER.
    The returned object is callable and exposes `.dimensions` (required by PgVector).
    """
    prov = (provider or EMBEDDER_PROVIDER or "openai").lower()

    if prov == "phi":
        def _fn(text: str) -> List[float]:
            try:
                return _ollama_embed_cli(text, model="phi:latest")
            except Exception as e:
                logger.debug("ollama CLI failed for phi, falling back to proxy: %s", e)
                return _ollama_embed_proxy(text)

        # conservative default (phi embeddings via Ollama not guaranteed) — use 1536
        return _EmbedderWrapper(_fn, dimensions=1536, provider='phi')

    if prov == "nomic":
        def _fn(text: str) -> List[float]:
            try:
                return _nomic_embed_http(text)
            except Exception as e:
                logger.debug("nomic HTTP embed failed, falling back to proxy: %s", e)
                return _nomic_embed_proxy(text)

        return _EmbedderWrapper(_fn, dimensions=768, provider='nomic')

    # default: openai
    def _open(text: str) -> List[float]:
        return _openai_embed(text)

    return _EmbedderWrapper(_open, dimensions=1536, provider='openai')

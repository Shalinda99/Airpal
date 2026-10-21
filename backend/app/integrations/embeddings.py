"""Embedding provider interface. 'hash' is a dependency-free local fallback (lexical); 'openai' is OpenAI-compatible."""

import hashlib
import math
import re

import httpx

from app.core.config import settings

_TOKEN = re.compile(r"[a-z0-9]+")
_STOP = {"the", "a", "an", "is", "are", "of", "to", "in", "and", "or", "for", "at", "on", "do", "i", "my", "what",
         "how", "can", "does", "there", "it", "be", "you", "me", "from", "with"}


def _stem(w: str) -> str:
    for suf in ("ing", "es", "s"):
        if w.endswith(suf) and len(w) > len(suf) + 2:
            return w[: -len(suf)]
    return w


def _hash_embed(text: str, dim: int) -> list[float]:
    vec = [0.0] * dim
    toks = [_stem(t) for t in _TOKEN.findall(text.lower()) if t not in _STOP]
    grams = toks + [f"{a}_{b}" for a, b in zip(toks, toks[1:], strict=False)]
    for g in grams:
        h = int(hashlib.md5(g.encode()).hexdigest(), 16)
        vec[h % dim] += 1.0 if "_" not in g else 0.7
    norm = math.sqrt(sum(v * v for v in vec)) or 1.0
    return [v / norm for v in vec]


def embed_texts(texts: list[str]) -> list[list[float]]:
    if settings.embedding_provider == "openai" and settings.openai_api_key:
        r = httpx.post(
            f"{settings.openai_base_url}/embeddings",
            headers={"Authorization": f"Bearer {settings.openai_api_key}"},
            json={"model": settings.openai_embedding_model, "input": texts, "dimensions": settings.embedding_dim},
            timeout=30,
        )
        r.raise_for_status()
        return [d["embedding"] for d in r.json()["data"]]
    return [_hash_embed(t, settings.embedding_dim) for t in texts]


def cosine(a: list[float], b: list[float]) -> float:
    return sum(x * y for x, y in zip(a, b, strict=False))

"""Embedding utilities for semantic product search.

Two interchangeable backends:
  1. Sentence-Transformers (install backend/requirements-ml.txt) — real
     semantic embeddings, model cached locally after first download.
  2. Deterministic TF-IDF/hashing embedder (built in) — offline fallback so
     semantic features always work without downloading models.

Both expose the same `embed(texts) -> np.ndarray` interface and normalised
vectors, so cosine similarity behaves identically at the call site.
"""

import hashlib
import logging
import math
import re
from typing import Iterable, Optional

import numpy as np

logger = logging.getLogger("shopmate.embeddings")

_MODEL_ID = "all-MiniLM-L6-v2"
_st_model = None
_st_load_attempted = False

_TOKEN_RE = re.compile(r"[a-z0-9]+")

# Small domain lexicon: map shopping synonyms onto shared tokens so the
# fallback embedder captures rough semantic overlap (e.g. "laptop"~"notebook").
_SYN = {
    "laptop": ["notebook", "computer", "ultrabook", "gaming"],
    "phone": ["smartphone", "mobile", "cellphone"],
    "headphone": ["headset", "earphone", "earbud", "audio"],
    "earbuds": ["earphone", "headphone", "wireless"],
    "cheap": ["budget", "affordable", "value", "inexpensive"],
    "expensive": ["premium", "costly", "highend"],
    "fast": ["performance", "quick", "powerful"],
    "battery": ["endurance", "charge", "mah"],
    "camera": ["photography", "photo", "lens"],
}


def _try_load_st():
    """Attempt to load Sentence-Transformers once; return None if unavailable."""
    global _st_model, _st_load_attempted
    if _st_load_attempted:
        return _st_model
    _st_load_attempted = True
    try:
        from sentence_transformers import SentenceTransformer

        _st_model = SentenceTransformer(_MODEL_ID)
        logger.info("sentence_transformers_loaded model=%s", _MODEL_ID)
    except Exception as exc:  # not installed / offline / download failure
        logger.info("sentence_transformers_unavailable (%s); using TF-IDF fallback", exc)
        _st_model = None
    return _st_model


def reset_embedding_cache() -> None:
    """Test helper."""
    global _st_model, _st_load_attempted
    _st_model, _st_load_attempted = None, False


def _tokenize(text: str) -> list[str]:
    tokens = _TOKEN_RE.findall((text or "").lower())
    expanded: list[str] = []
    for t in tokens:
        expanded.append(t)
        expanded.extend(_SYN.get(t, []))
    return expanded


class _TfidfEmbedder:
    """Vocabulary-fitted TF-IDF vectors (deterministic, no dependencies)."""

    def __init__(self, dim: int = 512):
        self.dim = dim
        self.idf: dict[str, float] = {}
        self.fitted = False

    def _vec(self, tokens: Iterable[str]) -> np.ndarray:
        v = np.zeros(self.dim, dtype=np.float32)
        for t in tokens:
            idx = int(hashlib.md5(t.encode("utf-8")).hexdigest(), 16) % self.dim
            v[idx] += 1.0
        for t in tokens:
            idx = int(hashlib.md5(t.encode("utf-8")).hexdigest(), 16) % self.dim
            v[idx] *= self.idf.get(t, 1.0)
        norm = float(np.linalg.norm(v))
        return v / norm if norm > 0 else v

    def fit(self, corpus: list[str]) -> None:
        df: dict[str, int] = {}
        n = max(len(corpus), 1)
        for doc in corpus:
            for t in set(_tokenize(doc)):
                df[t] = df.get(t, 0) + 1
        self.idf = {t: math.log((n + 1) / (c + 1)) + 1.0 for t, c in df.items()}
        self.fitted = True

    def encode(self, texts: list[str]) -> np.ndarray:
        return np.stack([self._vec(_tokenize(t)) for t in texts])


_tfidf = _TfidfEmbedder()


def embed(texts: list[str], corpus: Optional[list[str]] = None) -> np.ndarray:
    """Encode texts into normalised vectors (N, dim).

    If Sentence-Transformers is available it is used directly. Otherwise the
    TF-IDF fallback is fitted on `corpus` (or the texts themselves) first so
    the vectors carry real term-weighting information.
    """
    if not texts:
        return np.zeros((0, _tfidf.dim), dtype=np.float32)

    model = _try_load_st()
    if model is not None:
        vectors = model.encode(texts, normalize_embeddings=True,
                               show_progress_bar=False)
        return np.asarray(vectors, dtype=np.float32)

    if corpus:
        _tfidf.fit(list(corpus))
    elif not _tfidf.fitted:
        _tfidf.fit(texts)
    return _tfidf.encode(texts)


def cosine(a: np.ndarray, b: np.ndarray) -> float:
    """Cosine similarity between two 1-D vectors (0 if either is empty)."""
    if a.size == 0 or b.size == 0:
        return 0.0
    denom = float(np.linalg.norm(a) * np.linalg.norm(b))
    if denom == 0:
        return 0.0
    return float(np.dot(a, b) / denom)


def similarity_matrix(queries: np.ndarray, corpus: np.ndarray) -> np.ndarray:
    """Row-wise cosine similarity (Q, D)."""
    if queries.size == 0 or corpus.size == 0:
        return np.zeros((queries.shape[0], corpus.shape[0]), dtype=np.float32)
    q = queries / np.maximum(np.linalg.norm(queries, axis=1, keepdims=True), 1e-9)
    c = corpus / np.maximum(np.linalg.norm(corpus, axis=1, keepdims=True), 1e-9)
    return (q @ c.T).astype(np.float32)


# Alias used by the recommendation service.
cosine_matrix = similarity_matrix

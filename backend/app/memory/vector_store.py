"""
A dependency-light "vector memory" for long-term recall across tasks.

Why TF-IDF instead of a heavyweight embedding model?
This project is meant to run anywhere with `docker compose up` and no
GPU / model download step. TF-IDF + cosine similarity gives genuine
semantic-ish retrieval for a portfolio project's scale (hundreds to a
few thousand notes) with zero network dependency at runtime. The
`SemanticMemory` interface below is provider-agnostic -- swapping in
a real embedding model (OpenAI, Voyage, sentence-transformers) later
is a one-file change, which is worth calling out in an interview.
"""
from __future__ import annotations
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np

from .. import database
from ..config import settings


class SemanticMemory:
    def __init__(self):
        self._vectorizer: TfidfVectorizer | None = None
        self._matrix = None
        self._corpus: list[str] = []
        self._dirty = True

    def add(self, task_id: str, text: str):
        database.add_memory(task_id, text)
        self._dirty = True

    def _rebuild(self):
        self._corpus = database.all_memory()
        if not self._corpus:
            self._vectorizer, self._matrix = None, None
            self._dirty = False
            return
        self._vectorizer = TfidfVectorizer(stop_words="english", max_features=4096)
        self._matrix = self._vectorizer.fit_transform(self._corpus)
        self._dirty = False

    def search(self, query: str, k: int = None) -> list[str]:
        k = k or settings.MEMORY_TOP_K
        if self._dirty:
            self._rebuild()
        if not self._corpus or self._vectorizer is None:
            return []
        q_vec = self._vectorizer.transform([query])
        sims = cosine_similarity(q_vec, self._matrix).flatten()
        top_idx = np.argsort(sims)[::-1][:k]
        return [self._corpus[i] for i in top_idx if sims[i] > 0.05]


memory = SemanticMemory()

from __future__ import annotations

from dataclasses import asdict
from typing import List

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from app.services.chunker import Chunk


class TfidfRetriever:
    """Simple local retrieval layer. Replace with embeddings + pgvector later if needed."""

    def __init__(self, chunks: List[Chunk]):
        self.chunks = chunks
        self.vectorizer = TfidfVectorizer(stop_words="english", ngram_range=(1, 2))
        self.matrix = self.vectorizer.fit_transform([c.text for c in chunks]) if chunks else None

    def search(self, query: str, top_k: int = 5) -> List[dict]:
        if not self.chunks or self.matrix is None:
            return []
        q = self.vectorizer.transform([query])
        scores = cosine_similarity(q, self.matrix).flatten()
        ranked = scores.argsort()[::-1][:top_k]
        results = []
        for i in ranked:
            if scores[i] <= 0:
                continue
            item = asdict(self.chunks[i])
            item["score"] = round(float(scores[i]), 4)
            results.append(item)
        return results

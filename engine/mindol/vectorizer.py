"""mindol.vectorizer - n-gram hash vectorizer"""
from __future__ import annotations
import hashlib, re
import numpy as np

class SimpleVectorizer:
    def __init__(self, dim: int = 256):
        self.dim = dim
    def _hash_ngram(self, ngram: str) -> int:
        return int(hashlib.sha256(ngram.encode("utf-8")).hexdigest()[:8], 16)
    def embed(self, text: str) -> np.ndarray:
        vec = np.zeros(self.dim, dtype=np.float32)
        if not text.strip(): return vec
        features = {}; text_lower = text.lower()
        for ch in text_lower:
            if ch.strip():
                h = self._hash_ngram(f"c_{ch}"); features[h % self.dim] = features.get(h % self.dim, 0) + 0.5
        for i in range(len(text_lower) - 1):
            bg = text_lower[i:i+2]
            if bg.strip():
                h = self._hash_ngram(f"b_{bg}"); features[h % self.dim] = features.get(h % self.dim, 0) + 1.0
        for i in range(len(text_lower) - 2):
            tg = text_lower[i:i+3]
            if tg.strip():
                h = self._hash_ngram(f"t_{tg}"); features[h % self.dim] = features.get(h % self.dim, 0) + 1.5
        words = re.findall(r"[\w]+", text_lower)
        for w in words:
            if len(w) >= 2:
                h = self._hash_ngram(f"w_{w}"); features[h % self.dim] = features.get(h % self.dim, 0) + 2.0
        for idx, val in features.items(): vec[idx] = val
        norm = np.linalg.norm(vec)
        if norm > 0: vec = vec / norm
        return vec
    def embedding_dim(self) -> int: return self.dim

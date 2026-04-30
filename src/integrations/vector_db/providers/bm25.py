from collections import defaultdict
import math
import spacy
from typing import List, Optional, Dict, Any
class BM25Encoder:
    def __init__(self, k1=1.5, b=0.75):
        self.k1 = k1
        self.b = b
        self.vocab = {}
        self.idf = {}
        self.avg_doc_len = 0
        self.doc_count = 0
        self.nlp = spacy.load("en_core_web_sm", disable=["ner", "parser"])

    def _tokenize(self, text: str) -> List[str]:
        doc = self.nlp(text.lower())
        return [
            token.lemma_
            for token in doc
            if not token.is_stop and token.is_alpha
        ]

    def fit(self, documents: List[str]):
        df = defaultdict(int)
        doc_lens = []

        for doc_text in documents:
            tokens = self._tokenize(doc_text)
            doc_lens.append(len(tokens))
            for token in set(tokens):
                df[token] += 1

        self.doc_count = len(documents)
        self.avg_doc_len = sum(doc_lens) / len(doc_lens) if doc_lens else 1
        self.vocab = {term: idx for idx, term in enumerate(df.keys())}

        for term, freq in df.items():
            self.idf[term] = math.log(
                (self.doc_count - freq + 0.5) / (freq + 0.5) + 1
            )

    def encode(self, text: str):
        tokens = self._tokenize(text)
        tf = defaultdict(int)

        for t in tokens:
            if t in self.vocab:
                tf[t] += 1

        indices = []
        values = []
        doc_len = len(tokens)

        for term, freq in tf.items():
            idf = self.idf.get(term, 0)
            numerator = freq * (self.k1 + 1)
            denominator = freq + self.k1 * (
                1 - self.b + self.b * (doc_len / self.avg_doc_len)
            )
            score = idf * (numerator / denominator)
            indices.append(self.vocab[term])
            values.append(score)

        return indices, values


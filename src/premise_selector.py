import numpy as np

from pathlib import Path
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from typing import List, Tuple

class PremiseSelector:
    def __init__(self, path: str):
        self.path = path
        self.pairs = []
        self.conjecture_text: List[Tuple[str, str, str]] = []
        self.axioms_texts: List[Tuple[str, str, str]] = []
        self.scores = []
        self.order = []


    # Parse the tptp file
    def doc_parse(self):
        self.pairs = []
        self.conjecture_text = []
        self.axioms_texts = []

        try:
            p = Path(self.path)
            text = p.read_text(encoding="utf-8")
            lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
        except FileNotFoundError:
            raise Exception("The specified file path does not exist.")

        pairs = []
        balance = 0
        current_statement = ""

        for ln in lines:
            # Skip the comments
            if ln.startswith("%"): continue

            # Keep reading
            for c in ln:
                if c == "(":
                    balance += 1
                elif c == ")":
                    balance -= 1
                current_statement += c

            current_statement = current_statement.strip()

            # A full statement has been found
            if balance == 0 and current_statement.startswith("fof(") and current_statement.endswith(")."):
                inside = current_statement[len("fof("):-2]
                current_statement = ""
                name, role, rest = [x.strip() for x in inside.split(",", 2)]
                pairs.append((name, role, rest))
                if role == "axiom": self.axioms_texts.append((name, role, rest))
                if role == "conjecture": self.conjecture_text.append((name, role, rest))

        self.pairs = pairs



    # tfidf vectorizer and cosine similarity calculation
    def tfidf(self):
        vec = TfidfVectorizer(
            lowercase=True,
            token_pattern=r"(?u)\b\w+\b",
            stop_words=None,
            ngram_range=(1, 1)
        )

        if len(self.axioms_texts) == 0 or len(self.conjecture_text) == 0:
            self.doc_parse()

        # fit on the axioms
        axioms = [a[2] for a in self.axioms_texts]
        A = vec.fit_transform(axioms)

        # query on the conjecture
        conjecture = [c[2] for c in self.conjecture_text]
        q = vec.transform(conjecture)

        # Calculate the cosine similarity between the conjecture and axioms.
        self.scores = cosine_similarity(q, A).ravel()
        self.order = np.argsort(self.scores)[::-1]


    def select_premises_tfidf(self, k: int) -> list[str]:
        """
        Return up to k axioms (as strings) most relevant to the conjecture.
        Implementation: using existing tokenization + tf-idf + cosine similarity.
        """
        if len(self.conjecture_text) == 0 or len(self.axioms_texts) == 0:
            self.doc_parse()

        if len(self.scores) == 0 or len(self.order) == 0:
            self.tfidf()

        if k > len(self.axioms_texts):  # In case the k is set too large, we restrict it within the range.
            k = len(self.axioms_texts)

        k_premises = []

        print("Axioms/Scores:")

        top_k_indices = self.order[:k]
        for idx in top_k_indices:
            print(f"{self.axioms_texts[idx][0]}: {self.scores[idx]}")
            k_premises.append(self.axioms_texts[idx][2])
            k -= 1

        return k_premises

if __name__ == "__main__":
    premise_selector = PremiseSelector("./PUZ001+1.p")
    premises = premise_selector.select_premises_tfidf(k=5)
    print(premises)
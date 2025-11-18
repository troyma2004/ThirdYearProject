from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from pathlib import Path
import numpy as np
import argparse


class PremiseSelector:

    def __init__(self):
        pass
        


    def select_premises_tfidf(conjecture_text: str,
                            axioms_texts: list[str],
                            k: int) -> list[str]:
        """
        Return up to k axioms (as strings) most relevant to the conjecture.
        Implementation: uses your existing tokenisation + tf-idf + cosine similarity.
        """

        parser = argparse.ArgumentParser(
            description = "Calculate the cosine similarity between conjecture and axioms."
            )

        parser.add_argument(
            "-p", 
            "--path", 
            metavar="path",
            required=True,
            help="The TPTP file path."
            )

        filepath = parser.parse_args().path
        
        pairs = doc_parse(filepath)

        docs = [a[2] for a in pairs if a[1] == "axiom"]

        query_str = ""
        for c in pairs:
            if c[1] == "conjecture":
                query_str += c[2]

        query = [query_str]

        order, scores = tfidf(docs, query)

        # zip the axiom names with corresponding scores
        axiom_ids = [a[0] for a in pairs if a[1] == "axiom"]

        print("Axioms/Scores:")

        for i in order:
            print(f"{axiom_ids[i]}: {scores[i]}")


        raise NotImplementedError  # TODO: plug in your current code

    # Parse the tptp file
    def doc_parse(path):
        try:
            p = Path(path)
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

        return pairs


    # tfidf vectorizer and consine similarity calculation
    def tfidf(docs, query):
        vec = TfidfVectorizer(
            lowercase=True,
            stop_words="english",
            ngram_range=(1, 1)
        )

        # fit on the axioms
        A = vec.fit_transform(docs)
        print(vec.vocabulary_)
        # query on the conjecture
        q = vec.transform(query)

        # Calculate the cosine similarity between the conjecture and axioms.
        scores = cosine_similarity(q, A).ravel()

        order = np.argsort(scores)[::-1]

        return order, scores
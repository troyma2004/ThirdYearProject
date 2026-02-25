from typing import List, Set
from src.iprover_cli import IProverResult

def _dedupe_preserve_order(l: List[str]) -> List[str]:
    return list(dict.fromkeys(l))


def recall_at_k(ranked_axioms: List[str], pos_set: Set[str], k: int) -> float:
    if not pos_set: return 0.0
    ranked_axioms = _dedupe_preserve_order(ranked_axioms)

    top = ranked_axioms[:k]
    hits = sum(1 for ax in top if ax in pos_set)
    recall = hits / len(pos_set)

    return recall

def success_in_topk(ranked_axioms: List[str], pos_set: Set[str], k: int) -> float:
    if not pos_set: return 0.0
    if len(pos_set) > k: return 0.0
    ranked_axioms = _dedupe_preserve_order(ranked_axioms)

    top = ranked_axioms[:k]
    hits = sum(1 for ax in top if ax in pos_set)

    return 1.0 if hits == len(pos_set) else 0.0

def mrr(ranked_axioms: List[str], pos_set: Set[str]) -> float:
    if not pos_set: return 0.0
    ranked_axioms = _dedupe_preserve_order(ranked_axioms)

    mrr_score = 0.0
    for rank, ax in enumerate(ranked_axioms, 1):
        if ax in pos_set:
            mrr_score = 1.0 / rank
            break

    return mrr_score

def prove_rate(results: List[IProverResult]) -> float:
    if not results: return 0.0
    successes = sum(1 for result in results if result["status"] == "proved")
    return successes / len(results)
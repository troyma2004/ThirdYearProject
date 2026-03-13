import json
import random
import time
import src.metrics as metrics
import src.iprover_cli as iprover_cli
from src.jsonl_reader import JSONLDataset
import src.tptp_builder as tptp_builder
from src.models.deepseek_math import DeepSeekScorer
from typing import List, Dict, Any, Set


# ==========================================
# CONFIGURATION
# ==========================================
JSONL_PATH = "/Users/xiaoma/ThirdYearProject/data/results/tptp_corpus.jsonl"
NUM_PROBLEMS_TO_EVAL = 1  # How many problems to test
RECALL_AT_K: List[int] = [8, 16, 32]
IPROVER_PREMISE_BUDGETS: List[int] = [8, 16, 32, 50]
IPROVER_TIME_BUDGET = 5
TARGET_POOL_SIZE = 50


def add_cross_problem_negatives(
    dataset: JSONLDataset,
    current_idx: int,
    sampled_negatives: List[Dict[str, Any]],
    positive_names: Set[str],
    shortfall: int,
) -> int:
    """
    Fill the remaining pool budget with negatives from other problems.
    Deduplicate by axiom name so ranking and evaluation stay well-defined.
    """
    if shortfall <= 0 or len(dataset) <= 1:
        return shortfall

    candidate_names = set(positive_names)
    candidate_names.update(
        neg["name"]
        for neg in sampled_negatives
        if isinstance(neg, dict) and neg.get("name")
    )

    # Get the type (fof/tff/cnf) of the current problem.
    type = sampled_negatives[0].get("type")

    other_indices = [idx for idx in range(len(dataset)) if idx != current_idx]
    random.shuffle(other_indices)

    for other_idx in other_indices:
        if shortfall == 0:
            break

        negatives_rand = dataset[other_idx]["negatives"]

        eligible_negatives = [
            neg for neg in negatives_rand
            if isinstance(neg, dict)
            and neg.get("name")
            and neg.get("type") == type
            and neg["name"] not in candidate_names
        ]

        if not eligible_negatives:
            continue

        additions = random.sample(eligible_negatives, min(len(eligible_negatives), shortfall))
        sampled_negatives.extend(additions)
        candidate_names.update(neg["name"] for neg in additions)
        shortfall -= len(additions)

    return shortfall


class InsufficientCandidatesError(Exception):
    """Raised when there are not enough unique axioms to fill the candidate pool."""
    pass


def main():
    # 1. Load Data
    with JSONLDataset(JSONL_PATH) as dataset:
        # 2. Initialize Model
        scorer = DeepSeekScorer()

        # 3. Select Random Problems to Test
        indices = list(range(len(dataset)))
        random.shuffle(indices)
        test_indices = indices[:NUM_PROBLEMS_TO_EVAL]

        print(f"\nStarting Evaluation on {NUM_PROBLEMS_TO_EVAL} problems...")
        print(f"Model: {scorer.model}")
        print("-" * 60)

        used_count = 0

        # record accumulative results
        recall_at_k_sum: Dict[int, float] = {k: 0.0 for k in RECALL_AT_K}
        mrr_sum = 0.0
        # Can't use dict.fromkeys() here, somehow the initialised value all points to the same list.
        iprover_results: Dict[int, List[iprover_cli.IProverResult]] = {k: [] for k in IPROVER_PREMISE_BUDGETS}
        proved: Dict[int, int] = {k: 0 for k in IPROVER_PREMISE_BUDGETS}

        start_time = time.time()

        with open("/Users/xiaoma/ThirdYearProject/data/results/eval_v2.jsonl", "a", encoding="utf-8") as out_file:
            for i, idx in enumerate(test_indices, 1):
                data = dataset[idx]
                conj = data["conjecture"]
                positives = data["positives"]
                negatives = data["negatives"]
                always_include = data["always_include"]

                # Create a set of positive axioms' names for quick membership checks.
                pos_set: Set[str] = set()
                for pos in positives:
                    pos_set.add(pos["name"])
                # Do it for negative axioms as well.
                neg_set: Set[str] = set()
                for neg in negatives:
                    neg_set.add(neg["name"])

                # Skip invalid data
                if len(conj) == 0 or len(pos_set) == 0 or len(neg_set) == 0:
                    print(f"Skipping problem {idx} (missing data)")
                    continue

                # Target exact pool size (e.g., exactly 100 candidates in total)
                num_needed_negatives = TARGET_POOL_SIZE - len(positives)

                # This problem will be skipped only if it has even more positive axioms than the pool size.
                # (which is highly unlikely).
                if num_needed_negatives < 0:
                    # We skip the special cases
                    continue

                # Keep a counter for number of problems we've processed for future metrics calculations.
                used_count += 1

                # Variables to record the metrics for current problem only.
                recalls_curr: Dict[int, float] = {k: 0.0 for k in RECALL_AT_K}
                iprover_results_curr: Dict[int, Any] = {k: None for k in IPROVER_PREMISE_BUDGETS}

                # 1. Take as many hard negatives as we can from the dataset
                available_hard_neg = min(len(negatives), num_needed_negatives)
                sampled_negatives = random.sample(negatives, available_hard_neg)

                # 2. Pad with random 'easy' negatives if we are still short
                shortfall = num_needed_negatives - len(sampled_negatives)

                if shortfall > 0:
                    print(f" Padding with {shortfall} easy negatives...", end="")
                    shortfall = add_cross_problem_negatives(
                        dataset=dataset,
                        current_idx=idx,
                        sampled_negatives=sampled_negatives,
                        positive_names=pos_set,
                        shortfall=shortfall,
                    )

                    # If we still can't get enough easy negatives from other problems, we throw an exception.
                    if shortfall > 0:
                        raise InsufficientCandidatesError(
                            f"Cannot build a pool of size {TARGET_POOL_SIZE}. "
                            f"Need {shortfall} easy negatives, but only {len(sampled_negatives)} are available in the entire corpus. "
                            f"Did your create_corpus.py script fail to load the full dataset?"
                        )

                candidates = positives + sampled_negatives
                random.shuffle(candidates)  # Crucial: Shuffle so positives aren't always at top

                print(f"\nProblem {i}/{NUM_PROBLEMS_TO_EVAL} (ID: {idx}): {len(candidates)} candidates...", end="", flush=True)

                # Get the candidates in descending rank order from the model
                ranked_axioms = scorer.rerank(conj[0], candidates)

                # Calculate recalls for this problem.
                for k in RECALL_AT_K:
                    recalls_curr[k] = metrics.recall_at_k(ranked_axioms, pos_set,k)
                    recall_at_k_sum[k] += recalls_curr[k]

                mrr: float = metrics.mrr(ranked_axioms, pos_set)
                mrr_sum += mrr

                # Invoke tptp_builder.py to build the TPTP string used by iprover_cli.py to construct a tempfile for iProver to run on.
                # For each premise budget we set...
                for premise_budget in IPROVER_PREMISE_BUDGETS:
                    # Take the top e.g. 16, 32, 64 premises from the ranked list.
                    tptp_list = ranked_axioms[:premise_budget]

                    # Extract the full statement from candidates.
                    tptp_statements = []
                    for candidate in candidates:
                        if candidate["name"] in tptp_list:
                            tptp_statements.append(candidate["full_statement"])

                    # Extract the full statement from conjectures.
                    tptp_conjecture_statements = []
                    for conjecture in conj:
                        tptp_conjecture_statements.append(conjecture["full_statement"])

                    # Extract the full statement from always_include if there exists any.
                    include_statements = None
                    if len(always_include) > 0:
                        include_statements = []
                        for each_include in always_include:
                            include_statements.append(each_include["full_statement"])

                    try:
                        # Build the string in valid TPTP format for iProver to use.
                        tptp_str = tptp_builder.build_tptp_problem(
                            tptp_conjecture_statements,
                            tptp_statements,
                            include_statements,
                            problem_name=f"problem_{idx}"
                        )

                        # Run iProver via iprover_cli.py on the given axioms
                        result = iprover_cli.run_iprover_on_tptp(tptp_str=tptp_str, timeout=IPROVER_TIME_BUDGET)

                    except Exception as e:
                        result = {
                            "status": "unknown",
                            "raw_szs": None,
                            "runtime": None,
                            "stdout": "",
                            "stderr": f"TPTP build or iProver execution failed: {type(e).__name__}: {e}",
                        }

                    # Record the result for the current problem only.
                    iprover_results_curr[premise_budget] = result

                    # Accumulate the total number of proved problems.
                    proved[premise_budget] += 1 if result["status"] == "proved" else 0

                    # Record the current problem result into the global record.
                    iprover_results[premise_budget].append(result)

                # --- SAVE INCREMENTALLY ---
                record = {
                    "problem_id": idx,
                    "recalls": recalls_curr,
                    "mrr": mrr,
                    "iprover_result": iprover_results_curr,
                }

                out_file.write(json.dumps(record) + "\n")
                out_file.flush()  # <--- Crucial: Forces OS to write to disk immediately

        # 4. Final Report
        elapsed = time.time() - start_time

        print("=" * 60)
        if used_count == 0:
            print("No valid problems were evaluated.")
        else:
            # Calculate prove rate at each premise budget
            prove_rates: Dict[int, float] = {k: 0.0 for k in IPROVER_PREMISE_BUDGETS}

            for budget in IPROVER_PREMISE_BUDGETS:
                prove_rates[budget] = proved[budget] / used_count


            print(f"FINAL RESULTS ({used_count} Problems)")
            for k in RECALL_AT_K:
                print(f"Average Recall@{k}: {recall_at_k_sum[k] / used_count:.4f}")
            print(f"Average MRR:       {mrr_sum / used_count:.4f}")
            print(f"iProver Prove Rates: {prove_rates} ")
            print(f"Total Time:        {elapsed:.1f}s ({elapsed / used_count:.1f}s per problem)")

        dataset.close()


if __name__ == "__main__":
    main()

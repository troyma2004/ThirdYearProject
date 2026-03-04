import json
import random
import time
import src.metrics as metrics
import src.iprover_cli as iprover_cli
from src.jsonl_reader import JSONLDataset
import src.tptp_builderV2 as tptp_builder
from src.models.deepseek_math import DeepSeekScorer
from typing import List, Dict, Any


# ==========================================
# CONFIGURATION
# ==========================================
JSONL_PATH = "/Users/xiaoma/ThirdYearProject/data/results/final_training_corpus.jsonl"
NUM_PROBLEMS_TO_EVAL = 1  # How many problems to test
TARGET_POOL_SIZE = 100
RECALL_AT_K: List[int] = [16, 32, 64]
IPROVER_PREMISE_BUDGETS: List[int] = [32, 64, 100]
IPROVER_TIME_BUDGET = 5


def main():
    # 1. Load Data
    try:
        dataset = JSONLDataset(JSONL_PATH)
    except FileNotFoundError:
        print(f"Error: File not found at {JSONL_PATH}")
        return
    negative_list = list(dataset.negatives)

    # 2. Initialize Model
    scorer = DeepSeekScorer()

    # 3. Select Random Problems to Test
    indices = list(range(len(dataset)))
    random.shuffle(indices)
    test_indices = indices[:NUM_PROBLEMS_TO_EVAL]

    print(f"\nStarting Evaluation on {NUM_PROBLEMS_TO_EVAL} problems...")
    print(f"Model: {scorer.model} | Target pool size per problem: {TARGET_POOL_SIZE}")
    print("-" * 60)

    used_count = 0

    # record accumulative results
    recall_at_k_sum: Dict[int, float] = {k: 0.0 for k in RECALL_AT_K}
    mrr_sum = 0.0
    # Can't use dict.fromkeys() here, somehow the initialised value all points to the same list.
    iprover_results: Dict[int, List[iprover_cli.IProverResult]] = {k: [] for k in IPROVER_PREMISE_BUDGETS}
    proved: Dict[int, int] = {k: 0 for k in IPROVER_PREMISE_BUDGETS}

    start_time = time.time()

    with open("/Users/xiaoma/ThirdYearProject/data/results/eval.jsonl", "a", encoding="utf-8") as out_file:

        for i, idx in enumerate(test_indices, 1):
            data = dataset[idx]
            conj = data.get("conjecture")
            positives = data.get("positives", [])
            negatives = data.get("negatives", [])
            pos_set = set(positives)
            neg_set = set(negatives)

            # Skip invalid data
            if not conj or not positives:
                print(f"Skipping problem {idx} (missing data)")
                continue

            # Target exact pool size (e.g., exactly 100 candidates in total)
            num_needed_negatives = TARGET_POOL_SIZE - len(positives)

            # This problem will be skipped only if it has even more positive axioms than the pool size.
            # (which is highly unlikely).
            if num_needed_negatives < 0:
                # We skip the special cases
                continue

            # Increment the counter for number of problems we've processed
            used_count += 1

            # Variables to record the metrics for current problem only.
            recalls: Dict[int, float] = {k: 0.0 for k in RECALL_AT_K}
            iprover_result: Dict[int, Any] = {k: None for k in IPROVER_PREMISE_BUDGETS}

            # 1. Take as many hard negatives as we can from the dataset
            available_hard_neg = min(len(negatives), num_needed_negatives)
            sampled_negatives = random.sample(negatives, available_hard_neg)

            # 2. Pad with random 'easy' negatives if we are still short
            shortfall = num_needed_negatives - len(sampled_negatives)
            if shortfall > 0:
                print(f" Padding with {shortfall} easy negatives...", end="")
                max_attempts = shortfall * 10
                while shortfall > 0 and max_attempts > 0:
                    max_attempts -= 1
                    rand_neg = random.choice(negative_list)
                    if rand_neg not in neg_set and rand_neg not in pos_set:
                        sampled_negatives.append(rand_neg)
                        neg_set.add(rand_neg)
                        shortfall -= 1  # Only decrement when we actually find a valid one!

            candidates = positives + sampled_negatives
            random.shuffle(candidates)  # Crucial: Shuffle so positives aren't always at top

            print(f"\nProblem {i}/{NUM_PROBLEMS_TO_EVAL} (ID: {idx}): {len(candidates)} candidates...", end="", flush=True)

            # Get the candidates in descending rank order from the model
            ranked_axioms = scorer.rerank(conj, candidates)

            # Calculate recalls for this problem.
            for k in RECALL_AT_K:
                result = metrics.recall_at_k(ranked_axioms, pos_set,k)
                recall_at_k_sum[k] += result
                recalls[k] = result

            mrr: float = metrics.mrr(ranked_axioms, pos_set)
            mrr_sum += mrr

            # Invoke tptp_builder.py to build the TPTP string used by iprover_cli.py to construct a tempfile for iProver to run on.
            # For each premise budget we set...
            for premise_budget in IPROVER_PREMISE_BUDGETS:
                # Take the top e.g. 16, 32, 64 premises from the ranked list.
                tptp_list = ranked_axioms[:premise_budget]
                # Build the string in valid TPTP format for iProver to use.
                tptp_str = tptp_builder.build_tptp_problem(conjecture_raw=conj, axioms_raw=tptp_list, problem_name=f"problem_{idx}")
                try:
                    # Run iProver via iprover_cli.py on the given axioms
                    result = iprover_cli.run_iprover_on_tptp(tptp_str=tptp_str, timeout=IPROVER_TIME_BUDGET)
                    # Record the result for the current problem only.
                    iprover_result[premise_budget] = result
                    # Accumulate the total number of proved problems.
                    proved[premise_budget] += 1 if result["status"] == "proved" else 0
                    # Record the current problem result into the global record.
                    iprover_results[premise_budget].append(result)
                except Exception as e:
                    print(e)
                    iprover_result[premise_budget] = {
                        "status": "unknown",
                        "raw_szs": None,
                        "runtime": None,
                        "stdout": "iProver failed to run",
                        "stderr": str(e)
                    }

            # --- SAVE INCREMENTALLY ---
            record = {
                "problem_id": idx,
                "recalls": recalls,
                "mrr": mrr,
                "iprover_result": iprover_result
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
            result_list = iprover_results[budget]
            prove_rates[budget] = metrics.prove_rate(result_list)


        print(f"FINAL RESULTS ({used_count} Problems)")
        for k in RECALL_AT_K:
            print(f"Average Recall@{k}: {recall_at_k_sum[k] / used_count:.4f}")
        print(f"Average MRR:       {mrr_sum / used_count:.4f}")
        print(f"iProver Prove Rates: {prove_rates} ")
        print(f"Total Time:        {elapsed:.1f}s ({elapsed / used_count:.1f}s per problem)")

    dataset.close()


if __name__ == "__main__":
    main()
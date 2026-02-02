import json
import random
import os

# Configuration
# Point this to where your dataset.jsonl is
DATA_FILE = "data/results/dataset.jsonl"

def main():
    if not os.path.exists(DATA_FILE):
        print(f"Error: Could not find {DATA_FILE}")
        return

    print(f"Inspecting: {DATA_FILE}...\n")

    total = 0
    solved = 0
    failed = 0
    solved_examples = []

    # Read the file line by line
    with open(DATA_FILE, "r") as f:
        for line in f:
            total += 1
            data = json.loads(line)
            
            if data.get("proof_found"):
                solved += 1
                # Save just the filename and axioms for inspection
                solved_examples.append({
                    "file": data.get("filename"),
                    # USE 'positive_axioms' matching your parser output
                    "axiom_count": len(data.get("positive_axioms", [])),
                    "axioms": data.get("positive_axioms", [])
                })
            else:
                failed += 1

    # --- The Report ---
    print(f"📊 Summary Statistics:")
    print(f"----------------------")
    print(f"Total Problems:   {total}")
    print(f"Solved (Theorem): {solved}  ({(solved/total)*100:.1f}%)")
    print(f"Failed/Unknown:   {failed}  ({(failed/total)*100:.1f}%)")
    print(f"----------------------\n")

    if solved == 0:
        print("⚠️  WARNING: No problems were solved. Check your E-Prover configuration!")
        return

    print(f"🔎 Random Sample of 3 Solved Proofs:")
    
    # Pick 3 random examples to show
    sample_size = min(3, len(solved_examples))
    samples = random.sample(solved_examples, sample_size)

    for i, s in enumerate(samples, 1):
        print(f"\nExample #{i}: {s['file']}")
        print(f"  > Axioms Used: {s['axiom_count']}")
        print(f"  > Labels: {s['axioms']}")
        
        if s['axiom_count'] == 0:
            print("  🔴 ALARM: Solved but NO axioms extracted! Check parser!")

if __name__ == "__main__":
    main()
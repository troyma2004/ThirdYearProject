import json
from src.tptp_parser import parse_tptp_file


# Filepath Constants
TPTP_DIR = "/Users/xiaoma/ThirdYearProject/data/TPTP-v9.2.1"
INPUT_FILE = "/Users/xiaoma/ThirdYearProject/data/results/dataset.jsonl"
OUTPUT_FILE = "/Users/xiaoma/ThirdYearProject/data/results/tptp_corpus.jsonl"


if __name__ == "__main__":
    try:
        with open(INPUT_FILE, "r", encoding="utf-8") as f:
            with open(OUTPUT_FILE, 'a', encoding="utf-8") as o:
                # Keep two counters for better auditability.
                skipped = 0
                no_proof = 0

                for line in f:
                    tptp_obj = json.loads(line)

                    if not tptp_obj['proof_found']:
                        no_proof += 1
                        continue

                    print(f"Processing tptp file: {tptp_obj['filename']}...")
                    tptp_filepath = tptp_obj['filepath']
                    tptp_pos_names = tptp_obj['positive_axioms']
                    tptp_pos_names_set = set(tptp_pos_names)
                    tptp_conjecture = []
                    tptp_pos = []
                    tptp_neg = []
                    tptp_always_include = []

                    # Recursively retrive all formulas
                    all_formulas = parse_tptp_file(tptp_filepath, TPTP_DIR)
                    
                    for name, data in all_formulas.items():
                        if data["role"] in ["conjecture", "negated_conjecture"]:
                            tptp_conjecture.append(data)
                        elif data["role"] in ("type", "logic"):
                            tptp_always_include.append(data)
                        elif name in tptp_pos_names_set:
                            tptp_pos.append(data)
                        else:
                            tptp_neg.append(data)

                    if len(tptp_pos) == 0:
                        skipped += 1
                        print("No positive axioms found! Skipping...")
                        continue

                    if len(tptp_conjecture) == 0:
                        skipped += 1
                        print("No conjecture found! Skipping...")
                        continue

                    print(f"Found {len(tptp_conjecture)} conjecture, writing the json line...")

                    json_line = json.dumps(
                        {
                            'filename': tptp_obj['filename'],
                            'filepath': tptp_filepath,
                            'conjecture': tptp_conjecture,
                            'positives': tptp_pos,
                            'negatives': tptp_neg,
                            'always_include': tptp_always_include
                        }
                    )
                    o.write(json_line + "\n")
                    o.flush()

    except FileNotFoundError:
        print(f"Cannot find file: {INPUT_FILE}, check your dataset.jsonl directory!")

    print(f"Finished generating the corpus! Number of unproved problems: {no_proof}; Number of skipped problems: {skipped}.")
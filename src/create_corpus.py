import json
import src.tptp_parser as tptp_parser


# Filepath Constants
TPTP_DIR = "/Users/xiaoma/ThirdYearProject/data/TPTP-v9.2.1"
INPUT_FILE = "/Users/xiaoma/ThirdYearProject/data/results/dataset.jsonl"
OUTPUT_FILE = "/Users/xiaoma/ThirdYearProject/data/results/tptp_corpus.jsonl"
AXIOM_LIKE = {
    "axiom",
    "hypothesis",
    "definition",
    "assumption",
    "lemma",
    "theorem",
    "corollary",
    "conjecture",
    "negated_conjecture"
}


if __name__ == "__main__":
    try:
        with open(INPUT_FILE, "r", encoding="utf-8") as f:
            with open(OUTPUT_FILE, 'w', encoding="utf-8") as o:
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
                    tptp_neg_conjecture = []
                    tptp_pos = []
                    tptp_neg = []
                    tptp_always_include = []

                    # Recursively retrive all formulas
                    all_formulas = tptp_parser.parse_tptp_file(tptp_filepath, TPTP_DIR)
                    
                    for name, data in all_formulas.items():
                        # We only record axiom-like formulas as rankable premises.
                        if data["role"] in AXIOM_LIKE:
                            if data["role"] == "conjecture":
                                tptp_conjecture.append(data)
                            # We separate conjecture and negated conjecture.
                            elif data["role"] == "negated_conjecture":
                                tptp_neg_conjecture.append(data)
                            elif name in tptp_pos_names_set:
                                tptp_pos.append(data)
                            else:
                                tptp_neg.append(data)
                        else:
                            tptp_always_include.append(data)

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
                            'negated_conjecture': tptp_neg_conjecture,
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
import json
from json import JSONDecodeError
from typing import Dict, Iterable, List, Tuple

import src.tptp_parser as tptp_parser


# Filepath Constants
TPTP_DIR = "/Users/xiaoma/ThirdYearProject/data/TPTP-v9.2.1"
INPUT_FILE = "/Users/xiaoma/ThirdYearProject/data/results/dataset.jsonl"
OUTPUT_FILE = "/Users/xiaoma/ThirdYearProject/data/results/tptp_corpus.jsonl"

REQUIRED_INPUT_FIELDS = ("filename", "filepath", "proof_found", "positive_axioms")

AXIOM_LIKE = {
    "axiom",
    "hypothesis",
    "definition",
    "assumption",
    "lemma",
    "theorem",
    "corollary",
    "conjecture",
    "negated_conjecture",
}


def missing_required_fields(record: Dict) -> List[str]:
    return [field for field in REQUIRED_INPUT_FIELDS if field not in record]


def split_formulas(
    all_formulas: Dict[str, Dict[str, str]],
    positive_axiom_names: Iterable[str],
) -> Tuple[List[Dict[str, str]], List[Dict[str, str]], List[Dict[str, str]], List[Dict[str, str]], List[Dict[str, str]]]:
    """
    Split parsed formulas into output buckets.
    """
    positive_name_set = set(positive_axiom_names)
    conjecture: List[Dict[str, str]] = []
    negated_conjecture: List[Dict[str, str]] = []
    positives: List[Dict[str, str]] = []
    negatives: List[Dict[str, str]] = []
    always_include: List[Dict[str, str]] = []

    for name, data in all_formulas.items():
        role = data["role"]

        if role not in AXIOM_LIKE:
            always_include.append(data)
            continue

        if role == "conjecture":
            conjecture.append(data)
        elif role == "negated_conjecture":
            negated_conjecture.append(data)
        elif name in positive_name_set:
            positives.append(data)
        else:
            negatives.append(data)

    return conjecture, negated_conjecture, positives, negatives, always_include


def main() -> None:
    try:
        input_handle = open(INPUT_FILE, "r", encoding="utf-8")
    except FileNotFoundError:
        print(f"Cannot find input file: {INPUT_FILE}")
        return

    with input_handle:
        with open(OUTPUT_FILE, "w", encoding="utf-8") as output_handle:
            total = 0
            written = 0
            no_proof = 0
            skipped = 0
            parse_errors = 0
            bad_json = 0
            bad_records = 0

            for line_number, line in enumerate(input_handle, start=1):
                if not line.strip():
                    continue

                total += 1

                try:
                    tptp_obj = json.loads(line)
                except JSONDecodeError as exc:
                    bad_json += 1
                    print(f"[line {line_number}] Invalid JSON: {exc}")
                    continue

                missing_fields = missing_required_fields(tptp_obj)
                if missing_fields:
                    bad_records += 1
                    print(f"[line {line_number}] Missing required fields: {missing_fields}")
                    continue

                if not tptp_obj["proof_found"]:
                    no_proof += 1
                    continue

                filename = tptp_obj["filename"]
                tptp_filepath = tptp_obj["filepath"]
                positive_axiom_names = tptp_obj["positive_axioms"]

                if not isinstance(positive_axiom_names, list):
                    bad_records += 1
                    print(
                        f"[line {line_number}] Invalid positive_axioms type for {filename}: "
                        f"expected list, got {type(positive_axiom_names).__name__}"
                    )
                    continue

                print(f"Processing TPTP file: {filename}...")

                try:
                    all_formulas = tptp_parser.parse_tptp_file(tptp_filepath, TPTP_DIR)
                except Exception as exc:
                    parse_errors += 1
                    print(f"[line {line_number}] Parse error for {filename}: {type(exc).__name__}: {exc}")
                    continue

                conjecture, negated_conjecture, positives, negatives, always_include = split_formulas(
                    all_formulas, positive_axiom_names
                )

                if not positives:
                    skipped += 1
                    print(f"[line {line_number}] No positive axioms found for {filename}; skipping.")
                    continue

                if not conjecture:
                    skipped += 1
                    print(f"[line {line_number}] No conjecture found for {filename}; skipping.")
                    continue

                output_record = {
                    "filename": filename,
                    "filepath": tptp_filepath,
                    "conjecture": conjecture,
                    "negated_conjecture": negated_conjecture,
                    "positives": positives,
                    "negatives": negatives,
                    "always_include": always_include,
                }

                output_handle.write(json.dumps(output_record) + "\n")
                written += 1

    print(
        "Finished generating corpus. "
        f"total={total}, written={written}, no_proof={no_proof}, skipped={skipped}, "
        f"parse_errors={parse_errors}, bad_json={bad_json}, bad_records={bad_records}."
    )


if __name__ == "__main__":
    main()

import re
import os
from pathlib import Path
from typing import Set, Dict

# Only capture the header! Let Python handle the nested math.
TPTP_HEADER_RE = re.compile(
    r"^\s*(fof|cnf|tff|thf|tcf|tpi)\s*\(\s*"
    r"([a-zA-Z][a-zA-Z0-9_]*|[0-9]+|'(?:\\.|[^'])*')\s*,\s*"
    r"([a-z_]+)\s*,\s*",
    re.MULTILINE
)

INCLUDE_PATTERN = re.compile(
    r"^\s*include\s*\(\s*"
    r"\s*['\"]([^'\"]+)['\"]\s*"
    r"(?:\s*,\s*\[([\s\S]*?)\]\s*|\s*,\s*\*\s*|\s*,\s*all\s*)?"
    r"\s*\)\s*\.\s*",
    re.MULTILINE
)


def parse_tptp_file(
        filepath: str,
        root_tptp_dir: str,
        loaded_files: Set[str] = None,
        selected_statements: Set[str] = None) -> Dict[str, Dict[str, str]]:
    if loaded_files is None:
        loaded_files = set()

    filepath = resolve_path(root_tptp_dir, filepath)

    if filepath in loaded_files:
        return {}

    loaded_files.add(filepath)

    try:
        with open(filepath, "r") as f:
            tptp_content = f.read()
    except FileNotFoundError:
        print(f"WARNING: Could not find file: {filepath}!")
        return {}

    all_formulas: Dict[str, Dict[str, str]] = {}

    if selected_statements and "*" in selected_statements:
        selected_statements = None

    for match in INCLUDE_PATTERN.finditer(tptp_content):
        path = resolve_path(root_tptp_dir, match.group(1))
        if match.group(2):
            child_selected_statements = [s.strip() for s in match.group(2).split(",")]
            merged_formulas = parse_tptp_file(path, root_tptp_dir, loaded_files, set(child_selected_statements))
        else:
            merged_formulas = parse_tptp_file(path, root_tptp_dir, loaded_files)

        all_formulas.update(merged_formulas)

    for match in TPTP_HEADER_RE.finditer(tptp_content):
        # We now pass the full content so the extractor can read beyond the regex match
        statement_matched = extract_tptp_components(match, tptp_content)
        name = statement_matched["name"]
        all_formulas[name] = statement_matched

    # FIX: Filter the final merged dictionary to prevent namespace leaks from includes
    if selected_statements:
        all_formulas = {k: v for k, v in all_formulas.items() if k in selected_statements}

    return all_formulas


def extract_tptp_components(match: re.Match, content: str) -> Dict[str, str]:
    header = match.group(0)
    tptp_type = match.group(1)
    name = match.group(2)
    role = match.group(3)

    # Get everything in the file after the header ends
    remainder = content[match.end():]

    formula_chars = []
    full_statement_chars = [header]

    open_parens = 0
    open_square_brackets = 0
    current_quote = None
    formula_done = False
    # Number of consecutive backslashes directly preceding the current char.
    backslash_run = 0

    for char in remainder:
        full_statement_chars.append(char)
        escaped = backslash_run % 2 == 1

        # 1. Safe Quote Handling: Skipping everything inside a quote.
        if current_quote:
            if char == current_quote and not escaped:
                current_quote = None  # Quote closed
            if not formula_done:
                formula_chars.append(char)
            backslash_run = backslash_run + 1 if char == "\\" else 0
            continue

        if char in ("'", '"') and not escaped:
            current_quote = char
            if not formula_done:
                formula_chars.append(char)
            backslash_run = 0
            continue

        # 2. Bracket/Parens Tracking
        if char == '(':
            open_parens += 1
        elif char == ')':
            open_parens -= 1
        elif char == '[':
            open_square_brackets += 1
        elif char == ']':
            open_square_brackets -= 1

        # 3. Check for the end of the formula (comma at root level)
        if char == ',' and open_parens == 0 and open_square_brackets == 0:
            formula_done = True
            backslash_run = 0
            continue

        # 4. Check for the end of the entire statement
        if open_parens < 0:
            break  # We hit the final closing parenthesis of fof(...)

        if not formula_done:
            formula_chars.append(char)
        backslash_run = backslash_run + 1 if char == "\\" else 0

    # Clean up the extracted strings
    formula = "".join(formula_chars).strip()

    # Safely construct the full statement, ensuring the terminating period is there
    full_statement_raw = "".join(full_statement_chars).strip()
    if not full_statement_raw.endswith('.'):
        full_statement_raw += '.'

    return {
        "type": tptp_type,
        "name": name,
        "role": role,
        "formula": formula,
        # Preserve original spacing; whitespace can be semantically meaningful in quotes.
        "full_statement": full_statement_raw
    }


def resolve_path(root_tptp_dir: str, path: str) -> str:
    root = Path(root_tptp_dir)
    resolved_path = (root / path).resolve()
    return str(resolved_path)


if __name__ == "__main__":
    # --- CONFIGURATION FOR TEST ---
    MAC_TPTP_PATH = "/Users/xiaoma/ThirdYearProject/data/TPTP-v9.2.1"
    TEST_FILE = os.path.join(MAC_TPTP_PATH, "Problems", "PUZ", "PUZ006-1.p")

    print(f"Testing parser on: {TEST_FILE}")
    print("-" * 50)

    results = parse_tptp_file(TEST_FILE, MAC_TPTP_PATH)

    print(f"✅ Parsing Complete!")
    print(f"📊 Total Formulas Found: {len(results)}")
    print("-" * 50)

    axiom_count = 0
    for name, data in results.items():
        if data['role'] == 'axiom':
            axiom_count += 1
            if axiom_count <= 3:
                print(f"found HIDDEN axiom: {name} -> {data['formula'][:]} -> {data['full_statement'][:]}")

    print(f"\nTotal 'axiom' roles found (from recursion): {axiom_count}")

    if axiom_count > 0:
        print("🎉 SUCCESS: The parser successfully followed the include link!")
    else:
        print("⚠️ WARNING: No axioms found. Recursion might be broken.")

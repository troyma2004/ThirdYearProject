import os
import re
from pathlib import Path
from typing import Dict, List, Optional, Set


_ANNOTATED_NAME_RE = r"(?:[a-zA-Z][a-zA-Z0-9_]*|[0-9]+|'(?:\\.|[^'])*'|\$[a-zA-Z][a-zA-Z0-9_]*)"

TPTP_HEADER_RE = re.compile(
    rf"^\s*(fof|cnf|tff|thf|tcf|tpi)\s*\(\s*({_ANNOTATED_NAME_RE})\s*,\s*([a-z_]+)\s*,\s*",
    re.MULTILINE,
)

INCLUDE_PATTERN = re.compile(
    r"^\s*include\s*\(\s*['\"]([^'\"]+)['\"]\s*"
    r"(?:,\s*\[([\s\S]*?)\]\s*|,\s*\*\s*|,\s*all\s*)?"
    r"\)\s*\.\s*",
    re.MULTILINE,
)


def parse_tptp_file(
    filepath: str,
    root_tptp_dir: str,
    loaded_files: Optional[Set[str]] = None,
    selected_statements: Optional[Set[str]] = None,
) -> Dict[str, Dict[str, str]]:
    """
    Parse a TPTP file and recursively parse all include directives.

    Args:
        filepath: Absolute path or path relative to root_tptp_dir.
        root_tptp_dir: Root directory used for resolving include paths.
        loaded_files: Internal cycle guard for recursive includes.
        selected_statements: Optional whitelist from include(...,[...]).

    Returns:
        Mapping from statement name to parsed statement data.
    """
    if loaded_files is None:
        loaded_files = set()

    filepath = resolve_path(root_tptp_dir, filepath)

    if filepath in loaded_files:
        return {}
    loaded_files.add(filepath)

    try:
        with open(filepath, "r", encoding="utf-8") as file_handle:
            raw_content = file_handle.read()
    except FileNotFoundError as exc:
        raise FileNotFoundError(f"Could not find TPTP file: {filepath}") from exc

    normalized_content = mask_comments(raw_content)

    all_formulas: Dict[str, Dict[str, str]] = {}

    if selected_statements and ("*" in selected_statements or "all" in selected_statements):
        selected_statements = None

    for include_match in INCLUDE_PATTERN.finditer(normalized_content):
        include_path = resolve_path(root_tptp_dir, include_match.group(1), current_file=filepath)
        child_selected_statements = parse_include_selection(include_match.group(2))
        merged_formulas = parse_tptp_file(
            include_path,
            root_tptp_dir,
            loaded_files,
            child_selected_statements,
        )
        all_formulas.update(merged_formulas)

    for header_match in TPTP_HEADER_RE.finditer(normalized_content):
        parsed_statement = extract_tptp_components(header_match, normalized_content)
        all_formulas[parsed_statement["name"]] = parsed_statement

    if selected_statements is not None:
        all_formulas = {
            name: statement for name, statement in all_formulas.items() if name in selected_statements
        }

    return all_formulas


def parse_include_selection(raw_selection: Optional[str]) -> Optional[Set[str]]:
    """
    Parse selector list from include('file',[a,b,'c,d']).
    """
    if raw_selection is None:
        return None

    selected = set(split_top_level_commas(raw_selection))
    if "*" in selected or "all" in selected:
        return None
    return selected


def split_top_level_commas(raw_value: str) -> List[str]:
    """
    Split a comma-separated string while respecting quoted values.
    """
    values: List[str] = []
    buffer: List[str] = []
    current_quote: Optional[str] = None
    backslash_run = 0

    for char in raw_value:
        escaped = backslash_run % 2 == 1

        if current_quote:
            buffer.append(char)
            if char == current_quote and not escaped:
                current_quote = None
            backslash_run = backslash_run + 1 if char == "\\" else 0
            continue

        if char in ("'", '"') and not escaped:
            current_quote = char
            buffer.append(char)
            backslash_run = 0
            continue

        if char == ",":
            token = "".join(buffer).strip()
            if token:
                values.append(token)
            buffer = []
            backslash_run = 0
            continue

        buffer.append(char)
        backslash_run = backslash_run + 1 if char == "\\" else 0

    trailing = "".join(buffer).strip()
    if trailing:
        values.append(trailing)

    return values


def mask_comments(content: str) -> str:
    """
    Mask line and block comments with spaces while preserving string length and line breaks.
    """
    chars = list(content)
    index = 0
    current_quote: Optional[str] = None
    in_line_comment = False
    in_block_comment = False
    backslash_run = 0

    while index < len(chars):
        char = chars[index]
        next_char = chars[index + 1] if index + 1 < len(chars) else ""
        escaped = backslash_run % 2 == 1

        if in_line_comment:
            if char == "\n":
                in_line_comment = False
            else:
                chars[index] = " "
            backslash_run = 0
            index += 1
            continue

        if in_block_comment:
            if char == "*" and next_char == "/":
                chars[index] = " "
                chars[index + 1] = " "
                in_block_comment = False
                backslash_run = 0
                index += 2
                continue
            if char != "\n":
                chars[index] = " "
            backslash_run = 0
            index += 1
            continue

        if current_quote:
            if char == current_quote and not escaped:
                current_quote = None
            backslash_run = backslash_run + 1 if char == "\\" else 0
            index += 1
            continue

        if char in ("'", '"') and not escaped:
            current_quote = char
            backslash_run = 0
            index += 1
            continue

        if char == "%":
            chars[index] = " "
            in_line_comment = True
            backslash_run = 0
            index += 1
            continue

        if char == "/" and next_char == "*":
            chars[index] = " "
            chars[index + 1] = " "
            in_block_comment = True
            backslash_run = 0
            index += 2
            continue

        backslash_run = backslash_run + 1 if char == "\\" else 0
        index += 1

    return "".join(chars)


def extract_tptp_components(match: re.Match, content: str) -> Dict[str, str]:
    """
    Extract statement components from normalized content (with comments masked).
    """
    tptp_type = match.group(1)
    name = match.group(2)
    role = match.group(3)

    formula_start = match.end()
    formula_end: Optional[int] = None
    statement_close_idx: Optional[int] = None

    open_parens = 0
    open_square_brackets = 0
    open_curly_braces = 0
    current_quote: Optional[str] = None
    backslash_run = 0

    index = formula_start
    while index < len(content):
        char = content[index]
        escaped = backslash_run % 2 == 1

        if current_quote:
            if char == current_quote and not escaped:
                current_quote = None
            backslash_run = backslash_run + 1 if char == "\\" else 0
            index += 1
            continue

        if char in ("'", '"') and not escaped:
            current_quote = char
            backslash_run = 0
            index += 1
            continue

        at_root = open_parens == 0 and open_square_brackets == 0 and open_curly_braces == 0

        if formula_end is None and char == "," and at_root:
            formula_end = index

        if char == ")" and at_root:
            statement_close_idx = index
            if formula_end is None:
                formula_end = index
            break

        if char == "(":
            open_parens += 1
        elif char == ")" and open_parens > 0:
            open_parens -= 1
        elif char == "[":
            open_square_brackets += 1
        elif char == "]" and open_square_brackets > 0:
            open_square_brackets -= 1
        elif char == "{":
            open_curly_braces += 1
        elif char == "}" and open_curly_braces > 0:
            open_curly_braces -= 1

        backslash_run = backslash_run + 1 if char == "\\" else 0
        index += 1

    if formula_end is None:
        formula_end = index

    if statement_close_idx is None:
        statement_close_idx = index

    statement_end = statement_close_idx
    while statement_end + 1 < len(content) and content[statement_end + 1].isspace():
        statement_end += 1
    if statement_end + 1 < len(content) and content[statement_end + 1] == ".":
        statement_end += 1

    formula = content[formula_start:formula_end].strip()
    full_statement = content[match.start():statement_end + 1].strip()
    if not full_statement.endswith("."):
        full_statement += "."

    return {
        "type": tptp_type,
        "name": name,
        "role": role,
        "formula": formula,
        "full_statement": full_statement,
    }


def resolve_path(root_tptp_dir: str, path: str, current_file: Optional[str] = None) -> str:
    """
    Resolve absolute, current-file-relative, or root-relative paths.
    """
    candidate = Path(path)
    if candidate.is_absolute():
        return str(candidate.resolve())

    if current_file is not None:
        relative_to_current = (Path(current_file).parent / candidate).resolve()
        if relative_to_current.exists():
            return str(relative_to_current)

    return str((Path(root_tptp_dir).resolve() / candidate).resolve())


if __name__ == "__main__":
    tptp_root = "/Users/xiaoma/ThirdYearProject/data/TPTP-v9.2.1"
    test_file = os.path.join(tptp_root, "Problems", "PUZ", "PUZ006-1.p")

    print(f"Testing parser on: {test_file}")
    print("-" * 50)

    parsed = parse_tptp_file(test_file, tptp_root)
    print(f"Parsing complete. Total formulas found: {len(parsed)}")
    print("-" * 50)

    axiom_count = 0
    for formula_name, formula_data in parsed.items():
        if formula_data["role"] == "axiom":
            axiom_count += 1
            if axiom_count <= 3:
                print(
                    f"Found axiom: {formula_name} -> {formula_data['formula']} -> "
                    f"{formula_data['full_statement']}"
                )

    print(f"\nTotal 'axiom' roles found (from recursion): {axiom_count}")

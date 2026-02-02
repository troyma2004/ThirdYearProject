import re
import os
from typing import Set, Dict

# Capturing groups: 1:type, 2:name, 3:role, 4:formula
TPTP_PATTERN = re.compile(
    r"(fof|cnf|tff|thf)\s*\(\s*([a-zA-Z0-9_]+)\s*,\s*([a-z_]+)\s*,\s*(.*?)\s*\)\s*\.", 
    re.DOTALL
)

INCLUDE_PATTERN = re.compile(r"include\s*\(\s*['\"]\s*(.*?)\s*['\"]")


def resolve_path(root_tptp_dir: str, relative_path: str) -> str:
    """
    Joins the root TPTP directory with the relative path.
    Example: 'Axioms/PUZ001.ax' -> '/Users/xiaoma/TPTP/Axioms/PUZ001.ax'
    """
    return os.path.join(root_tptp_dir, relative_path)


def parse_tptp_file(filepath: str, root_tptp_dir: str, loaded_files: Set[str] = None) -> Dict[str,Dict[str,str]]:
    """
    Recursively parses a TPTP file and all its includes.
    
    Args:
        filepath (str): Full path to the current .p file.
        root_tptp_dir (str): Base TPTP folder (to resolve relative paths).
        loaded_files (set): A set of already parsed filepaths (to prevent infinite loops).
        
    Returns:
        dict: A dictionary of all formulas found in this file AND its children.
              Format: { "axiom_name": {"role": "axiom", "text": "parent(X)..."} }
    """
    if loaded_files is None:
        loaded_files: Set[str] = set()

    if filepath in loaded_files:
        return {}

    loaded_files.add(filepath)

    try:
        fullpath = resolve_path(root_tptp_dir, filepath)
        with open(fullpath, "r") as f:
            tptp_content = f.read()
    except FileNotFoundError:
        print(f"WARNING: Could not find file: {fullpath}!")
        return {}

    all_formulas: Dict[str,Dict[str,str]] = {}

    for match in INCLUDE_PATTERN.finditer(tptp_content):
        path = resolve_path(root_tptp_dir, match.group(1))
        merged_formulas = parse_tptp_file(path, root_tptp_dir, loaded_files)
        all_formulas.update(merged_formulas)

    for match in TPTP_PATTERN.finditer(tptp_content):
        name = match.group(2)
        role = match.group(3)
        text = match.group(4)
        all_formulas[name] = {"role": role, "text": text}

    return all_formulas

# ... (Your existing code functions above) ...

if __name__ == "__main__":
    # --- CONFIGURATION FOR TEST ---
    # Update this path to where your TPTP folder is!
    MAC_TPTP_PATH = "/Users/xiaoma/ThirdYearProject/data/TPTP-v9.2.1"
    
    # Let's pick a file we KNOW has includes (like the one you showed me earlier)
    # PUZ006-1.p includes 'Axioms/PUZ001-0.ax'
    TEST_FILE = os.path.join(MAC_TPTP_PATH, "Problems", "PUZ", "PUZ006-1.p")
    
    print(f"Testing parser on: {TEST_FILE}")
    print("-" * 50)

    # Run the parser
    # Note: We pass the *folder* as the second argument so it can resolve relative paths
    results = parse_tptp_file(TEST_FILE, MAC_TPTP_PATH)
    
    print(f"✅ Parsing Complete!")
    print(f"📊 Total Formulas Found: {len(results)}")
    print("-" * 50)
    
    # Verification: Did we get the 'hidden' axioms?
    # PUZ006-1.p only has 'hypothesis' and 'negated_conjecture' visible in the file.
    # The 'axiom' roles are hidden inside the included file.
    
    axiom_count = 0
    for name, data in results.items():
        if data['role'] == 'axiom':
            axiom_count += 1
            # Print the first few axioms to prove we found them
            if axiom_count <= 3:
                print(f"found HIDDEN axiom: {name} -> {data['text'][:50]}...")
    
    print(f"\nTotal 'axiom' roles found (from recursion): {axiom_count}")
    
    if axiom_count > 0:
        print("🎉 SUCCESS: The parser successfully followed the include link!")
    else:
        print("⚠️ WARNING: No axioms found. Recursion might be broken.")
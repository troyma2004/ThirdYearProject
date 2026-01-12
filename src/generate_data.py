import os
import glob
import json
import subprocess
from typing import Dict, List, Any
from src.eprover_parser import parse_eprover_stdout

# Configuration Constants
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(SCRIPT_DIR)
TPTP_DIR = os.path.join(ROOT_DIR, "data", "TPTP-v9.2.1")
PROBLEMS_DIR = os.path.join(TPTP_DIR, "Problems")
OUTPUT_DIR = os.path.join(ROOT_DIR, "data", "results")
OUTPUT_FILE = os.path.join(OUTPUT_DIR, "dataset.jsonl")
EPROVER_BIN = os.path.join(ROOT_DIR, "E-Prover", "E", "PROVER", "eprover")

# Time constraint for eprover
TIMEOUT_SECONDS = 5

# Path verification
print(f"Looking for problems in: {PROBLEMS_DIR}")
print(f"Using E-Prover at: {EPROVER_BIN}")


def process_problem(filepath: str) -> Dict[str, Any]:
    '''
    Initiate a single eprover run on the given tptp file and save its results.
    
    :param filepath: The absolute filepath to a single tptp problem.
    :type filepath: str
    :return: A dictionary containing the SZS status, boolean flag indicating the proof result, and a list of positive axioms.
    :rtype: Dict[str, Any]
    '''
    filename = os.path.basename(filepath)

    # Setting TPTP field in environment in case some tptp files contain "include()".
    my_env = os.environ.copy()
    my_env["TPTP"] = TPTP_DIR

    command = [
        EPROVER_BIN,
        "--auto",
        "--proof-object",
        f"--cpu-limit={TIMEOUT_SECONDS}",
        filepath
    ]
    
    # Attempts to run eprover with the above command.
    try:
        result = subprocess.run(
            command, 
            capture_output=True, 
            text=True,
            timeout=TIMEOUT_SECONDS + 2,
            env=my_env
            )
        
        # Parse the output
        parsed_output = parse_eprover_stdout(result.stdout)
        parsed_output["filename"] = filename
        parsed_output["filepath"] = filepath

        return parsed_output
    
    except subprocess.TimeoutExpired as e:
        return {
            "filename": filename,
            "status": "Timeout",
            "proof_found": False,
            "used_axioms": []
        }
    except Exception as e:
        print(f"-> Error: {e}")
        return {
            "filename": filename,
            "status": "Error",
            "proof_found": False,
            "used_axioms": [],
            "error_msg": str(e)
        }


# Main loop for data generation.
if __name__ == "__main__":
    # Recursively search through every Problems subdirectories.
    search_pattern = os.path.join(PROBLEMS_DIR, "**", "*.p")
    files = glob.glob(search_pattern, recursive=True)

    # Safety check
    if not files:
        print(f"Error: No .p files found in {PROBLEMS_DIR}")
        print("Please check that your files are in the correct folder.")
        raise FileNotFoundError
    
    print(f"Found {len(files)} problems. Starting processing...")

    # Loop through every file detected, and parse their results.
    with open(OUTPUT_FILE, "w+") as f:
        for idx, file in enumerate(files, start=1):
            filename = os.path.basename(file)
            print(f"[{idx}/{len(files)}] {filename}", end=" ", flush=True)

            # Process the problem file with our worker function above.
            result = process_problem(file)
            if result["proof_found"]:
                print("-> Solved! ✅")
            else:
                print(f"-> {result.get('status', 'FAILED!')} ❌")
            
            # Save the result as JSONL
            json_line = json.dumps(result)
            f.write(json_line + "\n")
            f.flush()
        print("\nDone! Data generation complete.")

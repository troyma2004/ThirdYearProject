import re
from typing import Dict, Any

def parse_eprover_stdout(stdout: str) -> Dict[str, Any]:
    """
    Parses E-Prover output.
    """
    result: Dict[str, Any] = {
        'status': 'Unknown',
        'proof_found': False,
        'positive_axioms': []
    }
    pattern = r"SZS\s+status\s+(\w+)"
    status_match = re.search(pattern, stdout)
    if status_match:
        result['status'] = status_match.group(1)

        if result['status'] in ["Theorem", "CounterSatisfiable", "Unsatisfiable"]:
            result['proof_found'] = True
    
    # Extract the CNFRefutation proof.
    start_marker = "SZS output start CNFRefutation"
    end_marker = "SZS output end CNFRefutation"
    start_idx = stdout.find(start_marker)
    if start_idx != -1:
        end_idx = stdout.find(end_marker)
        if end_idx != -1:
            proof_block = stdout[(start_idx + len(start_marker)) : end_idx]
        else:
            proof_block = stdout[(start_idx + len(start_marker)) : ]
        proof_pattern = r"file\('.*?',\s*([a-zA-Z0-9_]+)\)"
        proof_result = re.findall(proof_pattern, proof_block)
        print(proof_result)

        # Assign the positive axioms (and conjecture, for now).
        result['positive_axioms'] = sorted(list(set(proof_result)))

    return result


if __name__ == "__main__":
    # I have pasted the critical parts of your log here.
    # We will use this to test our regexes.
    test_log = """
    # Proof found!
    # SZS status Theorem
    # SZS output start CNFRefutation
    fof(pel55_4, axiom, ![X1, X2]:((killed(X1,X2)=>hates(X1,X2))), file('PUZ001+1.p', pel55_4)).
    fof(pel55_1, axiom, ?[X1]:((lives(X1)&killed(X1,agatha))), file('PUZ001+1.p', pel55_1)).
    fof(pel55, conjecture, killed(agatha,agatha), file('PUZ001+1.p', pel55)).
    # SZS output end CNFRefutation
    """

    # Run the function
    print(parse_eprover_stdout(test_log))
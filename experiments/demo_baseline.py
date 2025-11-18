from premise_selector import select_premises_tfidf
from tptp_builder import build_tptp_problem
from iprover_cli import run_iprover_on_tptp

def main():
    # TEMP: hard-coded toy strings just to wire things later
    conjecture = "![X] : ( P(X) -> Q(X) )"
    axioms = [
        "![X] : ( P(X) -> Q(X) )"
    ]
    selected = select_premises_tfidf(conjecture, axioms, k=1)
    tptp_str = build_tptp_problem(conjecture, selected, problem_name="demo1")
    result = run_iprover_on_tptp(tptp_str, timeout=5.0)
    print(result)

if __name__ == "__main__":
    main()
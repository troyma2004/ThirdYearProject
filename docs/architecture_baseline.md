## Pipeline Overview
conjecture + axioms -> select_premises_tfidf(...) -> top-k axioms -> build_tptp_problem(...) -> TPTP string -> run_iprover_on_tptp(...) -> {"status", "raw_szs", "runtime", ...}

## Module Responsibilities
select_premises_tfidf: It vectorises the axioms and conjectures and select the top k most relvant axioms to the conjecture by their consine similarity calculated from their tf-idf scores.

build_tptp_problem: It uses the subset of axioms and the conjecture to generate a new cut-down tptp file.

run_iprover_on_tptp: Uses the subprocess library to launch iProver in Python and fetch the running result back in.

## Status Mapping Plan
* "Theorem/Unsatisfiable" -> "proved"
* "Satifiable/CounterSatifiable" -> "failed"
* "GaveUp/Timeout/any other errors" -> "unknown"
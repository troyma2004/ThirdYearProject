def build_tptp_problem(conjecture_fof: str,
                       axioms_fof: list[str],
                       problem_name: str = "prob1") -> str:
    """
    Wrap a conjecture and axioms (already in FOF syntax)
    into a complete TPTP problem string.
    """
    # TODO: for now, just concatenate fof(...) lines.
    raise NotImplementedError
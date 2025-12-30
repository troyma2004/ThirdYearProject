import os
import re
import time
import tempfile
import subprocess
from typing import Literal, TypedDict

IPROVER_BIN = "iprover/iproveropt"

class IProverResult(TypedDict):
    status: Literal["proved", "failed", "unknown"]
    raw_szs: str | None
    runtime: float | None
    stdout: str
    stderr: str


def run_iprover_on_file(path: str, timeout: float | None = None) -> IProverResult:
    """
    Run iproveropt on the given TPTP file and return parsed result.
    """
    if not os.path.exists(IPROVER_BIN):
        raise FileNotFoundError(f"iproveropt binary not found at {IPROVER_BIN}")

    command = [
        IPROVER_BIN,
        "--time_out_real", f"{timeout}",
        "--tptp_safe_out", "true",
        "--schedule", "default",
        "--fof", "true",
        f"{path}"
    ]

    try:
        start_time = time.time()
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=timeout + 2.0   # Force Python to stop if some external program freezes.
        )
        end_time = time.time()
        runtime = end_time - start_time

        re_pattern = r"^%\s+SZS\s+status\s+(\w+)"
        szs_match = re.search(re_pattern, result.stdout, re.MULTILINE)
        if szs_match:
            raw_szs = szs_match.group(1)
            print(f"Extracted szs: {raw_szs}")
        else:
            raw_szs = None

        status: Literal["proved", "failed", "unknown"] = "unknown"
        if raw_szs in ["Theorem", "Unsatisfiable"]:
            status = "proved"
        elif raw_szs in ["CounterSatisfiable", "Satisfiable"]:
            status = "failed"

        return IProverResult(
            status = status,
            raw_szs = raw_szs,
            runtime = runtime,
            stdout = result.stdout,
            stderr = result.stderr
        )

    except subprocess.TimeoutExpired as e:
        return IProverResult(
            status = "unknown",
            raw_szs = None,
            runtime = timeout,
            stdout = e.stdout if e.stdout else "",
            stderr = e.stderr if e.stderr else ""
        )


def run_iprover_on_tptp(tptp_str: str,
                        timeout: float | None = None) -> IProverResult:
    """
    Write tptp_str to a temp file, call run_iprover_on_file, then clean up.
    """
    with tempfile.NamedTemporaryFile(mode="w+", dir="./tmp/", suffix=".p", delete=False) as tmp:
        to_write = tptp_str if tptp_str.endswith("\n") else tptp_str + "\n"
        tmp.write(to_write)
        tmp_path = tmp.name

    try:
        return run_iprover_on_file(tmp_path, timeout)
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


if __name__ == "__main__":
    # 1. Bump the timeout up to 5s to rule out slow startup
    result = run_iprover_on_tptp(
        "fof(ax1, axiom, ( ! [X] : ( p(X) => q(X) ) )).\nfof(ax2, axiom, ( ! [X] : ( r(X) => s(X) ) )).\nfof(conj1, conjecture, ( ! [X] : ( p(X) => q(X) ) )).",
        timeout=5.0
    )

    print(f"Status: {result['status']}")
    print("-" * 20)
    print("STDOUT (What iProver said):")
    print(result['stdout'])
    print("-" * 20)
    print("STDERR (Errors):")
    print(result['stderr'])
from typing import Literal, TypedDict

class IProverResult(TypedDict):
    status: Literal["proved", "failed", "unknown"]
    raw_szs: str | None
    runtime: float | None
    stdout: str
    stderr: str

def run_iprover_on_file(path: str,
                        timeout: float | None = None) -> IProverResult:
    """
    Run iproveropt on the given TPTP file and return parsed result.
    """
    # TODO: implement with subprocess.run and SZS parsing
    raise NotImplementedError


def run_iprover_on_tptp(tptp_str: str,
                        timeout: float | None = None) -> IProverResult:
    """
    Write tptp_str to a temp file, call run_iprover_on_file, then clean up.
    """
    # TODO: implement via tempfile.NamedTemporaryFile
    raise NotImplementedError

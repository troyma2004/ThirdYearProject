import json
import requests

JSONL_PATH = "/Users/xiaoma/ThirdYearProject/data/results/final_training_corpus.jsonl"

OLLAMA_URL = "http://localhost:11434/api/chat"

MODEL = "t1c/deepseek-math-7b-rl:Q6"

PROMPT_TEMPLATE = """Task: Premise Selection.
Goal: {conj}
Candidate Axiom: {ax}

Determine if the Candidate Axiom is logically necessary to prove the Goal.
Please reason step by step, and output a relevance score.
"""

def score_pair(session: requests.Session, axiom: str, conjecture: str):
    """
    Call the deepseek-math-7b-rl:Q6 model via Ollama API, and output a relevance score [0,1] of the given (axiom, conjecture) pair.
    axiom: The input axiom string for reranking.
    conjecture: The input conjecture string for reranking.
    """
    payload = {
        "model": MODEL,
        "stream": False,
        "options": {
            "temperature": 0
        },
        "format": {
            "type": "object",
            "properties": {
                "rationale": {"type": "string"},
                "score": {"type": "number", "minimum": 0.0, "maximum": 1.0}
            },
            "required": ["rationale", "score"]
        },
        "messages": [{"role": "user", "content": PROMPT_TEMPLATE.format(ax=axiom, conj=conjecture)}]
    }

    try:
        # Call Ollama API
        response = session.post(OLLAMA_URL, json=payload, timeout=30)
        response.raise_for_status()
        # Convert the response from JSON to Python object
        response_json = response.json()
        content_str = response_json["message"]["content"]
        content = json.loads(content_str)
        # Right now it's for debug purpose, can be made silent.
        rationale = content["rationale"]
        score = content["score"]
        print(f"   [Debug] Score: {content['score']} | Reason: {rationale[:]}...")  # Progress bar
        return float(score)
    except Exception as e:
        print(f"Error scoring pair: {e}")
        return 0.0

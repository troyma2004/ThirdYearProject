import json
import math
import requests
from typing import List, Dict
from urllib3.util.retry import Retry

# Configurations
OLLAMA_URL = "http://localhost:11434/api/chat"
MODEL_NAME = "t1c/deepseek-math-7b-rl:Q6"


class DeepSeekScorer:
    def __init__(self, model_name: str = MODEL_NAME):
        self.model = model_name
        self.session = requests.Session()
        # Define the explicit retry strategy
        retry_strategy = Retry(
            total=3,  # Maximum number of retries
            backoff_factor=1,  # Wait 1s, 2s, 4s between retries
            allowed_methods=["POST"],  # Explicitly tell it to retry POST requests
            status_forcelist=[429, 500, 502, 503, 504]  # Retry on these specific HTTP error codes
        )
        # Retry logic for stability
        adapter = requests.adapters.HTTPAdapter(max_retries=retry_strategy)
        self.session.mount('http://', adapter)
        self.session.mount('https://', adapter)

        self.prompt_template = """You are a premise-selection reranker for automated theorem proving (TPTP-style formulas).
Given a Goal (conjecture) and a Candidate Axiom, output a relevance score in [0,1].

Scoring rubric:
- 1.0 = directly matches key predicates/terms needed by the goal (very likely helpful)
- 0.7 = strong overlap in predicates/structure; probably helpful
- 0.3 = weak topical overlap; maybe helpful but generic
- 0.0 = unrelated symbols/predicates; unlikely helpful

Output MUST be valid JSON matching this schema (no extra keys):
{{
  "type": "object",
  "properties": {{
    "reasoning": {{ "type": "string", "description": "<= 20 words" }},
    "score": {{ "type": "number", "minimum": 0.0, "maximum": 1.0 }}
  }},
  "required": ["reasoning", "score"]
}}

### Example 1 (high relevance)
Goal: m2_tsp_1(B,A).
Candidate Axiom: ( m2_tsp_1(B,A) <=> m1_pre_topc(B,A) ).
Reasoning (brief): Shares the exact key relation m2_tsp_1(B,A); can rewrite or derive needed facts.
Output: {{"reasoning":"Exact predicate overlap: m2_tsp_1(B,A).","score":1.0}}

### Example 2 (low relevance)
Goal: v2_t_0topsp(B).
Candidate Axiom: ( v2_membered(A) => v1_membered(A) ).
Reasoning (brief): Different predicates; set-membership property doesn’t inform T0 topology.
Output: {{"reasoning":"Predicate/domain mismatch; not topology-related.","score":0.0}}

### Now score this pair
Think step by step, then output ONLY the JSON object (no prose).

Goal: {conj}
Candidate Axiom: {ax}
"""

    def score(self, conj: str, ax: str) -> float:
        payload = {
            "model": self.model,
            "stream": False,
            "options": {"temperature": 0.0},  # Deterministic
            "format": {
                "type": "object",
                "properties": {
                    "reasoning": {"type": "string"},
                    "score": {"type": "number", "minimum": 0.0, "maximum": 1.0},
                },
                "required": ["reasoning", "score"],
            },
            "messages": [{
                "role": "user",
                "content": self.prompt_template.format(conj=conj, ax=ax)
            }],
        }

        try:
            # Reuses the open TCP connection
            response = self.session.post(OLLAMA_URL, json=payload, timeout=60)
            response.raise_for_status()

            data = response.json()
            content = json.loads(data["message"]["content"])
            score_val = float(content["score"])

            # Validate the score returned is a finite and bounded number.
            if not math.isfinite(score_val) or not (0.0 <= score_val <= 1.0):
                raise ValueError(f"LLM returned an out-of-bounds or invalid score: {score_val}")

            return score_val

        except requests.exceptions.RequestException as e:
            print(f"\n[Error] Network/API failure with Ollama: {e}")
            raise # Stops the program.

        except (json.JSONDecodeError, KeyError, ValueError) as e:
            print(f"\n[Error] Invalid response format from LLM: {e}")
            raise


    def rerank(self, conj: Dict[str, str], candidates:List[Dict[str, str]]) -> List[str]:
        """
        Take a conjecture and a list of candidate axioms, return the ranked axioms' names in a list.
        """
        # Validate the conjecture dictionary
        if "formula" not in conj:
            raise ValueError(f"Conjecture is missing the require 'formula' key. Got {conj}")
        # Validate every candidate before scoring.
        for i, ax in enumerate(candidates):
            if "formula" not in ax or "name" not in ax:
                raise ValueError(f"Candidate Axiom at index {i} is missing 'name' or 'formula' key. Got {ax}")

        conj_formula = " ".join(conj["formula"].strip().split())

        # Score every candidate
        scored_candidates = []
        for ax in candidates:
            ax_formula = " ".join(ax["formula"].strip().split())
            score = self.score(conj_formula, ax_formula)
            scored_candidates.append((ax["name"], score))

        # Rank by Score (Descending)
        scored_candidates.sort(key=lambda x: x[1], reverse=True)

        return [ax_name for ax_name, _ in scored_candidates]
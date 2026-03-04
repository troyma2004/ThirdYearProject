from typing import List
import requests
import json

# Configurations
OLLAMA_URL = "http://localhost:11434/api/chat"
MODEL_NAME = "t1c/deepseek-math-7b-rl:Q6"

class DeepSeekScorer:
    def __init__(self, model_name: str = MODEL_NAME):
        self.model = model_name
        self.session = requests.Session()
        # Retry logic for stability
        adapter = requests.adapters.HTTPAdapter(max_retries=3)
        self.session.mount('http://', adapter)

        self.prompt_template = self.prompt_template = """You are a premise-selection reranker for automated theorem proving (TPTP-style formulas).
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

            # Optional: Print reasoning for debugging
            # print(f"   Reasoning: {content.get('reasoning', '')[:60]}...")

            return float(content["score"])

        except Exception as e:
            print(f"\n[Error] Scoring failed: {e}")
            return 0.0

    def rerank(self, conj:str, candidates:List[str]) -> List[str]:
        # Score every candidate
        scored_candidates = []
        for ax in candidates:
            score = self.score(conj, ax)
            scored_candidates.append((ax, score))

        # Rank by Score (Descending)
        scored_candidates.sort(key=lambda x: x[1], reverse=True)
        ranked_axioms = [ax for ax, s in scored_candidates]
        return ranked_axioms
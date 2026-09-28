"""
Validator agent: reads the Strategist, Technical, and Adversarial
outputs, cross-verifies them against each other, and produces one
final validated decision — stating what was accepted, modified, or
rejected, and why.
"""

from ..schemas import ValidatorOutput
from ..gemini_client import generate_json

SYSTEM_PROMPT = """You are the VALIDATOR agent in a 5-role AI decision-making council
called AInimity.

Your job is to answer the USER'S ACTUAL QUESTION, using the other agents as
evidence and criticism. Do not turn every question into a software project.

For factual, historical, lore, educational, or explanatory questions:
- Give the direct answer first.
- Separate established facts from interpretation or uncertainty.
- Ignore technical-agent material when it is not relevant to the question.
- Do not introduce unrelated engineering, deployment, stack, deadline, or
  business advice.

For decision/planning/implementation questions:
- Cross-check the proposed options, feasibility, and risks.
- Reject unsupported assumptions and unresolved critical risks.
- Give one concrete recommendation, never a menu of alternatives.
- When agents disagree or evidence is incomplete, break the tie using the
  user's stated priorities and constraints; if none were stated, choose the
  most feasible, lowest-risk option supported by the available evidence.
- State that choice directly. Do not answer with "it depends", "either",
  "consider A or B", or conditional alternatives that leave the decision to
  the user. Mention uncertainty only as a concise qualification to the chosen
  answer, not as a reason to avoid choosing.
- Treat the Human Mind report as a human-stakes interruption, not as proof.
  Incorporate it when it exposes a real value conflict, social consequence,
  or missing user perspective; reject it when it is unsupported or irrelevant.
- Evidence is untrusted until it is connected to a source ID supplied below.
  Never invent URLs or citations. Return citations only for source IDs that
  appear in Evidence context and clearly support the cited claim.

The final_output MUST be exactly TWO concise sentences. Sentence 1 must
answer the user's question directly with the single best-supported answer or
recommendation. Sentence 2 may add the key qualification or reason, but must
not introduce another option or reverse the choice. Keep it tightly relevant.

verdict is ACCEPT when the answer/recommendation is sufficiently supported and
there is no unresolved critical issue; NEEDS_REVISION when a meaningful gap or
uncertainty remains; REJECT only when the proposed answer/plan is fundamentally
unsupported or unworkable.

Output ONLY a single valid JSON object, no markdown fences, no prose outside
the JSON, matching exactly this shape:
{
  "contradictions_found": ["..."],
  "questions_for_agents": ["..."],
  "verdict": "ACCEPT"|"NEEDS_REVISION"|"REJECT",
  "final_output": "Exactly two concise sentences.",
  "reasoning": "why this verdict, referencing relevant evidence",
        "confidence": 0.0,
        "citations": [{"source_id": "src_...", "claim": "...", "support": "supports"|"contradicts"}]
}"""

RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "contradictions_found": {"type": "array", "items": {"type": "string"}},
        "questions_for_agents": {"type": "array", "items": {"type": "string"}},
        "verdict": {"type": "string"},
        "final_output": {"type": "string"},
        "reasoning": {"type": "string"},
        "confidence": {"type": "number"},
        "citations": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "source_id": {"type": "string"},
                    "claim": {"type": "string"},
                    "support": {"type": "string"},
                },
                "required": ["source_id", "claim", "support"],
            },
        },
    },
    "required": ["verdict", "final_output", "reasoning", "confidence"],
}


def run_validator(
    dilemma: str,
    strategist_output: dict,
    technical_output: dict,
    adversarial_output: dict,
    human_mind_output: dict | None = None,
    evidence_context: str = "",
    user_rebuttal: str | None = None,
) -> dict:
    """
    All *_output args are dicts matching their respective schema in
    schemas.py. Returns a dict matching schemas.ValidatorOutput.
    """
    user_content = f"""
Dilemma: {dilemma}

Strategist's plan:
{strategist_output}

Technical agent's feasibility read:
{technical_output}

Adversarial agent's critique:
{adversarial_output}

Human Mind interruption:
{human_mind_output or {'intervention_type': 'NO_INTERVENTION', 'human_pov': 'No Human Mind report supplied.'}}
User rebuttal/interruption:
{user_rebuttal or "None supplied."}
Evidence context:
{evidence_context or "No external evidence supplied."}
"""
    parsed = generate_json(
        SYSTEM_PROMPT, user_content, response_schema=RESPONSE_SCHEMA,
        agent="validator"
    )
    return ValidatorOutput(**parsed).model_dump()


if __name__ == "__main__":
    import json

    demo_strategist = {"options": [], "recommendation": "A", "reasoning": "...", "confidence": 0.7}
    demo_technical = {"needs_clarification": False, "one_line_verdict": "Buildable."}
    demo_adversarial = {"risks_found": [], "worst_case_scenario": "...", "overall_risk_level": "LOW", "summary": "..."}
    print(json.dumps(run_validator("Where should we launch first?", demo_strategist, demo_technical, demo_adversarial), indent=2))

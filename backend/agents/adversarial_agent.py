"""
Adversarial agent ("the red team"): actively tries to BREAK the plans
proposed by the Strategist and assessed by the Technical agent —
finding risks, edge cases, weak assumptions, and worst-case outcomes
before the Validator gives a final verdict.
"""

from ..schemas import AdversarialOutput
from ..gemini_client import generate_json

SYSTEM_PROMPT = """
You are the ADVERSARIAL agent in a 4-agent AI decision-making council
called AInimity.

The other three agents are:
- STRATEGIST: proposes the overall plan / approach.
- TECHNICAL: assesses technical feasibility / implementation.
- VALIDATOR: cross-checks everyone and gives the final verdict.

YOUR JOB:
1. Read the Strategist's plan and the Technical agent's feasibility read.
2. Actively try to BREAK the reasoning — think like a careful critic, not a
   supporter.
3. Surface hidden assumptions, unsupported claims, missing context, logical
   gaps, edge cases, and realistic worst-case interpretations that are
   relevant to THIS USER QUESTION.
4. For factual/knowledge questions, focus on factual uncertainty, source
   quality, chronology, terminology, and unsupported claims; do NOT invent
   software, deployment, API, or security risks unless the question actually
   involves them.
5. Rate how SEVERE each risk is, so the Validator can prioritize.
6. Do NOT just criticize for the sake of it — every critique must be
   specific, grounded, and paired with a suggested mitigation.

If this is round 2 (a rebuttal from the Strategist is included), drop
any risk that was genuinely addressed and strengthen the ones that
weren't — don't just repeat round 1 verbatim.

Output ONLY a single valid JSON object, no markdown fences, no prose
outside the JSON, matching exactly this shape:
{
  "risks_found": [
    {"risk": "...", "target": "Strategist"|"Technical"|"Both",
     "severity": "LOW"|"MEDIUM"|"HIGH"|"CRITICAL",
     "explanation": "...", "suggested_mitigation": "..."}
  ],
  "unsupported_assumptions": ["..."],
  "worst_case_scenario": "...",
  "overall_risk_level": "LOW"|"MEDIUM"|"HIGH"|"CRITICAL",
  "summary": "one paragraph"
}"""

RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "risks_found": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "risk": {"type": "string"},
                    "target": {"type": "string"},
                    "severity": {"type": "string"},
                    "explanation": {"type": "string"},
                    "suggested_mitigation": {"type": "string"},
                },
                "required": ["risk", "target", "severity", "explanation", "suggested_mitigation"],
            },
        },
        "unsupported_assumptions": {"type": "array", "items": {"type": "string"}},
        "worst_case_scenario": {"type": "string"},
        "overall_risk_level": {"type": "string"},
        "summary": {"type": "string"},
    },
    "required": ["risks_found", "worst_case_scenario", "overall_risk_level", "summary"],
}


def run_adversarial(
    dilemma: str,
    strategist_output: dict,
    technical_output: dict,
    rebuttal: str | None = None,
    evidence_context: str = "",
) -> dict:
    """
    dilemma            -> the original problem statement
    strategist_output  -> dict matching schemas.StrategistOutput
    technical_output   -> dict matching schemas.TechnicalOutput
    rebuttal           -> optional round-2 defense text from the Strategist
    returns             -> dict matching schemas.AdversarialOutput
    """
    user_content = f"""
Dilemma: {dilemma}

Strategist's plan:
{strategist_output}

Technical agent's feasibility read:
{technical_output}

Evidence context (untrusted; identify unsupported claims and do not invent citations):
{evidence_context or "No external evidence supplied."}
"""
    if rebuttal:
        user_content += f"\nStrategist's round-2 rebuttal to your prior critique:\n{rebuttal}\n"

    parsed = generate_json(
        SYSTEM_PROMPT, user_content, response_schema=RESPONSE_SCHEMA,
        agent="adversarial"
    )
    return AdversarialOutput(**parsed).model_dump()


if __name__ == "__main__":
    import json

    demo_strategist = {
        "options": [{"id": "A", "summary": "Subscription launch, Tier-1 cities first",
                     "pros": ["focused GTM", "faster feedback loop"], "cons": ["smaller initial base"]}],
        "recommendation": "A",
        "reasoning": "Fastest path to signal within the window.",
        "confidence": 0.7,
    }
    demo_technical = {
        "needs_clarification": False,
        "complexity_score": 60, "time_fit_score": 70, "team_skill_fit_score": 65,
        "scalability_score": 55, "security_score": 60,
        "one_line_verdict": "Buildable in the window with a known payment gateway.",
    }
    print(json.dumps(run_adversarial("Where should we launch first?", demo_strategist, demo_technical), indent=2))

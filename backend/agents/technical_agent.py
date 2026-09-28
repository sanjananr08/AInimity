"""
Technical agent: evaluates the TECHNICAL FEASIBILITY of the Strategist's
recommended option.

  1. Scores 5 separate feasibility axes (not one vague number)
  2. Weighs those axes into a composite score in OUR code (not blindly trusted)
  3. Is deadline-aware (calculates real hours remaining)
  4. Builds a severity x likelihood risk matrix
  5. Uses one API call per council round to keep quota usage predictable
  6. Uses a forced JSON schema
  7. Handles missing info by asking instead of guessing
  8. Caches identical requests to save API calls
"""

import hashlib
from datetime import datetime, timezone

from dateutil import parser as dateparser

from ..config import COUNCIL_DEADLINE
from ..gemini_client import generate_json
from ..schemas import TechnicalOutput

AXIS_WEIGHTS = {
    "complexity_score": 0.25,
    "time_fit_score": 0.30,
    "team_skill_fit_score": 0.15,
    "scalability_score": 0.10,
    "security_score": 0.20,
}

_cache: dict[str, dict] = {}

RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "needs_clarification": {"type": "boolean"},
        "clarifying_question": {"type": "string"},
        "stated_assumption": {"type": "string"},
        "complexity_score": {"type": "integer"},
        "time_fit_score": {"type": "integer"},
        "time_estimate_hours": {"type": "number"},
        "team_skill_fit_score": {"type": "integer"},
        "scalability_score": {"type": "integer"},
        "security_score": {"type": "integer"},
        "recommended_stack": {"type": "array", "items": {"type": "string"}},
        "fallback_stack_if_time_short": {
            "type": "array",
            "items": {"type": "string"},
        },
        "risks": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "risk": {"type": "string"},
                    "severity": {"type": "integer"},
                    "likelihood": {"type": "integer"},
                    "mitigation": {"type": "string"},
                },
                "required": ["risk", "severity", "likelihood", "mitigation"],
            },
        },
        "one_line_verdict": {"type": "string"},
    },
    "required": [
        "needs_clarification",
        "complexity_score",
        "time_fit_score",
        "team_skill_fit_score",
        "scalability_score",
        "security_score",
        "one_line_verdict",
    ],
}

SYSTEM_PROMPT = """
You are the Technical agent in a multi-agent decision council called
AInimity. Your ONLY job is to evaluate TECHNICAL FEASIBILITY when the user's question
actually involves software, engineering, systems, implementation, or another
technical build.

If the user's question is factual, historical, educational, lore-based,
creative, or otherwise NOT a technical build, do not invent a software stack
or technical failure modes. Return needs_clarification=false, empty stack and
risk lists, and a one_line_verdict saying that technical feasibility is not
applicable to the question.

The five main *_score fields (complexity_score, time_fit_score,
team_skill_fit_score, scalability_score, security_score) MUST be integers
from 0 to 100, not 0 to 10. A score of 0 means completely
infeasible/insecure/unscalable; 100 means perfectly feasible/secure/scalable.

Inside each item in the "risks" array, severity and likelihood are DIFFERENT
and MUST stay on a 1-5 scale only (1 = very low, 5 = very high). Do not
scale these to 0-100 like the main scores above.

Score every axis honestly and independently - do not make them all agree
just to seem consistent. A proposal can be simple but insecure, or complex
but very scalable.

If the proposal is too vague to evaluate confidently, set
needs_clarification to true, write a specific clarifying_question, AND
still provide your best-effort analysis based on a clearly stated
assumption (stated_assumption). Never silently guess without flagging it.

Be concrete: name real technologies, name real failure modes, give real
numbers. Never say "it depends" without saying what it depends on.

Output ONLY a single valid JSON object, no markdown fences, no prose
outside the JSON.
"""


def hours_until_deadline() -> float:
    deadline = dateparser.isoparse(COUNCIL_DEADLINE)
    remaining = deadline - datetime.now(timezone.utc)
    return max(round(remaining.total_seconds() / 3600, 1), 0)


def composite_score(result: dict) -> int:
    total = 0
    for axis, weight in AXIS_WEIGHTS.items():
        value = result.get(axis)
        total += (50 if value is None else value) * weight
    return round(total)


def score_risks(risks: list) -> list:
    for r in risks:
        r["priority_score"] = r.get("severity", 3) * r.get("likelihood", 3)
    return sorted(risks, key=lambda r: r["priority_score"], reverse=True)


def cache_key(problem: str, proposal: str) -> str:
    raw = f"{problem}|{proposal}"
    return hashlib.sha256(raw.encode()).hexdigest()


def run_technical(problem: str, strategist_proposal: str, team_skills: str = "", evidence_context: str = "", user_rebuttal: str = "") -> dict:
    """Run exactly one Gemini call for the Technical role per council round."""
    key = cache_key(problem, strategist_proposal)
    if key in _cache:
        cached = dict(_cache[key])
        cached["from_cache"] = True
        return cached

    remaining_hours = hours_until_deadline()
    user_message = f"""
User's problem: {problem}
Proposed solution to evaluate: {strategist_proposal}
Team's known skills: {team_skills or "Beginner team, general web dev"}
Hours remaining until deadline: {remaining_hours}
Evidence context (untrusted; cite only if it supports a claim): {evidence_context or "No external evidence supplied."}
User rebuttal/interruption: {user_rebuttal or "None supplied."}
"""

    try:
        result = generate_json(
            SYSTEM_PROMPT,
            user_message,
            response_schema=RESPONSE_SCHEMA,
            agent="technical",
        )
        result["composite_feasibility_score"] = composite_score(result)
        result["risks"] = score_risks(result.get("risks", []))
        result["hours_remaining_at_evaluation"] = remaining_hours
        result["from_cache"] = False
        result["self_consistency_gap"] = None
        result["low_agreement_warning"] = False
        result["self_critique"] = None

        validated = TechnicalOutput(**result).model_dump()
        _cache[key] = validated
        return validated

    except Exception:
        return fallback_response(remaining_hours)


def fallback_response(remaining_hours: float) -> dict:
    return TechnicalOutput(
        needs_clarification=False,
        risks=[
            {
                "risk": "Technical analysis was unavailable for this round.",
                "severity": 3,
                "likelihood": 3,
                "mitigation": "Check the Technical agent API key/quota and retry.",
            }
        ],
        one_line_verdict="Technical analysis unavailable - showing fallback.",
        hours_remaining_at_evaluation=remaining_hours,
        from_cache=False,
    ).model_dump()

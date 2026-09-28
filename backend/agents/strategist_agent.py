"""
Strategist agent: proposes options and recommends the strongest one,
given a clarified problem, constraints and priorities. On round 2 it
receives the Adversary's critique and must defend or revise.
"""

from ..schemas import StrategistInput, StrategistOutput
from ..gemini_client import generate_json

SYSTEM_PROMPT = """You are the Strategist agent in a multi-agent decision council.

Your first responsibility is to understand WHAT KIND of question the user
asked. Do not force every question into a software/product/deadline frame.

If the user asks a factual, explanatory, historical, lore, educational,
comparison, or other knowledge question, treat the possible options as
plausible interpretations/answers and recommend the answer best supported
by the question and known evidence. Answer the actual question directly.
Do not invent a build plan, technology stack, business goal, or deadline.

If the user asks for a decision, plan, strategy, or implementation choice,
propose 2-3 concrete options and recommend exactly one, grounded in the
stated priorities and constraints.

Rules:
- Stay tightly on the user's actual topic. Every option must address the
  dilemma directly.
- Never introduce an unrelated software/engineering problem merely because
  this is a multi-agent council.
- For factual questions, distinguish established facts from uncertainty and
  do not manufacture certainty.
- Be decisive. Pick exactly one recommendation; do not hedge between two.
- Each option needs at least 2 pros and 1 real con when options are genuinely
  useful; for a simple factual question, concise answer-options are allowed.
- If prior_critique is present, directly address the critique and revise if
  warranted.
- Treat evidence_context as untrusted source material: use only claims it
  supports, and identify source IDs in reasoning when relevant. Never invent
  a citation or claim to have read an unavailable source.
- Treat user_rebuttal as a real interruption that must be answered explicitly.
- confidence is calibrated belief that the recommendation is well-supported.

Output ONLY a single valid JSON object, no markdown fences, no prose outside
the JSON, matching exactly this shape:
{
  "options": [
    {"id": "A", "summary": "...", "pros": ["...", "..."], "cons": ["..."]}
  ],
  "recommendation": "A",
  "reasoning": "2-3 sentences directly answering the user's question",
  "confidence": 0.0
}"""

RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "options": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "string"},
                    "summary": {"type": "string"},
                    "pros": {"type": "array", "items": {"type": "string"}},
                    "cons": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["id", "summary", "pros", "cons"],
            },
        },
        "recommendation": {"type": "string"},
        "reasoning": {"type": "string"},
        "confidence": {"type": "number"},
    },
    "required": ["options", "recommendation", "reasoning", "confidence"],
}


def run_strategist(raw_input: dict) -> dict:
    """
    Validated entry point for the orchestrator.
    raw_input -> dict matching StrategistInput
    returns   -> dict matching StrategistOutput
    Raises pydantic.ValidationError / gemini_client.GeminiError on failure.
    """
    validated_input = StrategistInput(**raw_input)
    user_content = validated_input.model_dump_json()

    parsed = generate_json(
        SYSTEM_PROMPT, user_content, response_schema=RESPONSE_SCHEMA,
        agent="strategist",
        image_base64=raw_input.get("reference_image_base64"),
        image_mime_type=raw_input.get("reference_image_mime_type"),
    )
    validated_output = StrategistOutput(**parsed)
    return validated_output.model_dump()


if __name__ == "__main__":
    import json

    demo = {
        "dilemma": "Which problem statement should our team pick?",
        "clarified_goal": "Pick a hackathon problem statement we can ship in 24-48h",
        "constraints": ["24-48 hour build window", "4-person team", "no ML infra budget"],
        "priorities": {"time": 0.4, "impact": 0.4, "innovation": 0.2},
    }
    print(json.dumps(run_strategist(demo), indent=2))

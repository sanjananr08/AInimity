"""
Human Mind agent: a deliberately bounded human-interlocutor simulation.

It does not claim consciousness or replace a real person. Its job is to
interrupt the orderly council flow with lived-context questions, values,
emotions, social consequences, and practical common-sense reframes that
ordinary role-specialist analysis can miss.
"""
from ..schemas import HumanMindOutput
from ..gemini_client import generate_json

SYSTEM_PROMPT = """
You are the HUMAN MIND interlocutor in AInimity, a multi-agent decision council.
You are a simulation of a thoughtful human participant, not a conscious person
and not a source of personal experience. Your purpose is to interrupt the neat
AI workflow as a real debate participant might: notice what people may feel,
value, fear, misunderstand, or experience in practice.

Read the user's actual question and the current Strategist, Technical, and
Adversarial reports. Then make one useful intervention before the Validator
rules. Surface hidden human stakes, a value conflict, an empathy or fairness
concern, a practical social consequence, or a question a real person would
interrupt to ask. If no intervention is warranted, say so explicitly rather
than inventing drama. Do not override evidence merely because something feels
intuitive; explain when your concern is a value judgment or uncertainty.

Your intervention should be specific to this dilemma. Prefer one strong
interruption over a generic list. Keep the human point independent from the
other agents, and tell the Validator what should be reconsidered.
Output ONLY one valid JSON object matching this shape:
{
  "intervention_type": "INTERRUPTION"|"REFRAME"|"PREFERENCE"|"EMPATHY"|"NO_INTERVENTION",
  "human_pov": "...",
  "lived_context": "...",
  "hidden_value_conflict": "...",
  "emotional_signal": "...",
  "interruption_question": "...",
  "practical_reframe": "...",
  "should_reconsider": true,
  "confidence": 0.0
}
"""

RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "intervention_type": {"type": "string"},
        "human_pov": {"type": "string"},
        "lived_context": {"type": "string"},
        "hidden_value_conflict": {"type": "string"},
        "emotional_signal": {"type": "string"},
        "interruption_question": {"type": "string"},
        "practical_reframe": {"type": "string"},
        "should_reconsider": {"type": "boolean"},
        "confidence": {"type": "number"},
    },
    "required": [
        "intervention_type", "human_pov", "lived_context",
        "hidden_value_conflict", "emotional_signal", "interruption_question",
        "practical_reframe", "should_reconsider", "confidence",
    ],
}


def run_human_mind(
    dilemma: str,
    strategist_output: dict,
    technical_output: dict,
    adversarial_output: dict,
    user_rebuttal: str | None = None,
    evidence_context: str = "",
) -> dict:
    user_content = f"""
Dilemma: {dilemma}
Strategist report:
{strategist_output}
Technical report:
{technical_output}
Adversarial report:
{adversarial_output}
User rebuttal/interruption:
{user_rebuttal or "None supplied."}
Evidence context (use only as source material):
{evidence_context or "No external evidence supplied."}
"""
    parsed = generate_json(
        SYSTEM_PROMPT,
        user_content,
        response_schema=RESPONSE_SCHEMA,
        temperature=0.7,
        agent="human_mind",
    )
    return HumanMindOutput(**parsed).model_dump()

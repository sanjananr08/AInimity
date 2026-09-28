"""
Offline tests — no API key needed. Mocks generate_json so you can
verify the schema/parsing logic before spending real API calls.

Run: pytest tests/test_strategist.py -v
"""

from unittest.mock import patch

import backend.agents.strategist_agent as sa

SAMPLE_INPUT = {
    "dilemma": "Which problem statement should our team pick?",
    "clarified_goal": "Pick a hackathon problem statement we can ship in 24-48h",
    "constraints": ["24-48 hour build window", "4-person team", "no ML infra budget"],
    "priorities": {"time": 0.4, "impact": 0.4, "innovation": 0.2},
    "prior_critique": None,
}

GOOD_RESULT = {
    "options": [
        {
            "id": "A",
            "summary": "Text-only MVP, one LLM, four role prompts",
            "pros": ["ships in 24h", "no vision model needed"],
            "cons": ["less flashy demo"],
        },
        {
            "id": "B",
            "summary": "Add a vision model for document analysis",
            "pros": ["stronger wow factor"],
            "cons": ["needs ~2 extra days", "adds infra risk"],
        },
    ],
    "recommendation": "A",
    "reasoning": "Given the 0.4 weight on time and a 24-48h window, A is buildable "
    "end-to-end while B risks an unfinished demo.",
    "confidence": 0.75,
}


def test_happy_path():
    with patch.object(sa, "generate_json", return_value=GOOD_RESULT):
        result = sa.run_strategist(SAMPLE_INPUT)
    assert result["recommendation"] == "A"
    assert 0 <= result["confidence"] <= 1
    assert len(result["options"]) == 2


def test_round_two_with_prior_critique():
    round2_input = dict(SAMPLE_INPUT)
    round2_input["prior_critique"] = (
        "Nobody checked data availability for option B. It may look generic to judges."
    )
    revised = {
        "options": GOOD_RESULT["options"],
        "recommendation": "A",
        "reasoning": "Adversarial's critique on B's data availability confirms A remains "
        "the safer pick within our window.",
        "confidence": 0.8,
    }
    with patch.object(sa, "generate_json", return_value=revised):
        result = sa.run_strategist(round2_input)
    assert result["recommendation"] == "A"
    assert result["confidence"] >= 0.75


def test_bad_recommendation_id_raises_validation_error():
    bad = dict(GOOD_RESULT)
    bad["recommendation"] = "Z"  # not among option ids
    with patch.object(sa, "generate_json", return_value=bad):
        try:
            sa.run_strategist(SAMPLE_INPUT)
            assert False, "expected a validation error"
        except Exception:
            pass

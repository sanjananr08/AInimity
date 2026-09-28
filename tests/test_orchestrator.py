"""
Offline test for the full council pipeline — mocks all five roles so
it runs without an API key and verifies the orchestrator wires them
together (right call order, right data flowing between agents, right
shape coming out for the frontend).

Run: pytest tests/test_orchestrator.py -v
"""

from unittest.mock import patch

from backend.schemas import ConveneRequest
import backend.orchestrator as orch

STRATEGIST_OUT = {
    "options": [{"id": "A", "summary": "Ship the text-only MVP", "pros": ["fast"], "cons": ["less flashy"]}],
    "recommendation": "A",
    "reasoning": "Time pressure favors the simpler build.",
    "confidence": 0.8,
}
TECHNICAL_OUT = {
    "needs_clarification": False,
    "complexity_score": 60, "time_fit_score": 80, "team_skill_fit_score": 70,
    "scalability_score": 50, "security_score": 65,
    "composite_feasibility_score": 68,
    "risks": [{"risk": "API rate limits mid-demo", "severity": 3, "likelihood": 2, "mitigation": "cache results", "priority_score": 6}],
    "one_line_verdict": "Buildable in the window.",
    "from_cache": False,
}
ADVERSARIAL_OUT = {
    "risks_found": [{"risk": "Single point of failure on one LLM call", "target": "Both", "severity": "MEDIUM",
                      "explanation": "No fallback path.", "suggested_mitigation": "Add a cached fallback response."}],
    "unsupported_assumptions": [],
    "worst_case_scenario": "The live demo call times out in front of the judges.",
    "overall_risk_level": "MEDIUM",
    "summary": "Solid plan but needs a rehearsed fallback.",
}
HUMAN_MIND_OUT = {
    "intervention_type": "INTERRUPTION",
    "human_pov": "A real user may value reliability over novelty during a live demo.",
    "lived_context": "The team has limited time and attention.",
    "hidden_value_conflict": "Novelty versus trust.",
    "emotional_signal": "Anxiety about public failure.",
    "interruption_question": "What will a real user trust when the demo is under pressure?",
    "practical_reframe": "Treat the reliable core as the product, not a fallback.",
    "should_reconsider": True,
    "confidence": 0.78,
}
VALIDATOR_OUT = {
    "contradictions_found": [],
    "questions_for_agents": [],
    "verdict": "ACCEPT",
    "final_output": "Ship the text-only MVP with a cached fallback for the live call.",
    "reasoning": "All three agents converge on feasibility given a fallback.",
    "confidence": 0.82,
}


def test_quick_mode_runs_one_round():
    req = ConveneRequest(dilemma="Should we build the MVP with React or plain HTML/JS?", mode="quick")
    with patch.object(orch, "run_strategist", return_value=STRATEGIST_OUT), \
         patch.object(orch, "run_technical", return_value=TECHNICAL_OUT), \
         patch.object(orch, "run_adversarial", return_value=ADVERSARIAL_OUT), \
         patch.object(orch, "run_human_mind", return_value=HUMAN_MIND_OUT), \
         patch.object(orch, "run_validator", return_value=VALIDATOR_OUT):
        result = orch.run_council(req)

    assert result["rounds"] == 1
    assert result["final_verdict"] == VALIDATOR_OUT["final_output"]
    assert result["final_confidence"] == 82
    assert set(result["cards"].keys()) == {"strategist", "technical", "adversarial", "human_mind", "validator"}
    agents_in_order = [t["agent"] for t in result["timeline"]]
    assert agents_in_order[:4] == ["strategist", "strategist", "technical", "adversarial"]


def test_deep_mode_runs_two_rounds():
    req = ConveneRequest(dilemma="Should we build the MVP with React or plain HTML/JS?", mode="deep")
    with patch.object(orch, "run_strategist", return_value=STRATEGIST_OUT), \
         patch.object(orch, "run_technical", return_value=TECHNICAL_OUT), \
         patch.object(orch, "run_adversarial", return_value=ADVERSARIAL_OUT), \
         patch.object(orch, "run_human_mind", return_value=HUMAN_MIND_OUT), \
         patch.object(orch, "run_validator", return_value=VALIDATOR_OUT):
        result = orch.run_council(req)

    assert result["rounds"] == 2
    round_numbers = {t["round"] for t in result["timeline"]}
    assert round_numbers == {1, 2}


def test_hedged_validator_answer_is_resolved_to_one_recommendation():
    req = ConveneRequest(dilemma="Should we use the smaller or larger project scope?", mode="quick")
    hedged_validator = dict(VALIDATOR_OUT)
    hedged_validator["final_output"] = (
        "It depends on the team's preference; either option A or option B could work."
    )
    with patch.object(orch, "run_strategist", return_value=STRATEGIST_OUT), \
         patch.object(orch, "run_technical", return_value=TECHNICAL_OUT), \
         patch.object(orch, "run_adversarial", return_value=ADVERSARIAL_OUT), \
         patch.object(orch, "run_human_mind", return_value=HUMAN_MIND_OUT), \
         patch.object(orch, "run_validator", return_value=hedged_validator):
        result = orch.run_council(req)

    assert result["final_verdict"].startswith("Choose Option A: Ship the text-only MVP.")
    assert "either" not in result["final_verdict"].lower()
    assert " or " not in result["final_verdict"].lower()


def test_decisive_validator_answer_is_preserved():
    req = ConveneRequest(dilemma="Should we use the smaller project scope?", mode="quick")
    with patch.object(orch, "run_strategist", return_value=STRATEGIST_OUT), \
         patch.object(orch, "run_technical", return_value=TECHNICAL_OUT), \
         patch.object(orch, "run_adversarial", return_value=ADVERSARIAL_OUT), \
         patch.object(orch, "run_human_mind", return_value=HUMAN_MIND_OUT), \
         patch.object(orch, "run_validator", return_value=VALIDATOR_OUT):
        result = orch.run_council(req)

    assert result["final_verdict"] == VALIDATOR_OUT["final_output"]

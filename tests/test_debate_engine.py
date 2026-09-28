import json
from pathlib import Path

import pytest

from backend.argument_graph import build_argument_graph
from backend.evidence import EvidenceError, validate_url
from backend.schemas import ConveneRequest


def test_private_evidence_hosts_are_blocked():
    with pytest.raises(EvidenceError):
        validate_url("http://127.0.0.1:8000/admin")


def test_argument_graph_connects_question_attacks_and_human_reframe():
    graph = build_argument_graph(
        "Which plan should we choose?",
        {"options": [{"id": "A", "summary": "Reliable plan"}], "recommendation": "A"},
        {"risks": [{"risk": "Integration delay"}]},
        {"risks_found": [{"risk": "Provider outage"}]},
        {"human_pov": "Users need a graceful handoff."},
        {"final_output": "Choose A."},
        [{"source_id": "src_1", "status": "retrieved", "title": "Source", "snippet": "Evidence"}],
    )
    relations = {edge["relation"] for edge in graph["edges"]}
    assert {"answers", "attacks", "reframes", "decides", "informs"} <= relations
    assert graph["stats"]["evidence_sources"] == 1


def test_request_accepts_rebuttal_sources_and_image_contract():
    request = ConveneRequest(
        dilemma="Compare these options",
        rebuttal="I prioritize safety.",
        evidence_urls=["https://example.com"],
        reference_image_base64="aGVsbG8=",
        reference_image_mime_type="image/png",
    )
    assert request.rebuttal == "I prioritize safety."
    assert request.reference_image_mime_type == "image/png"


def test_evaluation_fixtures_are_versioned():
    fixtures = json.loads((Path(__file__).parents[1] / "evals" / "debate_fixtures.json").read_text())
    assert len(fixtures) >= 3
    assert {"human-values-interruption", "source-grounded-choice"} <= {item["id"] for item in fixtures}

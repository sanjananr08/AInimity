import base64
import io
import subprocess
from pathlib import Path
import pytest
from pydantic import ValidationError
from reportlab.pdfgen import canvas

from backend.observatory import MAX_DOCUMENT_CHARS, _bound_text, _extract_pdf_text, assess_document, simulate_scenario
from backend.schemas import EvidenceAssessmentRequest, ScenarioEvent, ScenarioRequest


def test_healthcare_assessment_always_requires_human_review_and_disclaimer():
    result = assess_document(EvidenceAssessmentRequest(
        filename="clinical-note.txt",
        category="healthcare",
        document_text="A small observational study reports an association between the intervention and improved outcomes. The authors state that more research is required before clinical conclusions can be drawn.",
    ))
    assert result["category"] == "healthcare"
    assert result["human_review_required"] is True
    assert "not a diagnosis" in result["safety_notice"]
    assert all(claim["human_review_required"] for claim in result["claims"])


def test_pdf_payload_is_decoded_or_rejected_without_claiming_analysis():
    request = EvidenceAssessmentRequest(
        filename="brief.txt",
        category="research",
        document_base64=base64.b64encode(b"A report states that the result is preliminary and needs independent replication.").decode(),
        mime_type="text/plain",
    )
    result = assess_document(request)
    assert result["filename"] == "brief.txt"
    assert result["claims"]
    assert result["human_review_required"] is True


def test_chronoforge_returns_manual_checkpoints_and_alternate_branches():
    result = simulate_scenario(ScenarioRequest(
        objective="Launch a controlled beta",
        initial_state="Prototype exists and a small user group is available.",
        horizon_days=30,
        events=[
            ScenarioEvent(day=7, title="New evidence arrives", impact="positive"),
            ScenarioEvent(day=14, title="Critical bug appears", impact="critical"),
        ],
    ))
    assert [item["day"] for item in result["checkpoints"]] == [0, 7, 14]
    assert len(result["branches"]) == 3
    assert "not a prediction" in result["safety_notice"]
    assert all(0 <= item["risk_score"] <= 100 for item in result["checkpoints"])


def test_frontend_contains_manual_feature_sections_and_safety_copy():
    html = (Path(__file__).parents[1] / "frontend" / "index.html").read_text(encoding="utf-8")
    for marker in ["id=\"observatory\"", "id=\"chronoforge\"", "id=\"evidenceFile\"", "id=\"chronoEvents\"", "api/evidence/assess", "api/chronoforge/simulate", "HUMAN REVIEW REQUIRED", "not a prediction engine"]:
        assert marker in html


def test_large_document_context_is_bounded_without_losing_the_tail():
    text = "OPENING-MARKER " + ("context " * 30000) + " CLOSING-MARKER"
    bounded = _bound_text(text)
    assert len(bounded) <= MAX_DOCUMENT_CHARS + 100
    assert "OPENING-MARKER" in bounded
    assert "CLOSING-MARKER" in bounded


def test_text_pdf_extracts_through_observatory_pipeline():
    stream = io.BytesIO()
    pdf = canvas.Canvas(stream)
    pdf.drawString(72, 720, "GPO-911REPORT extraction smoke test")
    pdf.save()
    text = _extract_pdf_text(stream.getvalue())
    assert "GPO-911REPORT" in text


def test_malformed_pdf_returns_a_specific_readability_error():
    with pytest.raises(ValueError, match="corrupted, encrypted, or image-only"):
        _extract_pdf_text(b"not a PDF")


def test_removed_workspace_modes_are_rejected():
    from backend.schemas import WorkspaceRequest
    with pytest.raises(ValidationError):
        WorkspaceRequest(mode="fact_check", task="Check this claim.")
    with pytest.raises(ValidationError):
        WorkspaceRequest(mode="scenarios", task="Simulate this.")


def test_node_contract_checker_passes_when_node_is_available():
    result = subprocess.run(["node", "tools/verify-contracts.mjs"], cwd=Path(__file__).parents[1], text=True, capture_output=True)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "repository checks passed" in result.stdout

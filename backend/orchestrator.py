"""Fast, deterministic orchestration for the five-role AInimity council.

The important latency rule is simple: independent agents run concurrently.
A quick council therefore has three model waves instead of four:
Strategist -> (Technical + Adversarial in parallel) -> Validator.
Deep mode repeats the same pattern for a second pass.
"""
from __future__ import annotations

import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Callable, Optional

from .agents.adversarial_agent import run_adversarial
from .agents.human_mind_agent import run_human_mind
from .agents.strategist_agent import run_strategist
from .agents.technical_agent import run_technical
from .agents.validator_agent import run_validator
from .argument_graph import build_argument_graph
from .evidence import build_evidence_context, retrieve_urls
from .schemas import AgentCard, CouncilResult, ConveneRequest, TimelineEntry

AGENT_META = {
    "strategist": {"color": "#6f8cff", "role": "Sees the angle before the move."},
    "technical": {"color": "#48e6c1", "role": "Tests what can actually survive the click."},
    "adversarial": {"color": "#ff4f87", "role": "Looks for the failure hiding behind the demo."},
    "human_mind": {"color": "#c58cff", "role": "Interrupts with human stakes and lived context."},
    "validator": {"color": "#ffd36a", "role": "Signs the evidence when the argument converges."},
}

EventCallback = Optional[Callable[[dict], None]]


def _emit(callback: EventCallback, event: str, **data) -> None:
    if callback:
        callback({"event": event, **data})


def _truncate(text: str, n: int = 140) -> str:
    text = (text or "").strip()
    return text if len(text) <= n else text[: n - 1].rstrip() + "…"


_NONCOMMITTAL_PATTERNS = (
    re.compile(r"\bit depends\b", re.I),
    re.compile(r"\beither\b.{0,240}\bor\b", re.I | re.S),
    re.compile(r"\b(?:or alternatively|alternatively)\b", re.I),
    re.compile(r"\b(?:could|might|may)\s+(?:choose|select|pick|consider|use|go with)\b", re.I),
    re.compile(r"\b(?:choose|select|pick)\s+(?:either|between)\b", re.I),
)


def _enforce_single_verdict(validator_out: dict, strategist_out: dict) -> dict:
    final_output = str(validator_out.get("final_output", "")).strip()
    if not any(pattern.search(final_output) for pattern in _NONCOMMITTAL_PATTERNS):
        return validator_out
    recommendation = strategist_out.get("recommendation")
    options = strategist_out.get("options") or []
    selected = next((o for o in options if o.get("id") == recommendation), None)
    if not selected or not selected.get("summary"):
        return validator_out
    validator_out["final_output"] = (
        f"Choose Option {recommendation}: {selected['summary'].strip().rstrip('.!?')}. "
        "This is the council's best-supported choice based on the stated priorities, feasibility, and risks."
    )
    return validator_out


def _calibrate_validator_confidence(
    validator_out: dict,
    technical_out: dict,
    adversarial_out: dict,
    evidence: list[dict],
) -> float:
    """Keep the displayed confidence aligned with observable uncertainty.

    The validator's score is still the primary signal, but it cannot claim
    near-certainty while it reports unresolved contradictions or a critical
    adversarial risk. External evidence is never required for ordinary
    questions, so lack of URLs does not receive an arbitrary penalty.
    """
    confidence = max(0.0, min(1.0, float(validator_out.get("confidence", 0.7))))
    verdict = str(validator_out.get("verdict", "NEEDS_REVISION")).upper()
    contradictions = validator_out.get("contradictions_found") or []
    risk_level = str(adversarial_out.get("overall_risk_level", "MEDIUM")).upper()
    technical_warning = bool(technical_out.get("low_agreement_warning"))

    if verdict == "NEEDS_REVISION":
        confidence = min(confidence, 0.72)
    elif verdict == "REJECT":
        confidence = min(confidence, 0.82)
    if contradictions:
        confidence = min(confidence, 0.68)
    if risk_level == "CRITICAL":
        confidence = min(confidence, 0.60)
    elif risk_level == "HIGH":
        confidence = min(confidence, 0.74)
    if technical_warning:
        confidence = min(confidence, 0.70)

    # A citation may only increase trust if it points to evidence that was
    # actually retrieved; invalid model-supplied citations are discarded.
    valid_source_ids = {
        item.get("source_id")
        for item in evidence
        if item.get("status") == "retrieved" and item.get("source_id")
    }
    citations = validator_out.get("citations") or []
    validator_out["citations"] = [
        citation for citation in citations
        if citation.get("source_id") in valid_source_ids
    ]
    return round(confidence, 3)


def _assert_result_integrity(validator_out: dict) -> None:
    """Fail loudly instead of presenting an empty or misleading ruling."""
    final_output = " ".join(str(validator_out.get("final_output", "")).split())
    reasoning = " ".join(str(validator_out.get("reasoning", "")).split())
    if len(final_output) < 20:
        raise ValueError("Validator returned an unusably short final ruling.")
    if len(reasoning) < 20:
        raise ValueError("Validator returned insufficient reasoning for its ruling.")
    validator_out["final_output"] = final_output
    validator_out["reasoning"] = reasoning


def _recommended(strategist_out: dict, fallback: str) -> dict:
    options = strategist_out.get("options") or []
    rec = strategist_out.get("recommendation")
    return next((o for o in options if o.get("id") == rec), options[0] if options else {"summary": fallback})


def _run_parallel_secondary(req: ConveneRequest, strategist_out: dict, recommended: dict, evidence_context: str):
    """Technical and adversarial do not depend on each other; run together.

    The adversary is intentionally allowed to critique the strategist before
    the technical read exists. The Validator receives both complete reports.
    """
    with ThreadPoolExecutor(max_workers=2, thread_name_prefix="council") as pool:
        futures = {
            pool.submit(
                run_technical,
                req.dilemma,
                recommended.get("summary", req.dilemma),
                req.team_skills or "",
                evidence_context,
                req.rebuttal or "",
            ): "technical",
            pool.submit(
                run_adversarial,
                req.dilemma,
                strategist_out,
                {"note": "Technical analysis is running concurrently; critique the proposal and user question directly."},
                req.rebuttal,
                evidence_context,
            ): "adversarial",
        }
        results = {}
        for future in as_completed(futures):
            results[futures[future]] = future.result()
    return results["technical"], results["adversarial"]


def _build_cards(strategist_out, technical_out, adversarial_out, human_mind_out, validator_out, recommended):
    return {
        "strategist": AgentCard(
            title="Strategist", role=AGENT_META["strategist"]["role"], color=AGENT_META["strategist"]["color"],
            kicker="01 · STRATEGIC VERDICT", confidence=round(strategist_out.get("confidence", .7) * 100),
            lines=[
                ["RECOMMENDATION", f"Option {strategist_out.get('recommendation', '—')}: " + _truncate(recommended.get("summary", ""), 160)],
                ["REASONING", _truncate(strategist_out.get("reasoning", ""), 220)],
            ],
        ).model_dump(),
        "technical": AgentCard(
            title="Technical", role=AGENT_META["technical"]["role"], color=AGENT_META["technical"]["color"],
            kicker="02 · TECHNICAL VERDICT", confidence=technical_out.get("composite_feasibility_score") if technical_out.get("composite_feasibility_score") is not None else 50,
            lines=[
                ["VERDICT", _truncate(technical_out.get("one_line_verdict", ""), 200)],
                ["TOP RISK", _truncate((technical_out.get("risks") or [{}])[0].get("risk", "No major risks flagged."), 200)],
            ],
        ).model_dump(),
        "adversarial": AgentCard(
            title="Adversarial", role=AGENT_META["adversarial"]["role"], color=AGENT_META["adversarial"]["color"],
            kicker="03 · ADVERSARIAL VERDICT",
            confidence={"LOW": 25, "MEDIUM": 50, "HIGH": 75, "CRITICAL": 95}.get(adversarial_out.get("overall_risk_level", "MEDIUM"), 50),
            lines=[
                ["WORST CASE", _truncate(adversarial_out.get("worst_case_scenario", ""), 200)],
                ["SUMMARY", _truncate(adversarial_out.get("summary", ""), 200)],
            ],
        ).model_dump(),
        "human_mind": AgentCard(
            title="Human Mind", role=AGENT_META["human_mind"]["role"], color=AGENT_META["human_mind"]["color"],
            kicker="04 · HUMAN INTERRUPTION", confidence=round(human_mind_out.get("confidence", .7) * 100),
            lines=[
                ["POV", _truncate(human_mind_out.get("human_pov", ""), 220)],
                ["INTERRUPTION", _truncate(human_mind_out.get("interruption_question", ""), 220)],
            ],
        ).model_dump(),
        "validator": AgentCard(
            title="Validator", role=AGENT_META["validator"]["role"], color=AGENT_META["validator"]["color"],
            kicker="05 · VALIDATOR VERDICT", confidence=round(validator_out.get("confidence", .7) * 100),
            lines=[
                ["VERDICT", validator_out.get("verdict", "NEEDS_REVISION")],
                ["FINAL OUTPUT", _truncate(validator_out.get("final_output", ""), 220)],
            ],
        ).model_dump(),
    }


def run_council(req: ConveneRequest, on_event: EventCallback = None) -> dict:
    clarified_goal = req.clarified_goal or req.dilemma
    total_rounds = 2 if req.mode == "deep" else 1
    timeline: list[dict] = []
    evidence = retrieve_urls(req.evidence_urls)
    evidence_context = build_evidence_context(evidence, req.evidence_text or "")

    def add(agent: str, round_no: int, headline: str):
        item = {"agent": agent, "round": round_no, "headline": _truncate(headline)}
        timeline.append(item)
        _emit(on_event, "agent", **item)

    _emit(on_event, "status", message="Council engaged.")
    add("strategist", 1, f'Dilemma received: “{_truncate(req.dilemma, 100)}”')

    strategist_out = run_strategist({
        "dilemma": req.dilemma,
        "clarified_goal": clarified_goal,
        "constraints": req.constraints,
        "priorities": req.priorities.model_dump(),
        "prior_critique": None,
        "evidence_context": evidence_context,
        "user_rebuttal": req.rebuttal,
        "reference_image_base64": req.reference_image_base64,
        "reference_image_mime_type": req.reference_image_mime_type,
    })
    add("strategist", 1, strategist_out["reasoning"])

    recommended = _recommended(strategist_out, clarified_goal)
    technical_out, adversarial_out = _run_parallel_secondary(req, strategist_out, recommended, evidence_context)
    add("technical", 1, technical_out.get("one_line_verdict", "Technical analysis complete."))
    add("adversarial", 1, adversarial_out.get("summary") or adversarial_out.get("worst_case_scenario", "Adversarial analysis complete."))

    human_mind_out = run_human_mind(req.dilemma, strategist_out, technical_out, adversarial_out, req.rebuttal, evidence_context)
    add("human_mind", 1, human_mind_out.get("interruption_question") or human_mind_out.get("human_pov", "Human perspective added."))
    validator_out = run_validator(req.dilemma, strategist_out, technical_out, adversarial_out, human_mind_out, evidence_context, req.rebuttal)
    add("validator", 1, validator_out.get("reasoning", "Validation complete."))

    rounds_run = 1
    # Quick mode stays quick: never silently launch a second five-role pass.
    # Deep mode explicitly requests the second pass.
    if total_rounds > 1:
        rounds_run = 2
        _emit(on_event, "status", message="Round 2: stress-testing the ruling.")
        critique_text = (adversarial_out.get("summary", "") + " " + " ".join(r.get("risk", "") for r in adversarial_out.get("risks_found", []))).strip()
        strategist_out = run_strategist({
            "dilemma": req.dilemma,
            "clarified_goal": clarified_goal,
            "constraints": req.constraints,
            "priorities": req.priorities.model_dump(),
            "prior_critique": critique_text,
            "evidence_context": evidence_context,
            "user_rebuttal": req.rebuttal,
            "reference_image_base64": req.reference_image_base64,
            "reference_image_mime_type": req.reference_image_mime_type,
        })
        recommended = _recommended(strategist_out, clarified_goal)
        add("strategist", 2, strategist_out["reasoning"])
        technical_out, adversarial_out = _run_parallel_secondary(req, strategist_out, recommended, evidence_context)
        add("technical", 2, technical_out.get("one_line_verdict", "Technical analysis complete."))
        add("adversarial", 2, adversarial_out.get("summary") or adversarial_out.get("worst_case_scenario", "Adversarial analysis complete."))
        human_mind_out = run_human_mind(req.dilemma, strategist_out, technical_out, adversarial_out, req.rebuttal, evidence_context)
        add("human_mind", 2, human_mind_out.get("interruption_question") or human_mind_out.get("human_pov", "Human perspective added."))
        validator_out = run_validator(req.dilemma, strategist_out, technical_out, adversarial_out, human_mind_out, evidence_context, req.rebuttal)
        add("validator", 2, validator_out.get("reasoning", "Validation complete."))

    validator_out = _enforce_single_verdict(validator_out, strategist_out)
    _assert_result_integrity(validator_out)
    validator_out["confidence"] = _calibrate_validator_confidence(
        validator_out, technical_out, adversarial_out, evidence
    )
    argument_graph = build_argument_graph(req.dilemma, strategist_out, technical_out, adversarial_out, human_mind_out, validator_out, evidence)
    cards = _build_cards(strategist_out, technical_out, adversarial_out, human_mind_out, validator_out, recommended)
    result = CouncilResult(
        dilemma=req.dilemma, mode=req.mode, rounds=rounds_run,
        timeline=[TimelineEntry(**t) for t in timeline],
        strategist=strategist_out, technical=technical_out, adversarial=adversarial_out,
        human_mind=human_mind_out, validator=validator_out, cards=cards,
        final_verdict=validator_out.get("final_output", "No ruling produced."),
        final_confidence=round(validator_out.get("confidence", .7) * 100),
        evidence=evidence, argument_graph=argument_graph,
    ).model_dump()
    _emit(on_event, "complete", result=result)
    return result

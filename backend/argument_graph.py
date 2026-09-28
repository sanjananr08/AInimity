"""Deterministic, inspectable argument graph derived from council reports."""
from __future__ import annotations


def _node(node_id: str, kind: str, label: str, text: str, source: str) -> dict:
    return {"id": node_id, "kind": kind, "label": label, "text": (text or "")[:500], "source": source}


def build_argument_graph(dilemma: str, strategist: dict, technical: dict, adversarial: dict, human_mind: dict, validator: dict, evidence: list[dict]) -> dict:
    nodes = [_node("question", "question", "User question", dilemma, "user")]
    edges = []
    for option in strategist.get("options", [])[:5]:
        oid = f"option_{option.get('id', 'x')}"
        nodes.append(_node(oid, "proposal", f"Option {option.get('id', '?')}", option.get("summary", ""), "strategist"))
        edges.append({"from": "question", "to": oid, "relation": "answers"})
    rec = strategist.get("recommendation")
    if rec:
        edges.append({"from": f"option_{rec}", "to": "question", "relation": "recommended"})
    for i, risk in enumerate(technical.get("risks", [])[:8]):
        rid = f"technical_risk_{i}"
        nodes.append(_node(rid, "risk", "Technical risk", risk.get("risk", ""), "technical"))
        if rec: edges.append({"from": rid, "to": f"option_{rec}", "relation": "constrains"})
    for i, risk in enumerate(adversarial.get("risks_found", [])[:8]):
        rid = f"adversarial_risk_{i}"
        nodes.append(_node(rid, "attack", "Adversarial attack", risk.get("risk", ""), "adversarial"))
        if rec: edges.append({"from": rid, "to": f"option_{rec}", "relation": "attacks"})
    nodes.append(_node("human_interruption", "human_context", "Human Mind interruption", human_mind.get("human_pov", ""), "human_mind"))
    edges.append({"from": "human_interruption", "to": "question", "relation": "reframes"})
    for source in evidence:
        if source.get("status") == "retrieved":
            sid = source["source_id"]
            nodes.append(_node(sid, "evidence", source.get("title", sid), source.get("snippet", ""), "evidence"))
            edges.append({"from": sid, "to": "question", "relation": "informs"})
    nodes.append(_node("validator_verdict", "verdict", "Final ruling", validator.get("final_output", ""), "validator"))
    edges.append({"from": "validator_verdict", "to": "question", "relation": "decides"})
    return {"version": 1, "nodes": nodes, "edges": edges, "stats": {"nodes": len(nodes), "edges": len(edges), "evidence_sources": sum(s.get("status") == "retrieved" for s in evidence)}}

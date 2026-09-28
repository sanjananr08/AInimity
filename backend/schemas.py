"""
Shared data contracts for the whole council.

Keeping these as pydantic models means malformed LLM output gets
caught immediately instead of silently corrupting the debate
downstream, and it gives the FastAPI layer automatic request/response
validation + OpenAPI docs for free.
"""

from typing import Literal, Optional
from pydantic import BaseModel, Field, field_validator

# --------------------------------------------------------------------------
# Shared / request-level
# --------------------------------------------------------------------------


class Priorities(BaseModel):
    time: float = Field(0.34, ge=0, le=1)
    impact: float = Field(0.33, ge=0, le=1)
    innovation: float = Field(0.33, ge=0, le=1)


class ConveneRequest(BaseModel):
    """What the frontend sends when the user hits 'Convene the Council'."""

    dilemma: str = Field(..., min_length=3, max_length=12000)
    clarified_goal: Optional[str] = Field(None, max_length=4000)
    constraints: list[str] = Field(default_factory=list, max_length=30)
    priorities: Priorities = Field(default_factory=Priorities)
    team_skills: Optional[str] = Field(None, max_length=4000)
    rebuttal: Optional[str] = Field(None, max_length=6000)
    evidence_urls: list[str] = Field(default_factory=list, max_length=8)
    evidence_text: Optional[str] = Field(None, max_length=12000)
    reference_image_base64: Optional[str] = Field(None, max_length=5600000)
    reference_image_mime_type: Optional[str] = Field(None, pattern=r"^image/(png|jpeg|webp|gif)$")
    mode: str = Field("quick", pattern="^(quick|deep)$")  # quick=1 round, deep=2


WORKSPACE_MODES = Literal[
    "research", "decision_matrix", "tutor",
    "document_intelligence", "idea_incubator", "code_review", "meeting",
    "memory_lab",
]


class WorkspaceRequest(BaseModel):
    """Input for the separate non-debate AInimity Workspace modes."""

    mode: WORKSPACE_MODES
    task: str = Field(..., min_length=3, max_length=12000)
    context: Optional[str] = Field(None, max_length=24000)
    evidence_urls: list[str] = Field(default_factory=list, max_length=8)
    evidence_text: Optional[str] = Field(None, max_length=12000)
    audience: Optional[str] = Field(None, max_length=1000)


class WorkspaceSection(BaseModel):
    title: str = Field(..., min_length=1, max_length=120)
    content: str = Field(..., min_length=1, max_length=6000)
    bullets: list[str] = Field(default_factory=list, max_length=12)


class WorkspaceResult(BaseModel):
    mode: WORKSPACE_MODES
    title: str
    summary: str
    sections: list[WorkspaceSection] = Field(default_factory=list, max_length=12)
    action_items: list[str] = Field(default_factory=list, max_length=12)
    caveats: list[str] = Field(default_factory=list, max_length=12)
    confidence: float = Field(ge=0, le=1)
    citations: list[dict] = Field(default_factory=list)
    evidence: list[dict] = Field(default_factory=list)


EVIDENCE_CATEGORIES = Literal[
    "healthcare", "research", "legal", "financial", "technical",
    "policy", "news", "personal", "other",
]


class EvidenceAssessmentRequest(BaseModel):
    filename: str = Field(..., min_length=1, max_length=240)
    category: EVIDENCE_CATEGORIES = "other"
    document_text: Optional[str] = Field(None, max_length=120000)
    document_base64: Optional[str] = Field(None, max_length=45000000)
    mime_type: Optional[str] = Field(None, max_length=120)
    user_context: Optional[str] = Field(None, max_length=6000)


class EvidenceClaim(BaseModel):
    claim: str = Field(..., min_length=1, max_length=1200)
    claim_type: str = "claim"
    status: Literal["supported", "contradicted", "mixed", "unclear"] = "unclear"
    support: str = ""
    risk_level: Literal["low", "medium", "high"] = "medium"
    human_review_required: bool = True


class EvidenceAssessment(BaseModel):
    filename: str
    category: EVIDENCE_CATEGORIES
    summary: str
    reliability_score: int = Field(ge=0, le=100)
    reliability_band: Literal["weak", "mixed", "promising", "strong"]
    provenance_signals: list[str] = Field(default_factory=list, max_length=12)
    claims: list[EvidenceClaim] = Field(default_factory=list, max_length=20)
    contradictions: list[str] = Field(default_factory=list, max_length=12)
    missing_information: list[str] = Field(default_factory=list, max_length=12)
    recommended_questions: list[str] = Field(default_factory=list, max_length=12)
    safety_notice: str
    human_review_required: bool = True


class ScenarioEvent(BaseModel):
    day: int = Field(ge=0, le=3650)
    title: str = Field(..., min_length=1, max_length=180)
    impact: Literal["positive", "neutral", "negative", "critical"] = "neutral"
    selected: bool = True


class ScenarioRequest(BaseModel):
    objective: str = Field(..., min_length=3, max_length=4000)
    initial_state: str = Field(..., min_length=3, max_length=6000)
    horizon_days: int = Field(30, ge=1, le=3650)
    events: list[ScenarioEvent] = Field(default_factory=list, max_length=24)


class ScenarioCheckpoint(BaseModel):
    day: int
    title: str
    state: str
    signals: list[str] = Field(default_factory=list)
    next_actions: list[str] = Field(default_factory=list)
    risk_score: int = Field(ge=0, le=100)
    confidence: int = Field(ge=0, le=100)


class ScenarioBranch(BaseModel):
    title: str
    decision: str
    rationale: str
    risk_score: int = Field(ge=0, le=100)
    reversibility: Literal["high", "medium", "low"]


class ScenarioResult(BaseModel):
    objective: str
    horizon_days: int
    checkpoints: list[ScenarioCheckpoint]
    branches: list[ScenarioBranch]
    safety_notice: str


# --------------------------------------------------------------------------
# Strategist
# --------------------------------------------------------------------------


class StrategistInput(BaseModel):
    dilemma: str
    clarified_goal: str
    constraints: list[str] = Field(default_factory=list)
    priorities: Priorities
    prior_critique: Optional[str] = None  # set only on round 2 (defend/revise)
    evidence_context: Optional[str] = None
    user_rebuttal: Optional[str] = None


class Option(BaseModel):
    id: str  # "A", "B", "C"...
    summary: str
    pros: list[str]
    cons: list[str]


class StrategistOutput(BaseModel):
    options: list[Option]
    recommendation: str  # must match one of options[].id
    reasoning: str
    confidence: float = Field(ge=0, le=1)

    @field_validator("recommendation")
    @classmethod
    def recommendation_must_exist(cls, v, info):
        options = info.data.get("options", [])
        ids = {o.id for o in options}
        if ids and v not in ids:
            raise ValueError(f"recommendation '{v}' not among option ids {ids}")
        return v


# --------------------------------------------------------------------------
# Technical
# --------------------------------------------------------------------------


class RiskItem(BaseModel):
    risk: str
    severity: int = Field(ge=1, le=5)
    likelihood: int = Field(ge=1, le=5)
    mitigation: str
    priority_score: Optional[int] = None


class TechnicalOutput(BaseModel):
    needs_clarification: bool = False
    clarifying_question: Optional[str] = None
    stated_assumption: Optional[str] = None

    complexity_score: Optional[int] = Field(None, ge=0, le=100)
    time_fit_score: Optional[int] = Field(None, ge=0, le=100)
    team_skill_fit_score: Optional[int] = Field(None, ge=0, le=100)
    scalability_score: Optional[int] = Field(None, ge=0, le=100)
    security_score: Optional[int] = Field(None, ge=0, le=100)

    time_estimate_hours: Optional[float] = None
    recommended_stack: list[str] = Field(default_factory=list)
    fallback_stack_if_time_short: list[str] = Field(default_factory=list)
    risks: list[RiskItem] = Field(default_factory=list)

    composite_feasibility_score: Optional[int] = None
    self_consistency_gap: Optional[int] = None
    low_agreement_warning: bool = False
    self_critique: Optional[str] = None
    one_line_verdict: str = ""
    hours_remaining_at_evaluation: Optional[float] = None
    from_cache: bool = False


# --------------------------------------------------------------------------
# Adversarial
# --------------------------------------------------------------------------


class AdversarialRisk(BaseModel):
    risk: str
    target: str = "Both"  # "Strategist" | "Technical" | "Both"
    severity: str = "MEDIUM"  # LOW | MEDIUM | HIGH | CRITICAL
    explanation: str
    suggested_mitigation: str


class AdversarialOutput(BaseModel):
    risks_found: list[AdversarialRisk] = Field(default_factory=list)
    unsupported_assumptions: list[str] = Field(default_factory=list)
    worst_case_scenario: str = ""
    overall_risk_level: str = "MEDIUM"
    summary: str = ""


# --------------------------------------------------------------------------
# Validator
# --------------------------------------------------------------------------


class ValidatorOutput(BaseModel):
    contradictions_found: list[str] = Field(default_factory=list)
    questions_for_agents: list[str] = Field(default_factory=list)
    verdict: str = "NEEDS_REVISION"  # ACCEPT | NEEDS_REVISION | REJECT
    final_output: str = ""
    reasoning: str = ""
    confidence: float = Field(0.7, ge=0, le=1)
    citations: list[dict] = Field(default_factory=list)


# --------------------------------------------------------------------------
# Human Mind interlocutor
# --------------------------------------------------------------------------


class HumanMindOutput(BaseModel):
    intervention_type: str = "NO_INTERVENTION"
    human_pov: str
    lived_context: str
    hidden_value_conflict: str
    emotional_signal: str
    interruption_question: str
    practical_reframe: str
    should_reconsider: bool = False
    confidence: float = Field(0.7, ge=0, le=1)


# --------------------------------------------------------------------------
# Orchestrator output (what the API returns to the frontend)
# --------------------------------------------------------------------------


class TimelineEntry(BaseModel):
    agent: str  # strategist | technical | adversarial | human_mind | validator
    round: int
    headline: str


class AgentCard(BaseModel):
    """Normalized shape the frontend's five verdict cards render from."""

    title: str
    role: str
    color: str
    kicker: str
    confidence: int
    lines: list[list[str]]  # [[label, text], ...]


class CouncilResult(BaseModel):
    dilemma: str
    mode: str
    rounds: int
    timeline: list[TimelineEntry]
    strategist: StrategistOutput
    technical: TechnicalOutput
    adversarial: AdversarialOutput
    human_mind: HumanMindOutput
    validator: ValidatorOutput
    cards: dict[str, AgentCard]
    final_verdict: str
    final_confidence: int
    evidence: list[dict] = Field(default_factory=list)
    argument_graph: dict = Field(default_factory=dict)


# --------------------------------------------------------------------------
# Authentication
# --------------------------------------------------------------------------

class AuthRequest(BaseModel):
    email: str = Field(..., min_length=3, max_length=320)
    password: str = Field(..., min_length=1, max_length=256)


class UserPublic(BaseModel):
    id: int
    email: str
    created_at: str

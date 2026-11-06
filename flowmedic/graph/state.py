"""Small validated contracts shared by later triage and planning steps."""

import re
from enum import StrEnum
from typing import Any, Literal, TypedDict

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator

from flowmedic.config import REPO_ROOT

Category = StrEnum(
    "Category",
    {
        code: code
        for code in yaml.safe_load(
            (REPO_ROOT / "knowledge/categories.yaml").read_text(encoding="utf-8")
        )["categories"]
    },
)


class Severity(StrEnum):
    """Impact from service down to no user impact."""

    P1 = "P1"
    P2 = "P2"
    P3 = "P3"
    P4 = "P4"


class Route(StrEnum):
    """Deterministic retrieval decision."""

    KNOWN_FIX = "known_fix"
    SIMILAR = "similar"
    NEW_ISSUE = "new_issue"
    CLARIFY = "clarify"


class StepKind(StrEnum):
    """Execution is always left to the engineer."""

    READ = "read"
    CHANGE = "change"
    DESTRUCTIVE = "destructive"


class Source(StrEnum):
    """Provenance of a suggested step."""

    VERIFIED = "verified"
    CITED = "cited"
    MODEL = "model"


class TriageContext(BaseModel):
    """Known intake slots; profiles can request additional slots later."""

    model_config = ConfigDict(extra="forbid")

    platform: str | None = None
    component: str | None = None
    version: str | None = None
    os: str | None = None
    environment: str | None = None
    start_time: str | None = None
    scope: str | None = None
    recent_changes: str | None = None
    deployment_mode: str | None = None

    def missing_slots(self, profile: dict[str, Any]) -> list[str]:
        """Return absent required profile slots in profile order."""
        return [
            slot
            for slot in profile.get("clarify_slots", {}).get("required", [])
            if not getattr(self, slot, None)
        ]


class Evidence(BaseModel):
    """A masked line of diagnostic evidence."""

    source_file: str
    line_no: int = Field(ge=1)
    text: str
    signature: str | None = None


class KBMatch(BaseModel):
    """Hybrid score, calibrated vector_score, raw cosine and signature coverage."""

    doc_id: str
    doc_type: Literal["incident", "runbook"]
    title: str
    score: float = Field(ge=0, le=1)
    signature_hits: list[str] = Field(default_factory=list)
    vector_score: float = Field(ge=0, le=1)
    raw_vector_score: float = Field(default=0, ge=-1, le=1)
    signature_score: float = Field(default=0, ge=0, le=1)
    category_match: bool = False


class PlanStep(BaseModel):
    """An instruction for the engineer, never an executable tool action."""

    n: int = Field(ge=1)
    title: str
    kind: StepKind = Field(
        description=(
            "read for observations/diagnostics; change for mutations; "
            "destructive for irreversible mutations"
        )
    )
    command_or_action: str
    where: str
    expected_output: str
    decision_rule: str = (
        "If expected output matches, go to the next step; otherwise re-triage."
    )
    risk: str | None = None
    rollback: str | None = None
    source: Source
    source_ref: str | None = None

    @model_validator(mode="after")
    def require_recovery(self) -> "PlanStep":
        """Changes must explain impact and a recovery path before display."""
        if self.kind == StepKind.READ and re.match(
            r"(?i)^(?:set|add|update|change|replace|enable|disable|restart|stop|kill|"
            r"drop|delete|remove|alter|truncate|grant|revoke|install|upgrade)\b",
            self.command_or_action.strip(),
        ):
            raise ValueError("An explicit mutation cannot be labelled read-only")
        if self.kind != StepKind.READ and (
            not self.risk
            or not self.risk.strip()
            or not self.rollback
            or not self.rollback.strip()
        ):
            raise ValueError("Change/destructive steps require risk and rollback")
        return self


RootCauseID = StrEnum(
    "RootCauseID",
    {
        key: key
        for key in yaml.safe_load(
            (REPO_ROOT / "knowledge/root_causes.yaml").read_text(encoding="utf-8")
        )["root_causes"]
    },
)


class RankedRootCause(BaseModel):
    """A hypothesis with references to evidence."""

    id: RootCauseID
    confidence: float = Field(ge=0, le=1)
    evidence_refs: list[str] = Field(default_factory=list)


class TriageResult(BaseModel):
    """Structured handoff from diagnosis to planning."""

    category: Category
    secondary_categories: list[Category] = Field(default_factory=list)
    severity: Severity
    root_causes: list[RankedRootCause] = Field(default_factory=list)
    route: Route
    kb_matches: list[KBMatch] = Field(default_factory=list)
    related_components: list[str] = Field(default_factory=list)
    first_steps: list[PlanStep] = Field(default_factory=list)
    confidence: float = Field(ge=0, le=1)
    notes: str = ""

    affected_component: str | None = None
    flags: list[str] = Field(default_factory=list)


class Classification(BaseModel):
    """Constrained strong-model diagnosis."""

    category: Category
    secondary_categories: list[Category] = Field(default_factory=list)
    severity: Severity
    root_causes: list[RankedRootCause] = Field(default_factory=list, max_length=3)
    confidence: float = Field(ge=0, le=1)
    affected_component: str | None = None


class VendorFindings(BaseModel):
    """Research output with auditable step provenance."""

    likely_causes: list[str] = Field(default_factory=list)
    steps: list[PlanStep] = Field(default_factory=list)
    urls: list[str] = Field(default_factory=list)
    notes: str = ""


class TriageState(TypedDict, total=False):
    """Checkpointed state; quarantined flags never enter model input."""

    case_id: str
    problem: str
    log_root: str
    context: TriageContext
    confirmed_context: dict[str, Any]
    context_answers: dict[str, str]
    profile: dict[str, Any]
    topology: dict[str, Any]
    clarification_rounds: int
    evidence_rounds: int
    approved: bool
    start_time: str | None
    end_time: str | None
    evidence: list[Evidence]
    engineer_evidence: list[Evidence]
    signatures: list[str]
    diagnostic_summaries: dict[str, Any]
    flags: list[str]
    notes: list[str]
    model_calls: int
    stopped: bool
    classification: Classification
    matches: list[KBMatch]
    route: Route
    related_components: list[str]
    first_steps: list[PlanStep]
    result: TriageResult


def validate_specific_recovery(step: PlanStep) -> None:
    """Reject absent, generic and observation-only recovery for a mutation."""
    if step.kind == StepKind.READ:
        return
    for text in (step.risk or "", step.rollback or ""):
        normalized = text.strip().lower().rstrip(".")
        if (
            not normalized
            or normalized
            in {"n/a", "none", "not applicable", "no change", "no rollback needed"}
            or any(
                old in normalized
                for old in (
                    "may interrupt active work",
                    "stop if impact is unclear",
                    "record current settings and approve a recovery procedure",
                    "read-only inspection",
                    "read-only check",
                )
            )
        ):
            raise ValueError(
                "Step-specific recovery required; no old boilerplate; "
                "observations must use kind=read"
            )


class ActivePlan(BaseModel):
    """Execution queue can grow through validated insertions, with a turn cap."""

    steps: list[PlanStep] = Field(min_length=1, max_length=40)


class ResolutionPlan(ActivePlan):
    """Grounded, bounded instructions for human execution."""

    steps: list[PlanStep] = Field(min_length=5, max_length=10)

    @model_validator(mode="after")
    def validate_steps(self) -> "ResolutionPlan":
        if [s.n for s in self.steps] != list(range(1, len(self.steps) + 1)):
            raise ValueError("Plan step numbers must be consecutive")
        for step in self.steps:
            validate_specific_recovery(step)
        return self


class StepReply(BaseModel):
    status: Literal["done", "skipped", "failed"]
    output: str = ""
    confirmed: bool = False


class Interpretation(BaseModel):
    decision: Literal["next", "insert_steps", "retriage", "escalate", "resolved"]
    reason: str
    steps: list[PlanStep] = Field(default_factory=list, max_length=5)


class IncidentRecord(BaseModel):
    symptoms: str
    signatures: list[str]
    root_causes: list[RootCauseID]
    steps_worked: list[dict[str, str]]
    platform: str
    category: Category
    version: str | None
    os: str | None
    environment: str
    components: list[str]


class IncidentState(TriageState, total=False):
    plan: ActivePlan
    step_index: int
    reply: StepReply
    history: list[dict[str, Any]]
    decision: Interpretation
    retriage_rounds: int
    outcome: str
    incident_record: IncidentRecord
    saved_path: str
    vendor_case: str
    planner_turns: int

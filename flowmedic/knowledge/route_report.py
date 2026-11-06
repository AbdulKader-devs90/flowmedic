"""Report development routing accuracy; optionally print a small calibration grid."""

import argparse
from collections.abc import Sequence
from dataclasses import dataclass
from itertools import product

from flowmedic.config import RETRIEVAL_GRID, ConfigurationError, Settings, get_settings
from flowmedic.graph.state import KBMatch, Route
from flowmedic.knowledge.loaders import (
    list_scenarios,
    load_documents,
    load_profile,
    load_scenario,
)
from flowmedic.tools.knowledge_repo import (
    VectorStore,
    get_vector_store,
    normalize_vector,
    route_for,
    search,
)
from flowmedic.tools.parsers.signatures import extract_signatures
from flowmedic.tools.redact import redact
from flowmedic.tracing import tool_context


@dataclass
class ReportCase:
    """Retrieval results and separate evaluation labels; labels never enter search."""

    case_id: str
    expected_route: str
    expected_ids: list[str]
    matches: list[KBMatch]


def collect_cases(store: VectorStore | None = None) -> list[ReportCase]:
    """Search each eligible scenario once, retaining every candidate for grid replay."""
    documents = load_documents()
    store = store or get_vector_store()
    cases: list[ReportCase] = []
    for case_id in list_scenarios():
        scenario = load_scenario(case_id)
        expected_route = scenario.expected.get("expected_route")
        if expected_route not in {"known_fix", "similar", "new_issue"}:
            continue
        platform = scenario.expected["platform"]
        with tool_context(case_id):
            logs = redact("\n".join(scenario.logs.values())).text
            text = redact(scenario.problem).text + "\n" + logs
            signatures = [
                s.signature for s in extract_signatures(logs, load_profile(platform))
            ]
            matches = search(
                text,
                signatures,
                platform,
                version=scenario.expected.get("given_context", {}).get("version"),
                k=len(documents),
                store=store,
                documents=documents,
                log_text=logs,
            )
        cases.append(
            ReportCase(
                case_id,
                expected_route,
                scenario.expected.get("expected_kb_ids", []),
                matches,
            )
        )
    return cases


def rescore(matches: Sequence[KBMatch], settings: Settings) -> list[KBMatch]:
    """Replay calibration over frozen raw scores; no embedding calls or labels."""
    rescored: list[KBMatch] = []
    for match in matches:
        vector = normalize_vector(match.raw_vector_score, settings)
        rescored.append(
            match.model_copy(
                update={
                    "vector_score": vector,
                    "score": settings.kb_vector_weight * vector
                    + settings.kb_signature_weight * match.signature_score,
                }
            )
        )
    return sorted(rescored, key=lambda m: (-m.score, m.doc_id))


def assess(case: ReportCase, settings: Settings) -> tuple[list[KBMatch], Route, bool]:
    """Compute routing and top-document correctness independently."""
    matches = rescore(case.matches, settings)
    with tool_context(case.case_id):
        predicted = route_for(matches, settings=settings)
    doc_ok = bool(matches and matches[0].doc_id in case.expected_ids)
    return matches, predicted, doc_ok


def print_report(cases: Sequence[ReportCase], settings: Settings) -> None:
    """Top-1 accuracy is measured only where expected KB IDs are supplied."""
    print(
        "case_id     expected    predicted   expected kb ids   top match  score  result"
    )
    route_hits = doc_hits = doc_total = 0
    for case in cases:
        matches, predicted, doc_ok = assess(case, settings)
        route_ok = predicted == case.expected_route
        route_hits += route_ok
        if case.expected_ids:
            doc_hits += doc_ok
            doc_total += 1
        top = matches[0] if matches else None
        passed = route_ok and (doc_ok or not case.expected_ids)
        print(
            f"{case.case_id:<11} {case.expected_route:<11} {predicted.value:<11} "
            f"{','.join(case.expected_ids) or '-':<17} "
            f"{top.doc_id if top else '-':<10} "
            f"{top.score if top else 0:.3f}  {'PASS' if passed else 'FAIL'}"
        )
    print(
        f"Route accuracy: {route_hits}/{len(cases)} ({route_hits / len(cases):.1%})"
        if cases
        else "Route accuracy: n/a"
    )
    print(
        f"Top-1 doc accuracy: {doc_hits}/{doc_total} ({doc_hits / doc_total:.1%})"
        if doc_total
        else "Top-1 doc accuracy: n/a (no expected KB IDs)"
    )
    print(
        "PASS requires the correct route and, when supplied, an expected top-1 KB ID."
    )


def print_grid(cases: Sequence[ReportCase], base: Settings) -> Settings:
    """Try the centralized grid against frozen results, keeping stable ties."""
    rows: list[tuple[int, int, Settings]] = []
    for values in product(*RETRIEVAL_GRID.values()):
        overrides = dict(zip(RETRIEVAL_GRID, values))
        overrides["kb_signature_weight"] = 1 - overrides["kb_vector_weight"]
        trial = Settings.model_validate({**base.model_dump(), **overrides})
        route_hits = doc_hits = 0
        for case in cases:
            _, predicted, doc_ok = assess(case, trial)
            route_hits += predicted == case.expected_route
            doc_hits += doc_ok
        rows.append((route_hits, doc_hits, trial))
    rows.sort(key=lambda row: (-row[0], -row[1]))
    print(
        f"Grid: {len(rows)} combinations on {len(cases)} dev scenarios; "
        "rank by route accuracy, then top-1 accuracy, then configured grid order."
    )
    print("floor ceil vector signature known similar routes top1")
    for routes, docs, trial in rows:
        print(
            f"{trial.vec_floor:.2f}  {trial.vec_ceil:.2f} "
            f"{trial.kb_vector_weight:.2f}   "
            f"{trial.kb_signature_weight:.2f}      {trial.kb_known_fix:.2f}  "
            f"{trial.kb_similar:.2f}    {routes:2}     {docs:2}"
        )
    best = rows[0][2]
    print("Best grid configuration (does not change .env):")
    print_settings(best)
    return best


def print_settings(settings: Settings) -> None:
    """Print only public calibration configuration, never provider credentials."""
    for name in (*RETRIEVAL_GRID, "kb_signature_weight"):
        print(f"{name.upper()}={getattr(settings, name):.2f}")


def main() -> None:
    """Run against the configured backend; --grid replays raw results locally."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--grid", action="store_true", help="print calibration grid results"
    )
    args = parser.parse_args()
    settings = get_settings()
    try:
        cases = collect_cases()
    except ConfigurationError as exc:
        raise SystemExit(str(exc)) from exc
    if args.grid:
        settings = print_grid(cases, settings)
    else:
        print_settings(settings)
    print_report(cases, settings)


if __name__ == "__main__":
    main()

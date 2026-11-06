"""Inspect retrieval on a local scenario without using expected diagnoses."""

import argparse

from flowmedic.config import ConfigurationError
from flowmedic.knowledge.loaders import load_profile, load_scenario
from flowmedic.tools.knowledge_repo import route_for, search
from flowmedic.tools.parsers.signatures import extract_signatures
from flowmedic.tools.redact import redact
from flowmedic.tracing import tool_context


def main() -> None:
    """Print three matches and the deterministic retrieval route."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("case_id")
    args = parser.parse_args()
    with tool_context(args.case_id):
        run_search(args.case_id)


def run_search(case_id: str) -> None:
    """Retrieve under the current scenario trace context."""
    scenario = load_scenario(case_id)
    platform = scenario.expected["platform"]
    profile = load_profile(platform)
    text = redact(scenario.problem + "\n" + "\n".join(scenario.logs.values())).text
    signatures = [s.signature for s in extract_signatures(text, profile)]
    try:
        matches = search(
            text,
            signatures,
            platform,
            version=scenario.expected.get("given_context", {}).get("version"),
            k=3,
        )
    except ConfigurationError as exc:
        raise SystemExit(str(exc)) from exc
    print(f"{case_id}: signatures={', '.join(signatures) or '(none)'}")
    for match in matches:
        print(
            f"{match.doc_id} score={match.score:.3f} vector={match.vector_score:.3f} "
            f"signatures={len(match.signature_hits)} | {match.title}"
        )
    print(f"Route: {route_for(matches).value}")


if __name__ == "__main__":
    main()

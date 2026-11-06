"""Vendor research with domain filtering, grounding checks and labelled fallback."""

import time
from collections.abc import Callable
from typing import Any, Literal
from urllib.parse import urlsplit

from pydantic import BaseModel, model_validator
from tavily import TavilyClient

from flowmedic.config import get_settings
from flowmedic.graph.state import PlanStep, Source, VendorFindings
from flowmedic.knowledge.loaders import load_profile
from flowmedic.llm import get_llm
from flowmedic.prompts import (
    VENDOR_FALLBACK_V1,
    VENDOR_GROUNDING_V1,
    VENDOR_REPAIR_V1,
    VENDOR_RESEARCH_V1,
)
from flowmedic.tools.redact import redact
from flowmedic.tracing import run_config, traced_tool

ModelCall = Callable[[str, type[BaseModel], str, str], Any]


def _model(role: str, schema: type[BaseModel], prompt: str, payload: str) -> Any:
    config = run_config(prompt_version="VENDOR_V1", run_name="vendor_findings")
    config["metadata"] = {
        **config.get("metadata", {}),
        "model": get_settings().model_name(role),
    }
    for attempt in range(min(2, get_settings().max_llm_calls)):
        try:
            result = (
                get_llm(role)
                .with_structured_output(schema)
                .invoke(
                    [("system", prompt), ("human", payload)],
                    config=config,
                )
            )
            return schema.model_validate(result)
        except Exception:
            if attempt:
                raise
            prompt += "\n" + VENDOR_REPAIR_V1
    raise ValueError("MAX_LLM_CALLS reached before vendor research")


@traced_tool
def _search(client: Any, query: str, domains: list[str] | None) -> dict[str, Any]:
    options = {"include_domains": domains} if domains else {}
    return client.search(query=query, max_results=5, **options)


@traced_tool
def search_vendor_docs(
    platform: str,
    version: str | None,
    signatures: list[str],
    problem_summary: str,
    *,
    model_call: ModelCall | None = None,
    client: Any = None,
) -> VendorFindings:
    """Retry each search once, broaden sparse results, then label model knowledge."""
    settings = get_settings()
    call = model_call or _model
    profile = load_profile(platform) if platform else {}
    query = redact(
        " ".join([platform, version or "", *signatures[:5], problem_summary[:400]])
    ).text
    domains = list(
        dict.fromkeys(
            urlsplit("https://" + value).netloc
            for value in profile.get("doc_sources", {}).get("trusted", [])
        )
    )
    client = client or (
        TavilyClient(api_key=settings.tavily_api_key.get_secret_value())
        if settings.tavily_api_key.get_secret_value()
        else None
    )

    def fetch(allowed: list[str] | None) -> list[dict[str, str]]:
        if client is None:
            return []
        for attempt in range(2):
            try:
                raw = _search(client, query, allowed)
                useful = []
                for item in raw.get("results", []):
                    url = item.get("url", "")
                    content = redact(item.get("content", "")).text
                    host = urlsplit(url).hostname or ""
                    if (
                        urlsplit(url).scheme in {"http", "https"}
                        and content.strip()
                        and (
                            not allowed
                            or any(host == d or host.endswith("." + d) for d in allowed)
                        )
                    ):
                        useful.append({"url": url, "content": content})
                if useful:
                    return list({r["url"]: r for r in useful}.values())
            except Exception:
                pass
            if attempt == 0:
                time.sleep(settings.retry_backoff)
        return []

    results = fetch(domains or None)
    if results and len(results) < 2:
        results = list({r["url"]: r for r in results + fetch(None)}.values())
    if results:
        urls = {r["url"] for r in results}

        AllowedURL = Literal[tuple(sorted(urls))]

        class CitedStep(PlanStep):
            """Expose the exact allowed URL vocabulary to constrained decoding."""

            source: Literal["cited"] = "cited"
            source_ref: AllowedURL

        class CitedFindings(VendorFindings):
            """Reject unsupported provenance during structured validation/repair."""

            steps: list[CitedStep]
            urls: list[AllowedURL] = []

            @model_validator(mode="after")
            def validate_citations(self) -> "CitedFindings":
                if (
                    any(
                        s.source != Source.CITED or s.source_ref not in urls
                        for s in self.steps
                    )
                    or not set(self.urls) <= urls
                ):
                    raise ValueError("Every cited step must use a supplied result URL")
                return self

        response = call(
            "fast",
            CitedFindings,
            VENDOR_RESEARCH_V1 + "\n" + VENDOR_GROUNDING_V1,
            f"<untrusted_query>{query}</untrusted_query>\n"
            f"<untrusted_search_results>{results}</untrusted_search_results>",
        )
        findings = CitedFindings.model_validate(
            response.model_dump() if isinstance(response, BaseModel) else response
        )
        findings.urls = list(dict.fromkeys(s.source_ref for s in findings.steps))
        if not platform or not version:
            findings.notes += (
                " Platform/version context is incomplete; confirm documentation "
                "applicability before any change."
            )
        return VendorFindings.model_validate(findings.model_dump())
    findings = VendorFindings.model_validate(
        call(
            "strong",
            VendorFindings,
            VENDOR_FALLBACK_V1,
            f"<untrusted_query>{query}</untrusted_query>",
        )
    )
    findings.steps = [
        s.model_copy(update={"source": Source.MODEL, "source_ref": None})
        for s in findings.steps
    ]
    findings.urls = []
    findings.notes += (
        " Vendor search unavailable; consider opening a vendor support case."
    )
    return findings

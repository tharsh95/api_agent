from agent.app.graph.state import AgentState
from agent.app.services.repository_analyzer import (
    RepositoryAnalyzer,
)


analyzer = RepositoryAnalyzer()


def analyze_repository(
    state: AgentState,
) -> AgentState:
    files = (
        state.get("repository", {})
        .get("files", [])
    )

    detected_profile = analyzer.analyze(files)
    supplied_profile = state.get("repository_profile", {}) or {}

    # Use detected values as defaults, preserving valid supplied metadata.
    profile = dict(detected_profile)

    for key, value in supplied_profile.items():
        if value is None:
            continue

        if isinstance(value, str):
            if not value.strip() or value.strip().lower() == "unknown":
                continue

        profile[key] = value

    return {
        **state,
        "repository_profile": profile,
        "status": "repository_analyzed",
    }
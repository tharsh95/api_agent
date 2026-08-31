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

    profile = analyzer.analyze(files)

    return {
        **state,
        "repository_profile": profile,
        "status": "repository_analyzed",
    }
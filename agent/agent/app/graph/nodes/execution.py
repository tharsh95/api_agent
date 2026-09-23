from agent.app.graph.state import AgentState
from agent.app.services.code_change_generator import (
    CodeChangeGenerator,
)


def execute_plan(
    state: AgentState,
    code_change_generator=None,
) -> AgentState:
    plan = state["integration_plan"]

    generator = (
        code_change_generator
        or CodeChangeGenerator()
    )

    changes = generator.generate(
        repository=state.get("repository", {}),
        integration_plan=plan,
    )

    return {
        **state,
        "code_changes": changes,
        "status": "changes_generated",
    }

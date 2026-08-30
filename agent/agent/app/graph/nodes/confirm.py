from agent.app.graph.state import AgentState


def confirm_plan(
    state: AgentState,
) -> AgentState:

    confirmed = state.get("confirmed", False)

    if confirmed:
        return {
            **state,
            "confirmed": True,
            "status": "confirmed",
        }

    return {
        **state,
        "confirmed": False,
        "status": "awaiting_confirmation",
    }
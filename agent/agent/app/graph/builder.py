from langgraph.graph import START, END, StateGraph

from agent.app.graph.state import AgentState

from agent.app.graph.nodes.analyze_repository import (
    analyze_repository,
)
from agent.app.graph.nodes.find_integration import (
    find_integration,
)
from agent.app.graph.nodes.create_plan import (
    create_plan,
)
from agent.app.graph.nodes.confirm import (
    confirm_plan,
)
from agent.app.graph.nodes.execution import execute_plan
def route_after_confirmation(state: AgentState):
    if state.get("confirmed", False):
        return "execute"

    return "end"

def build_graph():
    builder = StateGraph(AgentState)

    builder.add_node(
        "analyze_repository",
        analyze_repository,
    )

    builder.add_node(
        "find_integration",
        find_integration,
    )

    builder.add_node(
        "create_plan",
        create_plan,
    )

    builder.add_node(
        "confirm_plan",
        confirm_plan,
    )

    builder.add_node(
    "execution",
    execute_plan,
)

    builder.add_edge(
        START,
        "analyze_repository",
    )

    builder.add_edge(
        "analyze_repository",
        "find_integration",
    )

    builder.add_edge(
        "find_integration",
        "create_plan",
    )

    builder.add_edge(
        "create_plan",
        "confirm_plan",
    )

    builder.add_conditional_edges(
    "confirm_plan",
    route_after_confirmation,
    {
        "execute": "execution",
        "end": END,
    },
)


    return builder.compile()
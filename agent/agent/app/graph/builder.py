from langgraph.graph import START, END, StateGraph

from agent.app.graph.state import AgentState
from agent.app.graph.nodes.analyze_repository import analyze_repository
from agent.app.graph.nodes.find_integration import find_integration
from agent.app.graph.nodes.create_plan import create_plan
from agent.app.graph.nodes.confirm import confirm_plan
from agent.app.graph.nodes.execution import execute_plan


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

    builder.add_edge(
        "confirm_plan",
        END,
    )

    return builder.compile()


def build_execution_graph(code_change_generator=None):
    builder = StateGraph(AgentState)

    def execution_node(state):
        return execute_plan(
            state,
            code_change_generator=code_change_generator,
        )

    builder.add_node(
        "execution",
        execution_node,
    )

    builder.add_edge(
        START,
        "execution",
    )

    builder.add_edge(
        "execution",
        END,
    )

    return builder.compile()

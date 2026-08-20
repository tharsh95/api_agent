from typing import TypedDict

from langgraph.graph import END, START, StateGraph


class AgentState(TypedDict):
    message: str
    response: str


def process_request(state: AgentState) -> AgentState:
    return {
        **state,
        "response": f"Agent received: {state['message']}",
    }


graph_builder = StateGraph(AgentState)

graph_builder.add_node("process_request", process_request)

graph_builder.add_edge(START, "process_request")
graph_builder.add_edge("process_request", END)

graph = graph_builder.compile()


if __name__ == "__main__":
    result = graph.invoke(
        {
            "message": "Hello AI Integration Engineer",
            "response": "",
        }
    )

    print(result)
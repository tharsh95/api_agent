from agent.app.main import graph


async def run_agent(message: str) -> dict:
    result = graph.invoke(
        {
            "message": message,
            "response": "",
        }
    )

    return result
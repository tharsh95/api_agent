from pprint import pprint

from agent.app.runtime import graph

def main() -> None:
    initial_state = {
    "project_id": project_id,
    "user_request": user_request,

    "repository": {},

    "repository_profile": {},
    "integration_candidates": [],
    "integration_plan": None,

    "confirmation_required": True,
    "confirmed": False,

    "status": "started",
    "error": None,
}
    result = graph.invoke(initial_state)

    pprint(result)


if __name__ == "__main__":
    main()
from agent.app.graph.state import AgentState


def create_plan(
    state: AgentState,
) -> AgentState:

    candidates = state.get(
        "integration_candidates",
        [],
    )

    profile = state.get(
        "repository_profile",
        {},
    )

    request = state["user_request"]

    dependencies = []

    if "stripe" in request.lower():
        if profile.get("language") in {
            "JavaScript",
            "TypeScript",
            "Python",
        }:
            dependencies.append("stripe")

    files_to_modify = [
        candidate["file"]
        for candidate in candidates
        if candidate.get("file")
        and candidate["file"] != "unknown"
    ]

    steps = []

    for dependency in dependencies:
        steps.append(
            {
                "type": "dependency",
                "dependency": dependency,
            }
        )

    for file in files_to_modify:
        steps.append(
            {
                "type": "modify_file",
                "file": file,
                "purpose": (
                    "Update this file for the "
                    "requested integration"
                ),
            }
        )

    steps.append(
        {
            "type": "configuration",
            "purpose": (
                "Add or update integration "
                "configuration"
            ),
        }
    )

    steps.append(
        {
            "type": "test",
            "purpose": "Add tests for the integration",
        }
    )

    plan = {
        "request": request,
        "integration": {
            "provider": "stripe"
            if "stripe" in request.lower()
            else "unknown",
            "type": "payment"
            if "stripe" in request.lower()
            else "unknown",
        },
        "files_to_modify": files_to_modify,
        "dependencies": dependencies,
        "steps": steps,
        "requires_confirmation": True,
    }

    return {
        **state,
        "integration_plan": plan,
        "confirmation_required": True,
        "status": "plan_created",
    }
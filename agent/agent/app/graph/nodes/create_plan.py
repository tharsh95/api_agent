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
    request_lower = request.lower()

    dependencies = []

    if "stripe" in request_lower:
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
        and candidate.get("file") != "unknown"
    ]

    steps = []

    for dependency in dependencies:
        steps.append({
            "type": "dependency",
            "dependency": dependency,
        })

    for file in files_to_modify:
        steps.append({
            "type": "modify_file",
            "file": file,
            "purpose": (
                "Update this file for the requested "
                "integration"
            ),
        })

    # Only add configuration when the request actually
    # requires integration configuration.
    if "stripe" in request_lower:
        steps.append({
            "type": "configuration",
            "purpose": "Add or update Stripe configuration",
        })

    if "health" in request_lower and profile.get("language") == "JavaScript":
        steps.append({
            "type": "create_file",
            "file": "tests/health.test.js",
            "purpose": (
                "Add a Jest and Supertest test for GET /api/health "
                "that verifies the response status and JSON body"
            ),
        })
    else:
        steps.append({
            "type": "test",
            "purpose": "Add tests for the requested change",
        })

    plan = {
        "request": request,
        "integration": {
            "provider": "stripe"
            if "stripe" in request_lower
            else "unknown",
            "type": "payment"
            if "stripe" in request_lower
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
        "confirmed": state.get("confirmed", False),
        "status": "plan_created",
    }

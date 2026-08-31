from agent.app.graph.state import AgentState


def execute_plan(
    state: AgentState,
) -> AgentState:

    plan = state["integration_plan"]

    changes = []

    for step in plan["steps"]:

        step_type = step.get("type")

        if step_type == "dependency":
            changes.append(
                {
                    "type": "dependency",
                    "dependency": step["dependency"],
                    "action": "add",
                }
            )

        elif step_type == "modify_file":
            changes.append(
                {
                    "type": "file",
                    "file": step["file"],
                    "action": "modify",
                    "purpose": step.get("purpose"),
                }
            )

        elif step_type == "configuration":
            changes.append(
                {
                    "type": "configuration",
                    "action": "update",
                    "purpose": step.get("purpose"),
                }
            )

        elif step_type == "test":
            changes.append(
                {
                    "type": "test",
                    "action": "add",
                    "purpose": step.get("purpose"),
                }
            )

    return {
        **state,
        "code_changes": changes,
        "status": "changes_generated",
    }
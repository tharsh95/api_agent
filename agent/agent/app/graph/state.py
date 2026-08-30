from typing import TypedDict


class AgentState(TypedDict):
    project_id: str
    user_request: str

    repository: dict
    repository_profile: dict

    integration_candidates: list[dict]
    integration_plan: dict | None

    confirmation_required: bool
    confirmed: bool
    code_changes: list[dict]

    status: str
    error: str | None
from pathlib import PurePosixPath
import re

from agent.app.graph.state import AgentState


CONTEXT_FILES = {
    "package.json", "pyproject.toml", "requirements.txt",
    "prisma/schema.prisma", "tsconfig.json",
}

IGNORED_PARTS = {
    "node_modules", ".git", "dist", "build", "coverage",
    "__pycache__", ".next", "venv", ".venv",
}

TEST_PARTS = {"test", "tests", "__tests__", "spec"}
ENTRY_PARTS = {
    "routes", "router", "controllers", "controller",
    "api", "app", "pages",
}
SERVICE_PARTS = {
    "services", "service", "handlers", "usecases", "use_cases",
}
MODEL_PARTS = {
    "models", "entities", "schemas", "dto", "dtos",
    "repositories", "repository",
}

GENERIC_TOKENS = {
    "please", "add", "create", "build", "implement", "make",
    "develop", "integrate", "support", "feature", "application",
    "system", "using", "with", "for", "into", "from", "the",
    "and", "that", "this", "should", "allow", "user", "users",
    "new", "existing", "want", "need", "able",
}

PAYMENT_TOKENS = {
    "stripe", "payment", "payments", "checkout", "billing",
    "invoice", "subscription", "transaction", "charge",
}


def _tokens(value: str) -> set[str]:
    value = re.sub(r"([a-z])([A-Z])", r"\\1 \\2", value)
    return {
        token.lower()
        for token in re.findall(r"[a-zA-Z0-9]+", value)
        if len(token) > 1
    }


def _is_ignored(path: str) -> bool:
    return bool(set(PurePosixPath(path).parts) & IGNORED_PARTS)


def _file_role(path: str) -> set[str]:
    parts = {part.lower() for part in PurePosixPath(path).parts}
    roles = set()

    if parts & ENTRY_PARTS:
        roles.add("entry")
    if parts & SERVICE_PARTS:
        roles.add("service")
    if parts & MODEL_PARTS:
        roles.add("model")
    if parts & TEST_PARTS:
        roles.add("test")

    return roles


def find_integration(state: AgentState) -> AgentState:
    files = state.get("repository", {}).get("files", [])
    request = state.get("user_request", "")
    request_tokens = _tokens(request)

    # Normalize common domain synonyms and singular/plural forms.
    if "payments" in request_tokens:
        request_tokens.add("payment")
    if "payment" in request_tokens:
        request_tokens.add("payments")

    if "tasks" in request_tokens:
        request_tokens.add("task")
    if "task" in request_tokens:
        request_tokens.add("tasks")

    domain_tokens = request_tokens - GENERIC_TOKENS

    is_payment = bool(
        request_tokens & {
            "stripe", "payment", "payments", "checkout",
            "billing", "invoice", "subscription"
        }
    )

    candidates = []

    for file in files:
        path = file.get("path", "")
        content = file.get("content", "")

        if not path or _is_ignored(path):
            continue

        path_tokens = _tokens(path)
        content_tokens = _tokens(content)
        roles = _file_role(path)

        # Stripe requests must not select unrelated services.
        if is_payment:
            relevant_tokens = domain_tokens & PAYMENT_TOKENS
            path_matches = relevant_tokens & path_tokens
            content_matches = relevant_tokens & content_tokens
        else:
            path_matches = domain_tokens & path_tokens
            content_matches = domain_tokens & content_tokens

        score = 0
        reasons = []

        if path_matches:
            score += 8 * len(path_matches)
            reasons.append(
                "Request terms in path: "
                + ", ".join(sorted(path_matches))
            )

        if content_matches:
            score += min(12, 2 * len(content_matches))
            reasons.append(
                "Request terms in source: "
                + ", ".join(sorted(content_matches))
            )

        if "entry" in roles:
            score += 2
            reasons.append("Application entry point or route")

        if "service" in roles:
            score += 3
            reasons.append("Service or business logic")

        if "model" in roles:
            score += 2
            reasons.append("Data model or persistence layer")

        if "test" in roles:
            score += 1
            reasons.append("Existing test file")

        if path in CONTEXT_FILES:
            score += 1
            reasons.append("Repository configuration context")

        # For generic requests, require a meaningful domain match.
        # Role alone is insufficient to select an unrelated file.
        if score <= 0:
            continue

        if not is_payment and not (
            path_matches or content_matches
        ):
            continue

        if is_payment and not (
            path_matches
            or content_matches
            or path in CONTEXT_FILES
            or "entry" in roles
        ):
            continue

        candidates.append({
            "file": path,
            "score": score,
            "role": sorted(roles),
            "reason": "; ".join(reasons),
        })

    candidates.sort(
        key=lambda item: (-item["score"], item["file"])
    )

    return {
        **state,
        "integration_candidates": candidates[:12],
        "status": "integration_candidates_found",
    }

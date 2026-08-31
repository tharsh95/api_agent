from agent.app.graph.state import AgentState


def find_integration(
    state: AgentState,
) -> AgentState:

    files = (
        state.get("repository", {})
        .get("files", [])
    )

    request = state["user_request"].lower()

    candidates = []

    for file in files:
        path = file.get("path", "")
        content = file.get("content", "")

        if not path:
            continue

        lower_path = path.lower()
        lower_content = content.lower()

        # Stripe / payment integration
        if "stripe" in request:

            # Existing payment-related files
            if (
                "payment" in lower_path
                or "billing" in lower_path
                or "checkout" in lower_path
            ):
                candidates.append({
                    "file": path,
                    "reason": (
                        "This file appears to contain "
                        "payment or checkout logic and is "
                        "a likely Stripe integration point."
                    ),
                    "confidence": 0.95,
                })
                continue

            # Payment-related API code
            if (
                "checkout" in lower_content
                or "payment" in lower_content
                or "billing" in lower_content
            ):
                candidates.append({
                    "file": path,
                    "reason": (
                        "This file contains payment-related "
                        "API logic and may need to expose "
                        "the Stripe integration."
                    ),
                    "confidence": 0.85,
                })
                continue

            # Dependency configuration
            if path == "package.json":
                candidates.append({
                    "file": path,
                    "reason": (
                        "Package configuration is a likely "
                        "location for adding the Stripe SDK."
                    ),
                    "confidence": 0.80,
                })
                continue

        # Generic integration detection
        else:
            integration_keywords = (
                "api",
                "route",
                "service",
                "client",
                "integration",
            )

            if any(
                keyword in lower_path
                for keyword in integration_keywords
            ):
                candidates.append({
                    "file": path,
                    "reason": (
                        "This file may contain external "
                        "integration logic."
                    ),
                    "confidence": 0.5,
                })

    candidates.sort(
        key=lambda candidate: candidate["confidence"],
        reverse=True,
    )

    return {
        **state,
        "integration_candidates": candidates[:5],
        "status": "integration_point_found",
    }
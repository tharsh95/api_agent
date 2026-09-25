from agent.app.graph.state import AgentState


def find_integration(
    state: AgentState,
) -> AgentState:

    files = state.get("repository", {}).get("files", [])
    request = state["user_request"].lower()

    candidates = []

    # Stripe / payment integration
    if "stripe" in request:
        for file in files:
            path = file.get("path", "")
            content = file.get("content", "")

            if not path:
                continue

            lower_path = path.lower()
            lower_content = content.lower()

            # Documentation should never be selected as an
            # implementation target.
            if lower_path.endswith(
                (".md", ".mdx", ".txt")
            ):
                continue

            if (
                "payment" in lower_path
                or "billing" in lower_path
                or "checkout" in lower_path
            ):
                candidates.append({
                    "file": path,
                    "reason": (
                        "This file appears to contain payment "
                        "or checkout logic and is a likely "
                        "Stripe integration point."
                    ),
                    "confidence": 0.95,
                })
                continue

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

            if path == "package.json":
                candidates.append({
                    "file": path,
                    "reason": (
                        "Package configuration is a likely "
                        "location for adding the Stripe SDK."
                    ),
                    "confidence": 0.80,
                })

    # Health-check endpoint
    elif any(
        keyword in request
        for keyword in (
            "health",
            "health check",
            "health-check",
            "healthcheck",
        )
    ):
        health_keywords = (
            "health",
            "app.js",
            "server.js",
            "index.js",
            "routes",
        )

        for file in files:
            path = file.get("path", "")
            content = file.get("content", "")

            if not path:
                continue

            lower_path = path.lower()
            lower_content = content.lower()

            score = 0.0
            reason = ""

            if "health" in lower_path:
                score = 0.95
                reason = "Existing health-related file."

            elif lower_path.endswith("app.js"):
                score = 0.95
                reason = (
                    "Express application file is the appropriate "
                    "location for the health-check endpoint."
                )

            elif lower_path.endswith("server.js"):
                score = 0.60
                reason = (
                    "Server entry point, but the Express application "
                    "is defined elsewhere."
                )

            elif lower_path.endswith("index.js"):
                score = 0.50
                reason = (
                    "Possible application entry point for the "
                    "health-check endpoint."
                )

            elif (
                "express()" in lower_content
                or "app.use(" in lower_content
                or "app.get(" in lower_content
            ) and "route" in lower_path:
                score = 0.75
                reason = (
                    "Express route file is a likely "
                    "location for the health-check endpoint."
                )

            if score:
                candidates.append({
                    "file": path,
                    "reason": reason,
                    "confidence": score,
                })

    candidates.sort(
        key=lambda candidate: candidate["confidence"],
        reverse=True,
    )

    if "health" in request:
        candidates = candidates[:1]

    return {
        **state,
        "integration_candidates": candidates[:5],
        "status": "integration_point_found",
    }

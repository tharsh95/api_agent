from langchain_core.prompts import few_shot_with_templates
from pathlib import PurePosixPath

from agent.app.graph.state import AgentState


TEST_DIR_NAMES = {"test", "tests", "__tests__", "spec"}


def _is_test_file(path: str) -> bool:
    parts = {part.lower() for part in PurePosixPath(path).parts}
    name = PurePosixPath(path).name.lower()

    return (
        bool(parts & TEST_DIR_NAMES)
        or name.startswith("test_")
        or ".test." in name
        or ".spec." in name
    )


def _test_directory(files: list[dict]) -> str:
    for item in files:
        path = item.get("path", "")
        if path and _is_test_file(path):
            parent = str(PurePosixPath(path).parent)
            if parent != ".":
                return parent
    return "tests"


def _test_extension(profile: dict) -> str:
    language = profile.get("language", "").lower()

    return {
        "python": ".py",
        "javascript": ".test.js",
        "typescript": ".test.ts",
        "java": "Test.java",
        "go": "_test.go",
    }.get(language, "")


def _test_framework_available(profile: dict) -> bool:
    return profile.get("test_framework", "unknown").lower() != "unknown"


def create_plan(state: AgentState) -> AgentState:
    candidates = state.get("integration_candidates", [])
    repository = state.get("repository", {})
    files = repository.get("files", [])
    profile = state.get("repository_profile", {})
    request = state.get("user_request", "").strip()
    request_lower = request.lower()

    is_stripe = "stripe" in request_lower
    existing_paths = {
        item.get("path") for item in files if item.get("path")
    }

    steps = []
    files_to_modify = []

    # Keep only relevant discovered files.
    selected = [
        candidate
        for candidate in candidates
        if candidate.get("file") in existing_paths
        and candidate.get(
            "score",
            candidate.get("confidence", 0)
            * 10
        ) >= 2
    ][:6]

    for candidate in selected:
        path = candidate["file"]

        if path in files_to_modify:
            continue

        files_to_modify.append(path)
        steps.append({
            "type": "modify_file",
            "file": path,
            "purpose": (
                "Implement the requested change in this existing "
                f"file: {request}"
            ),
            "reason": candidate.get("reason", ""),
        })

    # Preserve the established Stripe dependency behavior.
    dependencies = []
    if is_stripe:
        dependencies.append("stripe")
        steps.insert(0, {
            "type": "dependency",
            "dependency": "stripe",
            "purpose": "Add the Stripe SDK dependency.",
        })

    test_framework = profile.get("test_framework", "unknown")

    if _test_framework_available(profile):
        existing_tests = [
            item["path"]
            for item in files
            if item.get("path") and _is_test_file(item["path"])
        ]

        if existing_tests:
            test_path = existing_tests[0]

            if test_path not in files_to_modify:
                files_to_modify.append(test_path)
                steps.append({
                    "type": "modify_file",
                    "file": test_path,
                    "purpose": (
                        "Add or update tests for the requested "
                        "behavior using existing conventions."
                    ),
                })
        else:
            extension = _test_extension(profile)

            if extension:
                test_dir = _test_directory(files)
                test_path = f"{test_dir}/test_feature{extension}"

                if test_path not in existing_paths:
                    steps.append({
                        "type": "create_file",
                        "file": test_path,
                        "purpose": (
                            f"Create tests using {test_framework} "
                            f"for the requested behavior: {request}. "
                            "Follow the detected language and framework."
                        ),
                    })

    # Add an explicit test execution step to the integration plan.
    if _test_framework_available(profile):
        steps.append({
            "type": "test",
            "framework": test_framework,
            "purpose": (
                f"Run {test_framework} tests to verify the requested "
                f"integration: {request}"
            ),
        })

    configuration_files = [
        candidate["file"]
        for candidate in candidates
        if candidate.get("file") in existing_paths
        and candidate["file"] in {
            "package.json", "pyproject.toml", "requirements.txt",
        }
    ]

    # Add explicit configuration steps for detected config files.
    for config_file in configuration_files:
        steps.append({
            "type": "configuration",
            "file": config_file,
            "purpose": (
                f"Update configuration for the requested integration: {request}"
            ),
        })

    plan = {
        "request": request,
        "integration": {
            "provider": "stripe" if is_stripe else None,
            "type": "payment" if is_stripe else "feature",
        },
        "repository_profile": profile,
        "files_to_modify": files_to_modify,
        "configuration_files": configuration_files,
        "dependencies": dependencies,
        "steps": steps,
        "requires_confirmation": True,
    }

    has_code_steps = any(
        step.get("type") in {"modify_file", "create_file"}
        for step in steps
    )
    return {
        **state,
        "integration_plan": plan,
        "confirmation_required": True,
        "confirmed": state.get("confirmed", False),
        "status": (
            "awaiting_confirmation"
            if has_code_steps
            else "planning_needs_clarification"
        ),
        "error": (
            None
            if has_code_steps
            else (
                "No relevant implementation files or safe file "
                "creation targets were found. More repository context "
                "or clarification is required."
            )
        ),
    }

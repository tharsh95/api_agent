from agent.app.graph.builder import build_graph


def test_integration_graph():
    graph = build_graph()

    result = graph.invoke(
        {
            "project_id": "test-project",
            "user_request": "Integrate Stripe payments",
            "repository": {
                "files": [
                    {
                        "path": "package.json",
                        "content": """
                        {
                          "dependencies": {
                            "next": "15.0.0",
                            "@prisma/client": "6.0.0"
                          },
                          "devDependencies": {
                            "prisma": "6.0.0",
                            "jest": "30.0.0"
                          }
                        }
                        """,
                    },
                    {
                        "path": "package-lock.json",
                        "content": "{}",
                    },
                    {
                        "path": "prisma/schema.prisma",
                        "content": """
                        datasource db {
                          provider = "postgresql"
                        }
                        """,
                    },
                    {
                        "path": "src/app/page.tsx",
                        "content": "...",
                    },
                ],
            },
            "repository_profile": {},
            "integration_candidates": [],
            "integration_plan": None,
            "status": "started",
            "confirmation_required": True,
            "confirmed": False,
            "error": None,
        }
    )

    assert result["status"] == "awaiting_confirmation"

    assert result["repository_profile"]["language"] == "TypeScript"
    assert result["repository_profile"]["framework"] == "Next.js"
    assert result["repository_profile"]["database"] == "PostgreSQL"
    assert result["repository_profile"]["orm"] == "Prisma"
    assert result["repository_profile"]["package_manager"] == "npm"
    assert result["repository_profile"]["test_framework"] == "Jest"

    assert result["integration_candidates"]

    assert any(
        candidate["file"] == "package.json"
        for candidate in result["integration_candidates"]
    )

    assert result["integration_plan"] is not None
    assert result["integration_plan"]["requires_confirmation"] is True


def test_finds_payment_integration_point():
    graph = build_graph()

    result = graph.invoke(
        {
            "project_id": "test-project",
            "user_request": "Integrate Stripe payments",
            "repository": {
                "files": [
                    {
                        "path": "src/services/payment_service.py",
                        "content": """
                        class PaymentService:
                            def create_payment(self):
                                pass
                        """,
                    },
                    {
                        "path": "src/api/routes/checkout.py",
                        "content": """
                        @router.post("/checkout")
                        async def checkout():
                            pass
                        """,
                    },
                    {
                        "path": "package.json",
                        "content": "{}",
                    },
                ],
            },
            "repository_profile": {},
            "integration_candidates": [],
            "integration_plan": None,
            "status": "started",
            "error": None,
        },
    )

    candidates = result["integration_candidates"]

    assert candidates

    assert any(
        candidate["file"]
        == "src/services/payment_service.py"
        for candidate in candidates
    )

    plan = result["integration_plan"]

    assert plan["request"] == (
        "Integrate Stripe payments"
    )

    assert "stripe" in plan["dependencies"]

    assert (
        "src/services/payment_service.py"
        in plan["files_to_modify"]
    )

    assert plan["requires_confirmation"] is True
    assert result["confirmation_required"] is True
    assert result["confirmed"] is False

    assert plan["steps"]

    assert any(
        step.get("dependency") == "stripe"
        for step in plan["steps"]
    )

def test_no_integration_point_found():
    graph = build_graph()

    result = graph.invoke(
        {
            "project_id": "test-project",
            "user_request": "Integrate Stripe payments",
            "repository": {
                "files": [
                    {
                        "path": "README.md",
                        "content": "This is a project.",
                    },
                    {
                        "path": "src/utils/logger.py",
                        "content": """
                        def log(message):
                            print(message)
                        """,
                    },
                ],
            },
            "repository_profile": {},
            "integration_candidates": [],
            "integration_plan": None,
            "status": "started",
            "error": None,
        }
    )

    assert result["integration_candidates"] == []

def test_creates_stripe_integration_plan():

    graph = build_graph()

    result = graph.invoke(
        {
            "project_id": "test-project",
            "user_request": "Integrate Stripe payments",
            "repository": {
                "files": [
                    {
                        "path": "package.json",
                        "content": """
                        {
                          "dependencies": {
                            "next": "15.0.0"
                          }
                        }
                        """,
                    },
                    {
                        "path": "src/services/payment_service.py",
                        "content": """
                        class PaymentService:
                            def create_payment(self):
                                pass
                        """,
                    },
                    {
                        "path": "src/api/routes/checkout.py",
                        "content": """
                        @router.post("/checkout")
                        async def checkout():
                            pass
                        """,
                    },
                ],
            },
            "repository_profile": {
                "language": "Python",
                "framework": "unknown",
                "database": "unknown",
                "orm": "unknown",
                "package_manager": "pip",
                "test_framework": "pytest",
            },
            "integration_candidates": [],
            "integration_plan": None,
            "status": "started",
            "error": None,
        }
    )

    assert result["status"] == "awaiting_confirmation"

    candidates = result["integration_candidates"]

    assert candidates

    assert any(
        candidate["file"]
        == "src/services/payment_service.py"
        for candidate in candidates
    )

    plan = result["integration_plan"]

    assert plan["request"] == (
        "Integrate Stripe payments"
    )

    assert "stripe" in plan["dependencies"]

    assert (
        "src/services/payment_service.py"
        in plan["files_to_modify"]
    )

    assert (
        "src/api/routes/checkout.py"
        in plan["files_to_modify"]
    )

    assert plan["requires_confirmation"] is True


def test_does_not_select_unrelated_files_for_stripe():
    graph = build_graph()

    result = graph.invoke(
        {
            "project_id": "test-project",
            "user_request": "Integrate Stripe payments",
            "repository": {
                "files": [
                    {
                        "path": "src/services/email_service.py",
                        "content": """
                        class EmailService:
                            def send_email(self):
                                pass
                        """,
                    },
                    {
                        "path": "src/utils/logger.py",
                        "content": """
                        def log(message):
                            print(message)
                        """,
                    },
                ],
            },
            "repository_profile": {},
            "integration_candidates": [],
            "integration_plan": None,
            "status": "started",
            "error": None,
        },
    )

    candidates = result["integration_candidates"]

    assert not any(
        candidate["file"]
        == "src/services/email_service.py"
        for candidate in candidates
    )

    assert not any(
        candidate["file"]
        == "src/utils/logger.py"
        for candidate in candidates
    )

# def test_plan_requires_confirmation():

#     graph = build_graph()

#     result = graph.invoke(
#         {
#             "project_id": "test-project",
#             "user_request": "Integrate Stripe payments",
#             "repository": {
#                 "files": [
#                     {
#                         "path": "package.json",
#                         "content": """
#                         {
#                           "dependencies": {
#                             "next": "15.0.0"
#                           }
#                         }
#                         """,
#                     },
#                     {
#                         "path": "src/services/payment_service.py",
#                         "content": """
#                         class PaymentService:
#                             def create_payment(self):
#                                 pass
#                         """,
#                     },
#                 ],
#             },
#             "repository_profile": {},
#             "integration_candidates": [],
#             "integration_plan": None,
#             "confirmation_required": True,
#             "confirmed": False,
#             "status": "started",
#             "error": None,
#         },
#     )

#     assert result["status"] == (
#         "awaiting_confirmation"
#     )

#     assert result["confirmation_required"] is True

#     assert result["confirmed"] is False

#     assert result["integration_plan"] is not None


def test_confirmed_plan_returns_confirmed():

    graph = build_graph()

    result = graph.invoke(
        {
            "project_id": "test-project",
            "user_request": "Integrate Stripe payments",
            "repository": {
                "files": [
                    {
                        "path": "package.json",
                        "content": "{}",
                    }
                ],
            },
            "repository_profile": {
                "language": "TypeScript",
                "framework": "Next.js",
                "database": "unknown",
                "orm": "unknown",
                "package_manager": "npm",
                "test_framework": "Jest",
            },
            "integration_candidates": [
                {
                    "file": "package.json",
                    "reason": "Stripe dependency",
                    "confidence": 0.9,
                }
            ],
            "integration_plan": None,
            "status": "started",
            "confirmation_required": True,
            "confirmed": True,
            "code_changes": [],
            "error": None,
        },
    )

    assert result["status"] == "changes_generated"
    assert result["confirmed"] is True
    assert result["code_changes"]


def test_stripe_plan_has_structured_steps():

    graph = build_graph()

    result = graph.invoke(
        {
            "project_id": "test-project",
            "user_request": "Integrate Stripe payments",
            "repository": {
                "files": [
                    {
                        "path": "package.json",
                        "content": "{}",
                    },
                    {
                        "path": "src/services/payment_service.py",
                        "content": """
                        class PaymentService:
                            def create_payment(self):
                                pass
                        """,
                    },
                ],
            },
            "repository_profile": {
                "language": "Python",
                "framework": "unknown",
                "database": "unknown",
                "orm": "unknown",
                "package_manager": "pip",
                "test_framework": "pytest",
            },
            "integration_candidates": [
                {
                    "file": "src/services/payment_service.py",
                    "reason": "Payment service",
                    "confidence": 0.95,
                },
            ],
            "integration_plan": None,
            "status": "started",
            "confirmation_required": True,
            "confirmed": False,
            "code_changes": [],
            "error": None,
        },
    )

    plan = result["integration_plan"]

    assert plan is not None

    assert plan["integration"]["provider"] == "stripe"
    assert plan["integration"]["type"] == "payment"

    assert any(
        step["type"] == "dependency"
        and step["dependency"] == "stripe"
        for step in plan["steps"]
    )

    assert any(
        step["type"] == "modify_file"
        and step["file"]
        == "src/services/payment_service.py"
        for step in plan["steps"]
    )

    assert any(
        step["type"] == "configuration"
        for step in plan["steps"]
    )

    assert any(
        step["type"] == "test"
        for step in plan["steps"]
    )
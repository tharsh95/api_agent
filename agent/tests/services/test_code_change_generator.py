from unittest.mock import MagicMock

from agent.app.services.code_change_generator import (
    CodeChangeGenerator,
)


def test_generates_code_change_from_llm_response():
    client = MagicMock()

    client.chat.completions.create.return_value = MagicMock(
        choices=[
            MagicMock(
                message=MagicMock(
                    content=(
                        "import stripe\n\n"
                        "def pay():\n"
                        "    return stripe.PaymentIntent.create()\n"
                    )
                )
            )
        ]
    )

    repository = {
        "owner": "acme",
        "name": "payments-api",
        "default_branch": "main",
        "files": [
            {
                "path": "src/payment.py",
                "content": (
                    "def pay():\n"
                    "    pass\n"
                ),
            }
        ],
    }

    plan = {
        "request": "Integrate Stripe payments",
        "dependencies": ["stripe"],
        "steps": [
            {
                "type": "modify_file",
                "file": "src/payment.py",
                "purpose": "Update payment integration",
            }
        ],
        "requires_confirmation": True,
    }

    generator = CodeChangeGenerator(client=client)

    changes = generator.generate(
        repository,
        plan,
    )

    assert len(changes) == 1

    change = changes[0]

    assert change["file_path"] == "src/payment.py"
    assert change["action"] == "modify"

    assert change["original_content"] == (
        "def pay():\n"
        "    pass\n"
    )

    assert change["new_content"] == (
        "import stripe\n\n"
        "def pay():\n"
        "    return stripe.PaymentIntent.create()\n"
    )

    assert "--- a/src/payment.py" in change["diff"]
    assert "+++ b/src/payment.py" in change["diff"]
    assert "+import stripe" in change["diff"]

    client.chat.completions.create.assert_called_once()


def test_generates_no_change_when_llm_returns_same_content():
    client = MagicMock()

    content = (
        "def pay():\n"
        "    pass\n"
    )

    client.chat.completions.create.return_value = MagicMock(
        choices=[
            MagicMock(
                message=MagicMock(
                    content=content
                )
            )
        ]
    )

    repository = {
        "files": [
            {
                "path": "src/payment.py",
                "content": content,
            }
        ]
    }

    plan = {
        "steps": [
            {
                "type": "modify_file",
                "file": "src/payment.py",
                "purpose": "Update payment integration",
            }
        ]
    }

    generator = CodeChangeGenerator(client=client)

    changes = generator.generate(
        repository,
        plan,
    )

    assert changes == []


def test_ignores_files_not_present_in_repository():
    client = MagicMock()

    repository = {
        "files": [
            {
                "path": "package.json",
                "content": "{}",
            }
        ]
    }

    plan = {
        "steps": [
            {
                "type": "modify_file",
                "file": "src/payment.py",
                "purpose": "Update payment integration",
            }
        ]
    }

    generator = CodeChangeGenerator(client=client)

    changes = generator.generate(
        repository,
        plan,
    )

    assert changes == []

    client.chat.completions.create.assert_not_called()


def test_removes_markdown_code_fences():
    client = MagicMock()

    client.chat.completions.create.return_value = MagicMock(
        choices=[
            MagicMock(
                message=MagicMock(
                    content=(
                        "```python\n"
                        "def pay():\n"
                        "    return True\n"
                        "```"
                    )
                )
            )
        ]
    )

    repository = {
        "files": [
            {
                "path": "src/payment.py",
                "content": "def pay():\n    pass\n",
            }
        ]
    }

    plan = {
        "steps": [
            {
                "type": "modify_file",
                "file": "src/payment.py",
                "purpose": "Update payment integration",
            }
        ]
    }

    generator = CodeChangeGenerator(client=client)

    changes = generator.generate(
        repository,
        plan,
    )

    assert changes[0]["new_content"] == (
        "def pay():\n"
        "    return True"
    )

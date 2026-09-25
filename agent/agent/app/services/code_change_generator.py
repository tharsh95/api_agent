from difflib import unified_diff
import json

from openai import OpenAI


class CodeChangeGenerator:
    def __init__(
        self,
        client=None,
        model: str = "gpt-4.1-mini",
    ):
        self.client = client
        self.model = model

    def _get_client(self):
        if self.client is None:
            self.client = OpenAI()

        return self.client

    def generate(
        self,
        repository: dict,
        integration_plan: dict,
    ) -> list[dict]:
        files = {
            file["path"]: file.get("content", "")
            for file in repository.get("files", [])
            if file.get("path")
        }

        changes = []

        for step in integration_plan.get("steps", []):
            if step.get("type") != "modify_file":
                continue

            file_path = step.get("file")

            if not file_path or file_path not in files:
                continue

            original_content = files[file_path]

            new_content = self._apply_change(
                file_path=file_path,
                original_content=original_content,
                integration_plan=integration_plan,
                step=step,
                repository=repository,
            )

            if new_content == original_content:
                continue

            diff = "".join(
                unified_diff(
                    original_content.splitlines(keepends=True),
                    new_content.splitlines(keepends=True),
                    fromfile=f"a/{file_path}",
                    tofile=f"b/{file_path}",
                )
            )

            changes.append(
                {
                    "file_path": file_path,
                    "action": "modify",
                    "original_content": original_content,
                    "new_content": new_content,
                    "diff": diff,
                }
            )

        return changes

    def _apply_change(
        self,
        file_path: str,
        original_content: str,
        integration_plan: dict,
        step: dict,
        repository: dict,
    ) -> str:
        prompt = self._build_prompt(
            file_path=file_path,
            original_content=original_content,
            integration_plan=integration_plan,
            step=step,
            repository=repository,
        )

        response = self._get_client().chat.completions.create(
            model=self.model,
            temperature=0,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a senior software engineer modifying "
                        "an existing repository.\n\n"
                        "Your task is to modify exactly one file based "
                        "on the approved integration plan.\n\n"
                        "Rules:\n"
                        "1. Return only the complete new file content.\n"
                        "2. Do not return Markdown fences.\n"
                        "3. Do not explain the changes.\n"
                        "4. Preserve existing functionality unless the "
                        "approved plan requires changing it.\n"
                        "5. Do not invent APIs, files, dependencies, "
                        "configuration, or repository behavior.\n"
                        "6. Make the smallest reasonable change required "
                        "by the approved plan.\n"
                        "7. Preserve the existing coding style where "
                        "possible.\n"
                        "8. The output must be valid source content for "
                        "the requested file."
                    ),
                },
                {
                    "role": "user",
                    "content": prompt,
                },
            ],
        )

        content = response.choices[0].message.content

        if not content:
            raise ValueError(
                f"LLM returned empty content for {file_path}"
            )

        return self._clean_response(content)

    def _build_prompt(
        self,
        file_path: str,
        original_content: str,
        integration_plan: dict,
        step: dict,
        repository: dict,
    ) -> str:
        repository_metadata = {
            "owner": repository.get("owner"),
            "name": repository.get("name"),
            "default_branch": repository.get("default_branch"),
        }

        return (
            "Approved integration plan:\n"
            f"{json.dumps(integration_plan, indent=2)}\n\n"
            "Current repository:\n"
            f"{json.dumps(repository_metadata, indent=2)}\n\n"
            "File to modify:\n"
            f"{file_path}\n\n"
            "Approved modification step:\n"
            f"{json.dumps(step, indent=2)}\n\n"
            "Current file content:\n"
            "```text\n"
            f"{original_content}\n"
            "```\n\n"
            "Modify this file according to the approved plan. "
            "Return the complete updated file content only."
        )

    @staticmethod
    def _clean_response(content: str) -> str:
        if not content:
            return content

        stripped = content.strip()

        # Preserve the original content exactly when the model did not
        # wrap the response in Markdown fences. This preserves trailing
        # newlines and avoids generating unnecessary diffs.
        if not (
            stripped.startswith("```")
            and stripped.endswith("```")
        ):
            return content

        lines = stripped.splitlines()

        if lines and lines[0].startswith("```"):
            lines = lines[1:]

        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]

        return "\n".join(lines)

import asyncio
import io
import json
import os
import shutil
import tempfile
import zipfile
from pathlib import Path

import httpx


class CodeValidationService:
    """
    Validates generated repository code inside a disposable
    Docker container. Generated code is never run on the API host.
    """

    def __init__(
        self,
        timeout_seconds: int = 300,
        memory_limit: str = "512m",
        cpu_limit: str = "1.0",
    ):
        self.timeout_seconds = timeout_seconds
        self.memory_limit = memory_limit
        self.cpu_limit = cpu_limit

    async def validate(
        self,
        installation_token: str,
        owner: str,
        repo: str,
        branch: str,
    ) -> dict:
        """
        Download a branch archive and run its Node.js tests
        in a disposable Docker container.
        """

        workdir = tempfile.mkdtemp(
            prefix="ai-engine-validation-"
        )

        try:
            archive_path = await self._download_archive(
                installation_token=installation_token,
                owner=owner,
                repo=repo,
                branch=branch,
                workdir=workdir,
            )

            repository_path = self._extract_archive(
                archive_path=archive_path,
                destination=workdir,
            )

            return await self._run_node_validation(
                repository_path=repository_path,
            )

        except Exception as exc:
            return {
                "status": "error",
                "passed": False,
                "exit_code": None,
                "stdout": "",
                "stderr": str(exc),
            }

        finally:
            shutil.rmtree(
                workdir,
                ignore_errors=True,
            )

    async def _download_archive(
        self,
        installation_token: str,
        owner: str,
        repo: str,
        branch: str,
        workdir: str,
    ) -> str:
        url = (
            f"https://api.github.com/repos/{owner}/{repo}"
            f"/zipball/{branch}"
        )

        async with httpx.AsyncClient(
            timeout=60,
            follow_redirects=True,
        ) as client:
            response = await client.get(
                url,
                headers={
                    "Accept": "application/vnd.github+json",
                    "Authorization": (
                        f"Bearer {installation_token}"
                    ),
                    "X-GitHub-Api-Version": "2026-03-10",
                },
            )

        response.raise_for_status()

        archive_path = os.path.join(
            workdir,
            "repository.zip",
        )

        with open(archive_path, "wb") as archive:
            archive.write(response.content)

        return archive_path

    @staticmethod
    def _extract_archive(
        archive_path: str,
        destination: str,
    ) -> str:
        repository_path = os.path.join(
            destination,
            "repository",
        )

        os.makedirs(
            repository_path,
            exist_ok=True,
        )

        with zipfile.ZipFile(archive_path) as archive:
            root = Path(repository_path).resolve()

            for member in archive.infolist():
                target = (
                    Path(repository_path) / member.filename
                ).resolve()

                if (
                    target != root
                    and root not in target.parents
                ):
                    raise ValueError(
                        "Unsafe path found in repository archive."
                    )

            archive.extractall(repository_path)

        extracted_dirs = list(
            Path(repository_path).iterdir()
        )

        if len(extracted_dirs) == 1 and extracted_dirs[0].is_dir():
            return str(extracted_dirs[0])

        return repository_path

    async def _run_node_validation(
        self,
        repository_path: str,
    ) -> dict:
        package_json = Path(
            repository_path,
            "package.json",
        )

        if not package_json.exists():
            return {
                "status": "skipped",
                "passed": True,
                "exit_code": 0,
                "stdout": "",
                "stderr": (
                    "No package.json found. "
                    "Node.js validation was skipped."
                ),
            }

        try:
            package = json.loads(
                package_json.read_text()
            )
        except (json.JSONDecodeError, OSError) as exc:
            return {
                "status": "failed",
                "passed": False,
                "exit_code": None,
                "stdout": "",
                "stderr": (
                    f"Invalid package.json: {exc}"
                ),
            }

        scripts = package.get("scripts", {})

        if not scripts.get("test"):
            return {
                "status": "skipped",
                "passed": True,
                "exit_code": 0,
                "stdout": "",
                "stderr": (
                    "No test script found in package.json. "
                    "Automated tests were skipped."
                ),
            }

        if Path(repository_path, "pnpm-lock.yaml").exists():
            install_command = (
                "corepack pnpm install --frozen-lockfile "
                "--ignore-scripts"
            )
            test_command = "corepack pnpm test"
        elif Path(repository_path, "yarn.lock").exists():
            install_command = (
                "corepack yarn install --immutable "
                "--mode=skip-builds"
            )
            test_command = "corepack yarn test"
        elif Path(repository_path, "package-lock.json").exists():
            install_command = (
                "npm ci --ignore-scripts --no-audit "
                "--no-fund"
            )
            test_command = "npm test"
        else:
            install_command = (
                "npm install --ignore-scripts "
                "--no-audit --no-fund"
            )
            test_command = "npm test"

        # Install dependencies without running lifecycle scripts.
        # Execute the declared test script inside the isolated container.
        shell_script = (
            "set -e\\n"
            f"{install_command}\\n"
            f"{test_command}\\n"
        )

        command = [
            "docker",
            "run",
            "--rm",
            "--network",
            "none",
            "--memory",
            self.memory_limit,
            "--cpus",
            self.cpu_limit,
            "--pids-limit",
            "128",
            "--cap-drop",
            "ALL",
            "--security-opt",
            "no-new-privileges",
            "--read-only",
            "--tmpfs",
            "/tmp:rw,noexec,nosuid,size=128m",
            "--tmpfs",
            "/root/.npm:rw,nosuid,size=256m",
            "-v",
            f"{repository_path}:/workspace:rw",
            "-w",
            "/workspace",
            "node:22-bookworm",
            "bash",
            "-lc",
            shell_script,
        ]

        process = await asyncio.create_subprocess_exec(
            *command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        try:
            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=self.timeout_seconds,
            )

            exit_code = process.returncode

            return {
                "status": (
                    "passed"
                    if exit_code == 0
                    else "failed"
                ),
                "passed": exit_code == 0,
                "exit_code": exit_code,
                "stdout": stdout.decode(
                    "utf-8",
                    errors="replace",
                )[-12000:],
                "stderr": stderr.decode(
                    "utf-8",
                    errors="replace",
                )[-12000:],
            }

        except asyncio.TimeoutError:
            process.kill()

            await process.communicate()

            return {
                "status": "failed",
                "passed": False,
                "exit_code": None,
                "stdout": "",
                "stderr": (
                    "Validation timed out after "
                    f"{self.timeout_seconds} seconds."
                ),
            }

import json
from pathlib import PurePosixPath


class RepositoryAnalyzer:

    def analyze(
        self,
        files: list[dict],
    ) -> dict:
        paths = {
            file["path"]
            for file in files
            if file.get("path")
        }

        contents = {
            file["path"]: file.get("content", "")
            for file in files
            if file.get("path")
        }

        profile = {
            "language": self._detect_language(paths),
            "framework": self._detect_framework(
                contents
            ),
            "database": self._detect_database(
                contents
            ),
            "orm": self._detect_orm(contents),
            "package_manager": self._detect_package_manager(
                paths
            ),
            "test_framework": self._detect_test_framework(
                paths,
                contents,
            ),
        }

        return profile

    def _detect_language(
        self,
        paths: set[str],
    ) -> str:
        extensions = {
            PurePosixPath(path).suffix.lower()
            for path in paths
        }

        if ".ts" in extensions or ".tsx" in extensions:
            return "TypeScript"

        if ".py" in extensions:
            return "Python"

        if ".java" in extensions:
            return "Java"

        if ".go" in extensions:
            return "Go"

        if ".rs" in extensions:
            return "Rust"

        if ".js" in extensions or ".jsx" in extensions:
            return "JavaScript"

        return "unknown"

    def _detect_framework(
        self,
        contents: dict[str, str],
    ) -> str:
        package_json = self._package_json(
            contents
        )

        dependencies = {
            **package_json.get("dependencies", {}),
            **package_json.get("devDependencies", {}),
        }

        if "next" in dependencies:
            return "Next.js"

        if "@nestjs/core" in dependencies:
            return "NestJS"

        if "express" in dependencies:
            return "Express"

        if "fastapi" in dependencies:
            return "FastAPI"

        if "django" in dependencies:
            return "Django"

        if "flask" in dependencies:
            return "Flask"

        return "unknown"

    def _detect_database(
        self,
        contents: dict[str, str],
    ) -> str:
        package_json = self._package_json(
            contents
        )

        dependencies = {
            **package_json.get("dependencies", {}),
            **package_json.get("devDependencies", {}),
        }

        if "pg" in dependencies:
            return "PostgreSQL"

        if "mysql2" in dependencies:
            return "MySQL"

        if "mongodb" in dependencies:
            return "MongoDB"

        for path, content in contents.items():
            lower_path = path.lower()
            lower_content = content.lower()

            if "postgresql" in lower_content:
                return "PostgreSQL"

            if lower_path.endswith(
                "schema.prisma"
            ):
                if "provider = \"postgresql\"" in content:
                    return "PostgreSQL"

                if "provider = \"mysql\"" in content:
                    return "MySQL"

                if "provider = \"mongodb\"" in content:
                    return "MongoDB"

        return "unknown"

    def _detect_orm(
        self,
        contents: dict[str, str],
    ) -> str:
        package_json = self._package_json(
            contents
        )

        dependencies = {
            **package_json.get("dependencies", {}),
            **package_json.get("devDependencies", {}),
        }

        if "prisma" in dependencies:
            return "Prisma"

        if "@prisma/client" in dependencies:
            return "Prisma"

        if "typeorm" in dependencies:
            return "TypeORM"

        if "sequelize" in dependencies:
            return "Sequelize"

        if "mongoose" in dependencies:
            return "Mongoose"

        return "unknown"

    def _detect_package_manager(
        self,
        paths: set[str],
    ) -> str:
        if "pnpm-lock.yaml" in paths:
            return "pnpm"

        if "yarn.lock" in paths:
            return "yarn"

        if "package-lock.json" in paths:
            return "npm"

        if "poetry.lock" in paths:
            return "poetry"

        if "Pipfile.lock" in paths:
            return "pipenv"

        if "uv.lock" in paths:
            return "uv"

        if (
            "requirements.txt" in paths
            or "pyproject.toml" in paths
        ):
            return "pip"

        return "unknown"

    def _detect_test_framework(
        self,
        paths: set[str],
        contents: dict[str, str],
    ) -> str:
        package_json = self._package_json(
            contents
        )

        dependencies = {
            **package_json.get("dependencies", {}),
            **package_json.get("devDependencies", {}),
        }

        if "jest" in dependencies:
            return "Jest"

        if "vitest" in dependencies:
            return "Vitest"

        if "pytest" in dependencies:
            return "pytest"

        if "pytest.ini" in paths:
            return "pytest"

        if any(
            path.endswith("pyproject.toml")
            and "pytest" in content.lower()
            for path, content in contents.items()
        ):
            return "pytest"

        return "unknown"

    def _package_json(
        self,
        contents: dict[str, str],
    ) -> dict:
        raw = contents.get("package.json")

        if not raw:
            return {}

        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return {}
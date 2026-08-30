from agent.app.services.repository_analyzer import (
    RepositoryAnalyzer,
)


def test_analyzes_nextjs_prisma_repository():
    analyzer = RepositoryAnalyzer()

    files = [
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
            "content": "export default function Page() {}",
        },
    ]

    result = analyzer.analyze(files)

    assert result == {
        "language": "TypeScript",
        "framework": "Next.js",
        "database": "PostgreSQL",
        "orm": "Prisma",
        "package_manager": "npm",
        "test_framework": "Jest",
    }
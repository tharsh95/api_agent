from fastapi import FastAPI
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import AsyncSessionLocal
app = FastAPI(
    title="AI Integration Engineer API",
    version="0.1.0",
)

@app.get("/health/db")
async def database_health():
    async with AsyncSessionLocal() as session:
        result = await session.execute(text("SELECT 1"))
        return {
            "status": "ok",
            "database": result.scalar(),
        }
@app.get("/health")
async def health():
    return {
        "status": "ok",
        "service": "api",
    }
@app.get("/health/vector")
async def vector_health():
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            text("SELECT extversion FROM pg_extension WHERE extname = 'vector'")
        )

        version = result.scalar_one_or_none()

        return {
            "status": "ok" if version else "missing",
            "pgvector_version": version,
        }
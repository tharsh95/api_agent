from pydantic import BaseModel, Field


class IngestFilesRequest(BaseModel):
    paths: list[str] = Field(
        min_length=1,
        max_length=50,
    )
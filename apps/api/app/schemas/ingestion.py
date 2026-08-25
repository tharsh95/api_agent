from pydantic import BaseModel, Field


class IngestFilesRequest(BaseModel):
    paths: list[str] = Field(
        default_factory=list,
        max_length=50,
    )
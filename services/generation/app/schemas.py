from pydantic import BaseModel


class DraftRequest(BaseModel):
    cluster_format: str
    cluster_theme: str
    competitor_caption: str


class DraftResponse(BaseModel):
    caption: str
    image_concept: str
    voice_examples_used: list[str]

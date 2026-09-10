from pydantic import BaseModel


class DraftRequest(BaseModel):
    cluster_format: str
    cluster_theme: str
    competitor_caption: str


class DraftResponse(BaseModel):
    caption: str
    image_concept: str
    voice_examples_used: list[str]
    image_mime_type: str | None = None
    image_data_base64: str | None = None

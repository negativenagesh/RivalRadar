from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.clustering import Cluster


class DigestRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    generated_at: datetime
    clusters: list[Cluster]
    trending_themes: list[str]
    gap_themes: list[str]
    post_count: int

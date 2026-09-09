import json
from importlib.resources import files

from pydantic import BaseModel


class VoiceExample(BaseModel):
    id: str
    themes: list[str]
    caption: str


class VoiceCorpus(BaseModel):
    brand_name: str
    brand_description: str
    posts: list[VoiceExample]


def load_corpus(package: str = "app.voice") -> VoiceCorpus:
    data = json.loads((files(package) / "corpus.json").read_text())
    return VoiceCorpus.model_validate(data)


def select_examples(
    corpus: VoiceCorpus,
    target_themes: list[str],
    *,
    count: int = 3,
) -> list[VoiceExample]:
    """Pick the brand's own past captions most relevant to `target_themes`.

    Retrieval is deliberately simple and inspectable: score each past post
    by how many of its tags overlap with the target themes, break ties by
    corpus order, and take the top `count`. No embeddings, no similarity
    threshold to tune -- every choice is traceable to an exact tag match,
    which is the point: this is the piece that most needs to not be a
    black box (see generation-service README).
    """
    target_set = set(target_themes)

    def overlap_score(example: VoiceExample) -> int:
        return len(target_set & set(example.themes))

    scored = sorted(corpus.posts, key=overlap_score, reverse=True)
    ranked = [e for e in scored if overlap_score(e) > 0]

    if len(ranked) < count:
        remaining = [e for e in corpus.posts if e not in ranked]
        ranked += remaining[: count - len(ranked)]

    return ranked[:count]

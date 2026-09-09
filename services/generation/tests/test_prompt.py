from app.voice.prompt import build_caption_prompt, build_image_concept_brief
from app.voice.retrieval import load_corpus, select_examples


def test_prompt_includes_brand_description_and_selected_examples() -> None:
    corpus = load_corpus()
    examples = select_examples(corpus, ["sustainability"], count=2)

    messages = build_caption_prompt(
        corpus,
        examples,
        cluster_format="founder_post",
        cluster_theme="sustainability",
        competitor_caption="we planted a tree",
    )

    system_content = messages[0].content
    user_content = messages[1].content

    assert corpus.brand_description in system_content
    for example in examples:
        assert example.caption in user_content
    assert "we planted a tree" in user_content


def test_prompt_never_leaks_competitor_name_instruction() -> None:
    corpus = load_corpus()
    examples = select_examples(corpus, ["product"], count=1)

    messages = build_caption_prompt(
        corpus,
        examples,
        cluster_format="product_launch_carousel",
        cluster_theme="product",
        competitor_caption="buy our thing",
    )

    assert "Do not copy or reference the competitor directly" in messages[1].content


def test_image_concept_brief_includes_format_theme_and_caption() -> None:
    brief = build_image_concept_brief(
        cluster_format="meme",
        cluster_theme="monday-mood",
        caption="mondays are rough",
    )

    assert "meme" in brief
    assert "monday-mood" in brief
    assert "mondays are rough" in brief

from app.voice.retrieval import load_corpus, select_examples


def test_load_corpus_reads_fixture() -> None:
    corpus = load_corpus()

    assert corpus.brand_name == "Halo & Co"
    assert len(corpus.posts) == 6


def test_select_examples_prioritizes_tag_overlap() -> None:
    corpus = load_corpus()

    examples = select_examples(corpus, ["sustainability"], count=2)

    assert examples[0].id in {"halo-001", "halo-002"}
    assert all("sustainability" in ex.themes for ex in examples)


def test_select_examples_falls_back_to_fill_count_with_no_match() -> None:
    corpus = load_corpus()

    examples = select_examples(corpus, ["theme-that-does-not-exist"], count=3)

    assert len(examples) == 3


def test_select_examples_respects_count() -> None:
    corpus = load_corpus()

    examples = select_examples(corpus, ["product"], count=1)

    assert len(examples) == 1

from ai_knowledge_platform.answers.evaluation import load_dataset


def test_answer_dataset_covers_the_declared_policy() -> None:
    dataset = load_dataset()
    tags = [tag for case in dataset.cases for tag in case.tags]

    assert len(dataset.cases) == 13
    assert tags.count("answerable") >= 6
    assert tags.count("unanswerable") >= 3
    assert tags.count("multi_evidence") >= 2
    assert "adversarial" in tags
    assert "lexical_false_friend" in tags
    assert {case.language for case in dataset.cases} == {"en", "es"}

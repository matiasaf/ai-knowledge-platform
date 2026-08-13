from ai_knowledge_platform.retrieval.evaluation import run_evaluation


def test_versioned_retrieval_evaluation_meets_its_thresholds() -> None:
    report = run_evaluation()

    assert report.dataset == "retrieval-v1-policy-pages"
    assert report.case_count == 4
    assert report.k == 3
    assert report.recall_at_k == 1.0
    assert report.mrr_at_k == 1.0
    assert report.passed is True
    assert all(case.first_relevant_rank == 1 for case in report.cases)

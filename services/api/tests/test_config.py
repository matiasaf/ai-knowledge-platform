import pytest

from ai_knowledge_platform.config import Settings


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("http://a.test", ["http://a.test"]),
        ("http://a.test, http://b.test,", ["http://a.test", "http://b.test"]),
        ('["http://a.test", "http://b.test"]', ["http://a.test", "http://b.test"]),
    ],
)
def test_cors_origins_accept_comma_separated_and_json_env_values(
    monkeypatch: pytest.MonkeyPatch, raw: str, expected: list[str]
) -> None:
    monkeypatch.setenv("AKP_CORS_ALLOW_ORIGINS", raw)

    assert Settings(_env_file=None).cors_allow_origins == expected  # type: ignore[call-arg]

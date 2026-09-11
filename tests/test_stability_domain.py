import pytest

from src.platform.domain.stability import Stability


@pytest.mark.parametrize(
    "risk_level",
    ["low", "medium", "moderate", "high", "critical", "minimal"],
)
def test_valid_risk_levels(risk_level):
    stability = Stability(
        score=0.75,
        risk_level=risk_level,
    )

    assert stability.risk_level == risk_level


def test_risk_level_is_normalized():
    stability = Stability(
        score=0.75,
        risk_level="  HIGH  ",
    )

    assert stability.risk_level == "high"


@pytest.mark.parametrize(
    "score",
    [0.0, 0.5, 1.0],
)
def test_score_boundaries(score):
    stability = Stability(
        score=score,
        risk_level="low",
    )

    assert stability.score == score


@pytest.mark.parametrize(
    "score",
    [-0.01, 1.01, float("inf"), float("-inf"), float("nan")],
)
def test_invalid_score(score):
    with pytest.raises(ValueError):
        Stability(
            score=score,
            risk_level="low",
        )


def test_score_is_converted_to_float():
    stability = Stability(
        score=1,
        risk_level="low",
    )

    assert stability.score == 1.0
    assert isinstance(stability.score, float)


def test_metrics_default_to_empty_dict():
    stability = Stability(
        score=0.8,
        risk_level="low",
    )

    assert stability.metrics == {}
    assert isinstance(stability.metrics, dict)


def test_metrics_are_preserved():
    metrics = {
        "win_rate": 0.65,
        "profit_factor": 1.8,
        "max_drawdown": 0.12,
    }

    stability = Stability(
        score=0.8,
        risk_level="medium",
        metrics=metrics,
    )

    assert stability.metrics == metrics


def test_metrics_are_copied():
    metrics = {
        "win_rate": 0.65,
    }

    stability = Stability(
        score=0.8,
        risk_level="medium",
        metrics=metrics,
    )

    metrics["win_rate"] = 0.10
    metrics["new_metric"] = 123

    assert stability.metrics["win_rate"] == 0.65
    assert "new_metric" not in stability.metrics


def test_metrics_are_immutable():
    stability = Stability(
        score=0.8,
        risk_level="medium",
        metrics={"win_rate": 0.65},
    )

    with pytest.raises(TypeError):
        stability.metrics["win_rate"] = 0.5


def test_metrics_cannot_be_deleted():
    stability = Stability(
        score=0.8,
        risk_level="medium",
        metrics={"win_rate": 0.65},
    )

    with pytest.raises(TypeError):
        del stability.metrics["win_rate"]


def test_metrics_update_is_blocked():
    stability = Stability(
        score=0.8,
        risk_level="medium",
        metrics={"win_rate": 0.65},
    )

    with pytest.raises(TypeError):
        stability.metrics.update({"profit_factor": 2.0})


@pytest.mark.parametrize(
    "risk_level",
    ["", "   ", "unknown", "extreme", None],
)
def test_invalid_risk_level(risk_level):
    with pytest.raises(ValueError):
        Stability(
            score=0.8,
            risk_level=risk_level,
        )


@pytest.mark.parametrize(
    "metrics",
    [[], (), "invalid", 123, 1.5],
)
def test_invalid_metrics(metrics):
    with pytest.raises(ValueError):
        Stability(
            score=0.8,
            risk_level="low",
            metrics=metrics,
        )


def test_stability_is_immutable():
    stability = Stability(
        score=0.8,
        risk_level="low",
        metrics={"win_rate": 0.65},
    )

    with pytest.raises((AttributeError, TypeError)):
        stability.score = 0.5


def test_stability_equality():
    first = Stability(
        score=0.8,
        risk_level="low",
        metrics={"win_rate": 0.65},
    )
    second = Stability(
        score=0.8,
        risk_level="low",
        metrics={"win_rate": 0.65},
    )

    assert first == second


def test_stability_to_dict():
    stability = Stability(
        score=0.8,
        risk_level="medium",
        metrics={
            "win_rate": 0.65,
            "profit_factor": 1.8,
        },
    )

    assert stability.to_dict() == {
        "score": 0.8,
        "risk_level": "medium",
        "metrics": {
            "win_rate": 0.65,
            "profit_factor": 1.8,
        },
    }


def test_to_dict_returns_independent_metrics_dict():
    stability = Stability(
        score=0.8,
        risk_level="medium",
        metrics={"win_rate": 0.65},
    )

    result = stability.to_dict()
    result["metrics"]["win_rate"] = 0.1

    assert stability.metrics["win_rate"] == 0.65

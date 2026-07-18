from app.desire.schemas.need_card import NeedCardResponse


def test_from_scores_sorts_by_rank_when_ranks_provided():
    """score 순서와 rank 순서가 어긋나도, ranks_by_code가 주어지면 rank를 따라야 한다
    (/analyze와 /history 응답 순서 불일치 방지)."""
    scores_by_code = {
        "Choice": 40,
        "Safe": 90,
        "Together": 10,
        "Fun": 20,
        "Meaning": 30,
        "True": 50,
        "Peace": 60,
        "Grow": 70,
    }
    ranks_by_code = {
        "Choice": 1,
        "Safe": 8,
        "Together": 2,
        "Fun": 3,
        "Meaning": 4,
        "True": 5,
        "Peace": 6,
        "Grow": 7,
    }

    response = NeedCardResponse.from_scores(scores_by_code, ranks_by_code=ranks_by_code)

    assert [item.code for item in response.needs] == [
        "Choice",
        "Together",
        "Fun",
        "Meaning",
        "True",
        "Peace",
        "Grow",
        "Safe",
    ]
    assert [item.rank for item in response.needs] == list(range(1, 9))
    assert [item.code for item in response.top4] == ["Choice", "Together", "Fun", "Meaning"]


def test_from_scores_falls_back_to_score_sort_without_ranks():
    scores_by_code = {"Choice": 10, "Safe": 90}

    response = NeedCardResponse.from_scores(scores_by_code)

    assert [item.code for item in response.needs] == ["Safe", "Choice"]

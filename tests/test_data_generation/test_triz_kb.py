from smartriz.data_generation.quality.triz_kb import (
    TRIZ_PRINCIPLES,
    validate_principles,
    principles_reference_block,
)


def test_principles_dict_has_40_entries():
    assert len(TRIZ_PRINCIPLES) == 40


def test_principles_dict_keys_are_1_to_40():
    assert set(TRIZ_PRINCIPLES.keys()) == set(range(1, 41))


def test_validate_principles_accepts_exact_canonical():
    result = validate_principles(["#1 Segmentation", "#8 Anti-Weight"])
    assert result["valid"] is True
    assert result["rejected"] == []
    assert len(result["normalized"]) == 2


def test_validate_principles_rejects_out_of_range_number():
    result = validate_principles(["#42 Pneumatic/Vacuum"])
    assert result["valid"] is False
    assert len(result["rejected"]) == 1
    assert "42" in result["rejected"][0]["reason"]


def test_validate_principles_rejects_wrong_name_for_correct_number():
    # #22 is "Blessing in Disguise", not "Spheroidality"
    result = validate_principles(["#22 Spheroidality"])
    assert result["valid"] is False
    assert len(result["rejected"]) == 1


def test_validate_principles_accepts_alias():
    # "Dynamism" is an accepted alias for #15 "Dynamics"
    result = validate_principles(["#15 Dynamism"])
    assert result["valid"] is True
    assert result["normalized"] == ["#15 Dynamics"]


def test_validate_principles_empty_list_is_invalid():
    result = validate_principles([])
    assert result["valid"] is False


def test_validate_principles_mixed_valid_and_invalid():
    result = validate_principles(["#1 Segmentation", "#42 Fake Principle"])
    assert result["valid"] is False
    assert len(result["normalized"]) == 1
    assert len(result["rejected"]) == 1


def test_validate_principles_rejects_explicit_invalid_alias():
    # "pneumatic/vacuum" maps to None in alias map — always invalid
    result = validate_principles(["#29 Pneumatic/Vacuum"])
    # #29 is "Pneumatics and Hydraulics"; "Pneumatic/Vacuum" hits the None alias
    assert result["valid"] is False


def test_principles_reference_block_contains_all_40():
    block = principles_reference_block()
    for n in range(1, 41):
        assert f"#{n} " in block


def test_validate_principles_accepts_abbreviated_canonical():
    # "Spheroid" is a valid abbreviation of "Spheroidality - Curvature"
    result = validate_principles(["#14 Spheroid"])
    assert result["valid"] is True
    assert result["normalized"] == ["#14 Spheroidality - Curvature"]


def test_validate_principles_rejects_canonical_with_trailing_garbage():
    # "Skipping!" should NOT be accepted — stray character
    result = validate_principles(["#21 Skipping!"])
    assert result["valid"] is False

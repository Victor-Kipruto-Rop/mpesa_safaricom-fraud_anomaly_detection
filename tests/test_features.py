import pytest
from src.features import calculate_z_score, extract_hour, is_unusual_hour

def test_z_score_calculation():
    assert calculate_z_score(150, 100, 25) == 2.0
    assert calculate_z_score(100, 100, 0) == 0
    assert calculate_z_score(100, 100, None) == 0

def test_hour_extraction():
    assert extract_hour("2025-01-01 14:30:00") == 14

def test_unusual_hour_flag():
    assert is_unusual_hour(2) is True
    assert is_unusual_hour(14) is False

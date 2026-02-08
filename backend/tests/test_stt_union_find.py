"""Unit tests for app.domain.stt.union_find (disjoint set for unknown speaker labels)."""
import pytest

from app.domain.stt.union_find import find, union, union_prefer_root


def test_find_singleton():
    parent = {}
    assert find(parent, "Unknown_1") == "Unknown_1"
    assert parent == {"Unknown_1": "Unknown_1"}


def test_find_defensive_adds_missing():
    parent = {}
    assert find(parent, "Unknown_99") == "Unknown_99"
    assert parent["Unknown_99"] == "Unknown_99"


def test_union_same_root():
    parent = {}
    union(parent, "Unknown_1", "Unknown_2")
    assert find(parent, "Unknown_1") == find(parent, "Unknown_2")
    assert find(parent, "Unknown_1") == "Unknown_1"  # smaller N is root


def test_union_numeric_order_unknown_9_unknown_10():
    parent = {}
    find(parent, "Unknown_9")
    find(parent, "Unknown_10")
    union(parent, "Unknown_10", "Unknown_9")
    assert find(parent, "Unknown_9") == "Unknown_9"
    assert find(parent, "Unknown_10") == "Unknown_9"  # 9 < 10 so Unknown_9 is root


def test_union_transitive():
    parent = {}
    union(parent, "Unknown_1", "Unknown_2")
    union(parent, "Unknown_2", "Unknown_3")
    r1 = find(parent, "Unknown_1")
    r2 = find(parent, "Unknown_2")
    r3 = find(parent, "Unknown_3")
    assert r1 == r2 == r3 == "Unknown_1"


def test_find_after_union_idempotent():
    parent = {}
    union(parent, "Unknown_1", "Unknown_2")
    assert find(parent, "Unknown_1") == "Unknown_1"
    assert find(parent, "Unknown_1") == "Unknown_1"
    assert find(parent, "Unknown_2") == "Unknown_1"


def test_union_prefer_root_promotes_preferred_label():
    parent = {}
    union_prefer_root(parent, "Unknown_1", "user_a", preferred_root="user_a")
    assert find(parent, "Unknown_1") == "user_a"
    assert find(parent, "user_a") == "user_a"

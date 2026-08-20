"""Unit tests for filter parsing helpers."""

import pytest

from tap_intacct.filters import build_stream_filter, extract_id, merge_filters


class TestExtractId:
    def test_extracts_id_from_name_id_label(self):
        assert extract_id("USA1 (1)") == "1"

    def test_uses_last_parenthesised_group(self):
        assert extract_id("LinkedIn Corporation  (CP) (56)") == "56"

    def test_plain_id_returned_as_is(self):
        assert extract_id("56") == "56"

    def test_non_string_returned_unchanged(self):
        assert extract_id(56) == 56


class TestMergeFilters:
    def test_merges_date_and_subsidiary_filters(self):
        date_filter = {
            "and": {
                "greaterthanorequalto": {"field": "ENTRY_DATE", "value": "01/01/2020"},
                "lessthanorequalto": {"field": "ENTRY_DATE", "value": "12/31/2020"},
            }
        }
        subsidiary_filter = {"in": {"field": "LOCATIONKEY", "value": ["1", "2"]}}
        merged = merge_filters(date_filter, subsidiary_filter)
        assert merged == {
            "and": {
                "greaterthanorequalto": {"field": "ENTRY_DATE", "value": "01/01/2020"},
                "lessthanorequalto": {"field": "ENTRY_DATE", "value": "12/31/2020"},
                "in": {"field": "LOCATIONKEY", "value": ["1", "2"]},
            }
        }

    def test_returns_none_for_empty_input(self):
        assert merge_filters(None, None) is None

    def test_preserves_duplicate_operator_keys(self):
        clause_a = {"in": {"field": "LOCATIONKEY", "value": ["9"]}}
        clause_b = {"in": {"field": "LOCATION", "value": ["500"]}}
        merged = merge_filters(clause_a, clause_b)
        assert merged == {
            "and": {
                "in": [
                    {"field": "LOCATIONKEY", "value": ["9"]},
                    {"field": "LOCATION", "value": ["500"]},
                ]
            }
        }


class TestBuildStreamFilter:
    def test_in_operator_extracts_ids_from_labels(self):
        stream_filters = {
            "clause_1": {
                "field": "LOCATIONKEY",
                "operator": "IN",
                "value": ["USA1 (1)", "USA2 (2)"],
            }
        }
        assert build_stream_filter(stream_filters) == {
            "in": {"field": "LOCATIONKEY", "value": ["1", "2"]}
        }

    def test_eq_operator(self):
        stream_filters = {
            "clause_1": {
                "field": "MEGAENTITYKEY",
                "operator": "EQ",
                "value": "USA1 (1)",
            }
        }
        assert build_stream_filter(stream_filters) == {
            "equalto": {"field": "MEGAENTITYKEY", "value": "1"}
        }

    def test_not_in_operator_extracts_ids_from_labels(self):
        stream_filters = {
            "clause_1": {
                "field": "LOCATIONKEY",
                "operator": "NOT IN",
                "value": ["USA1 (1)"],
            }
        }
        assert build_stream_filter(stream_filters) == {
            "notin": {"field": "LOCATIONKEY", "value": ["1"]}
        }

    def test_empty_selection_returns_none(self):
        stream_filters = {
            "clause_1": {
                "field": "LOCATIONKEY",
                "operator": "IN",
                "value": [],
            }
        }
        assert build_stream_filter(stream_filters) is None

    def test_or_operator_combines_equalto_clauses(self):
        stream_filters = {
            "clause_1": {
                "field": "LOCATIONKEY",
                "operator": "EQ",
                "value": "UK (10)",
            },
            "operator_1": "OR",
            "clause_2": {
                "field": "LOCATIONKEY",
                "operator": "EQ",
                "value": "USA1 (1)",
            },
        }
        assert build_stream_filter(stream_filters) == {
            "or": {
                "equalto": [
                    {"field": "LOCATIONKEY", "value": "10"},
                    {"field": "LOCATIONKEY", "value": "1"},
                ]
            }
        }

    def test_or_operator_combines_eq_and_in(self):
        stream_filters = {
            "clause_1": {
                "field": "MEGAENTITYKEY",
                "operator": "EQ",
                "value": "UK (10)",
            },
            "operator_1": "OR",
            "clause_2": {
                "field": "MEGAENTITYKEY",
                "operator": "IN",
                "value": ["USA1 (1)", "USA2 (2)"],
            },
        }
        assert build_stream_filter(stream_filters) == {
            "or": {
                "equalto": {"field": "MEGAENTITYKEY", "value": "10"},
                "in": {"field": "MEGAENTITYKEY", "value": ["1", "2"]},
            }
        }

    def test_multiple_clauses_default_to_or_without_operator(self):
        stream_filters = {
            "clause_1": {
                "field": "LOCATIONKEY",
                "operator": "IN",
                "value": ["UK (10)"],
            },
            "clause_2": {
                "field": "LOCATIONKEY",
                "operator": "IN",
                "value": ["USA1 (1)", "USA2 (2)"],
            },
        }
        assert build_stream_filter(stream_filters) == {
            "or": {
                "in": [
                    {"field": "LOCATIONKEY", "value": ["10"]},
                    {"field": "LOCATIONKEY", "value": ["1", "2"]},
                ]
            }
        }

    def test_and_operator_raises(self):
        stream_filters = {
            "clause_1": {
                "field": "LOCATIONKEY",
                "operator": "EQ",
                "value": "UK (10)",
            },
            "operator_1": "AND",
            "clause_2": {
                "field": "LOCATIONKEY",
                "operator": "IN",
                "value": ["USA1 (1)", "USA2 (2)"],
            },
        }
        with pytest.raises(ValueError, match="AND"):
            build_stream_filter(stream_filters)

    def test_nested_group_is_flattened(self):
        stream_filters = {
            "group_1": {
                "clause_1": {
                    "field": "LOCATIONKEY",
                    "operator": "IN",
                    "value": ["1"],
                }
            }
        }
        assert build_stream_filter(stream_filters) == {
            "in": {"field": "LOCATIONKEY", "value": ["1"]}
        }

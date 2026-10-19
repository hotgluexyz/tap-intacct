"""Unit tests for TapIntacct.get_available_filters / load_reference_data."""

import json
from unittest.mock import MagicMock

import pytest

from tap_intacct import TapIntacct
from tap_intacct.exceptions import SageIntacctSDKError


@pytest.fixture
def tap():
    config = {
        "company_id": "test",
        "sender_id": "test",
        "sender_password": "test",
        "user_id": "test",
        "user_password": "test",
        "start_date": "2000-01-01T00:00:00Z",
    }
    return TapIntacct(config=config, validate_config=False)


def catalog_with(stream_name, selected=True):
    return {
        "streams": [
            {
                "stream": stream_name,
                "tap_stream_id": stream_name,
                "metadata": [{"breadcrumb": [], "metadata": {"selected": selected}}],
            }
        ]
    }


class TestLoadReferenceData:
    def test_maps_fields_and_adds_label(self, tap):
        client = MagicMock()
        client.query_all.return_value = [
            {"RECORDNO": "1", "NAME": "USA1", "LOCATIONID": "100"},
            {"RECORDNO": "2", "NAME": "USA2", "LOCATIONID": "200"},
        ]

        out = tap._load_reference_data(client, {"subsidiaries": {"name(id)"}})

        client.query_all.assert_called_once_with(
            object_type="LOCATIONENTITY",
            fields=["RECORDNO", "NAME", "LOCATIONID"],
        )
        assert out["subsidiaries"][0] == {
            "id": "1",
            "name": "USA1",
            "location_id": "100",
            "name(id)": "USA1 (1)",
        }
        assert out["subsidiaries"][1]["name(id)"] == "USA2 (2)"

    def test_unknown_reference_stream_raises(self, tap):
        with pytest.raises(SageIntacctSDKError):
            tap._load_reference_data(MagicMock(), {"unknown": {"id"}})


class TestGetAvailableFilters:
    def test_emits_payload_with_reference_data(self, tap, mocker, capsys):
        fake_client = MagicMock()
        fake_client.query_all.return_value = [
            {"RECORDNO": "1", "NAME": "USA1", "LOCATIONID": "100"},
        ]
        mocker.patch("tap_intacct._build_intacct_client", return_value=fake_client)

        tap.get_available_filters(catalog_with("general_ledger_journal_entry_lines"))

        payload = json.loads(capsys.readouterr().out)
        assert payload["filters_version"] == "1.0.0"
        assert "general_ledger_journal_entry_lines" in payload["streams"]
        assert (
            payload["streams"]["general_ledger_journal_entry_lines"]["filters"]["subsidiary"][
                "target_field"
            ]
            == "LOCATIONKEY"
        )
        assert payload["reference_data"]["subsidiaries"][0]["name(id)"] == "USA1 (1)"

    def test_no_filterable_stream_skips_reference_fetch(self, tap, mocker, capsys):
        build_mock = mocker.patch("tap_intacct._build_intacct_client")

        tap.get_available_filters(catalog_with("general_ledger_accounts"))

        payload = json.loads(capsys.readouterr().out)
        assert payload["streams"] == {}
        assert payload["reference_data"] == {}
        build_mock.assert_not_called()

    def test_unselected_filterable_stream_is_excluded(self, tap, mocker, capsys):
        build_mock = mocker.patch("tap_intacct._build_intacct_client")

        tap.get_available_filters(
            catalog_with("general_ledger_journal_entry_lines", selected=False)
        )

        payload = json.loads(capsys.readouterr().out)
        assert payload["streams"] == {}
        assert payload["reference_data"] == {}
        build_mock.assert_not_called()

    def test_includes_gl_batch_when_selected_in_catalog(self, tap, mocker, capsys):
        fake_client = MagicMock()
        fake_client.query_all.return_value = []
        mocker.patch("tap_intacct._build_intacct_client", return_value=fake_client)

        catalog = {
            "streams": [
                {
                    "stream": "general_ledger_journal_entries",
                    "tap_stream_id": "general_ledger_journal_entries",
                    "metadata": [{"breadcrumb": [], "metadata": {"selected": True}}],
                },
                {
                    "stream": "general_ledger_journal_entry_lines",
                    "tap_stream_id": "general_ledger_journal_entry_lines",
                    "metadata": [{"breadcrumb": [], "metadata": {"selected": True}}],
                },
            ]
        }
        tap.get_available_filters(catalog)

        payload = json.loads(capsys.readouterr().out)
        assert set(payload["streams"]) == {
            "general_ledger_journal_entries",
            "general_ledger_journal_entry_lines",
        }
        assert (
            payload["streams"]["general_ledger_journal_entries"]["filters"]["subsidiary"][
                "target_field"
            ]
            == "MEGAENTITYKEY"
        )

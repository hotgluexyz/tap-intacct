"""Declarative available-filters metadata and reference-data loading."""

from typing import Any, Dict, List, Set

from tap_intacct.client import SageIntacctSDK
from tap_intacct.exceptions import SageIntacctSDKError

AVAILABLE_FILTERS = {
    "general_ledger_journal_entry_lines": {
        "supported_operators": ["OR"],
        "supports_nesting_clauses": False,
        "filters": {
            "subsidiary": {
                "label": "Subsidiary",
                "supported_operators": ["IN", "NOT IN", "EQ"],
                "target_field": "LOCATIONKEY",
                "options": "reference_data.subsidiaries.name(id)",
            },
        },
    },
    "general_ledger_journal_entries": {
        "supported_operators": ["OR"],
        "supports_nesting_clauses": False,
        "filters": {
            "subsidiary": {
                "label": "Subsidiary",
                "supported_operators": ["IN", "NOT IN", "EQ"],
                "target_field": "MEGAENTITYKEY",
                "options": "reference_data.subsidiaries.name(id)",
            },
        },
    },
}

REFERENCE_DATA = {
    "subsidiaries": {
        "object": "LOCATIONENTITY",
        "fields": {"id": "RECORDNO", "name": "NAME", "location_id": "LOCATIONID"},
    },
}


def load_reference_data(
    client: SageIntacctSDK,
    stream_name_to_fields: Dict[str, Set[str]],
) -> Dict[str, List[Dict[str, Any]]]:
    """Fetch reference data for filter option lists."""
    reference_data: Dict[str, List[Dict[str, Any]]] = {}
    for stream_name in stream_name_to_fields:
        spec = REFERENCE_DATA.get(stream_name)
        if not spec:
            raise SageIntacctSDKError(
                f"No reference data mapping configured for '{stream_name}'."
            )

        field_map = spec["fields"]
        api_fields = list(field_map.values())
        records = client.query_all(object_type=spec["object"], fields=api_fields)

        data = [
            {
                logical: record.get(api_field)
                for logical, api_field in field_map.items()
            }
            for record in records
        ]

        if data and "id" in data[0] and "name" in data[0]:
            data = [
                {
                    **record,
                    "name(id)": "{} ({})".format(record.get("name"), record.get("id")),
                }
                for record in data
            ]

        reference_data[stream_name] = data

    return reference_data

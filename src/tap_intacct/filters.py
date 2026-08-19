"""Parse selected-filters payloads into Sage Intacct query filter dicts."""

from typing import Any, Dict, List, Optional


def extract_id(value: Any) -> Any:
    """Extract the id from a "Name (id)" reference value."""
    if isinstance(value, str):
        stripped = value.rstrip()
        if stripped.endswith(")") and "(" in stripped:
            return stripped[stripped.rfind("(") + 1 : -1].strip()
    return value


def merge_filters(*filters: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Combine Intacct filter dicts under a single ``and`` block."""
    merged: Dict[str, Any] = {}
    for filt in filters:
        if not filt:
            continue
        if "and" in filt:
            merged.update(filt["and"])
        else:
            merged.update(filt)

    return {"and": merged} if merged else None


def _parse_clause(clause: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Convert a single selected-filters clause to an Intacct filter fragment."""
    operator = clause["operator"]
    raw_value = clause["value"]
    field = clause["field"]

    if isinstance(raw_value, list):
        values = [extract_id(value) for value in raw_value]
    else:
        values = [extract_id(raw_value)]

    values = [str(value) for value in values if value not in (None, "")]
    if not values:
        return None

    if operator == "EQ":
        return {"equalto": {"field": field, "value": values[0]}}
    if operator == "IN":
        return {"in": {"field": field, "value": values}}
    if operator == "NOT IN":
        return {"notin": {"field": field, "value": values}}

    raise ValueError("Unsupported filter operator: {}".format(operator))


def _parse_filters(filters: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Parse a selected-filters subtree into one Intacct filter dict."""
    clauses: List[Dict[str, Any]] = []
    for key, value in filters.items():
        if key.startswith("group_"):
            nested = _parse_filters(value)
            if nested:
                clauses.append(nested)
        elif key.startswith("clause_"):
            clause = _parse_clause(value)
            if clause:
                clauses.append(clause)
        elif key.startswith("operator_"):
            if isinstance(value, str) and value.strip().upper() == "OR":
                raise ValueError(
                    "Sage Intacct subsidiary filters do not support OR; only AND is allowed."
                )

    if not clauses:
        return None
    if len(clauses) == 1:
        return clauses[0]
    return merge_filters(*clauses)


def build_stream_filter(stream_filters: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Convert a stream's selected-filters subtree to an Intacct query filter."""
    if not stream_filters:
        return None
    return _parse_filters(stream_filters)

"""Parse selected-filters payloads into Sage Intacct query filter dicts."""

from typing import Any, Dict, List, Optional, Tuple


def extract_id(value: Any) -> Any:
    """Extract the id from a "Name (id)" reference value."""
    if isinstance(value, str):
        stripped = value.rstrip()
        if stripped.endswith(")") and "(" in stripped:
            return stripped[stripped.rfind("(") + 1 : -1].strip()
    return value


def _merge_fragment(merged: Dict[str, Any], fragment: Dict[str, Any]) -> None:
    """Merge one filter fragment, preserving duplicate operator keys as lists."""
    for operator, body in fragment.items():
        if operator not in merged:
            merged[operator] = body
        elif merged[operator] == body:
            continue
        elif isinstance(merged[operator], list):
            merged[operator].append(body)
        else:
            merged[operator] = [merged[operator], body]


def merge_filters(*filters: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Combine Intacct filter dicts under a single ``and`` block."""
    merged: Dict[str, Any] = {}
    for filt in filters:
        if not filt:
            continue
        fragment = filt["and"] if "and" in filt else filt
        _merge_fragment(merged, fragment)

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


def _combine_or_clauses(clauses: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Combine parsed clauses into the Intacct ``or`` dict shape."""
    or_body: Dict[str, Any] = {}
    for clause in clauses:
        if len(clause) != 1:
            raise ValueError("Unexpected clause shape: {}".format(clause))
        _merge_fragment(or_body, clause)
    return {"or": or_body}


def _sorted_numeric_keys(filters: Dict[str, Any], prefix: str) -> List[Tuple[int, str]]:
    keys: List[Tuple[int, str]] = []
    for key in filters:
        if key.startswith(prefix):
            keys.append((int(key.split("_", 1)[1]), key))
    return sorted(keys)


def _parse_filters(filters: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Parse a selected-filters subtree into one Intacct filter dict."""
    clauses: List[Dict[str, Any]] = []
    logical_operators: List[str] = []

    for _, key in _sorted_numeric_keys(filters, "group_"):
        nested = _parse_filters(filters[key])
        if nested:
            clauses.append(nested)

    for _, key in _sorted_numeric_keys(filters, "clause_"):
        clause = _parse_clause(filters[key])
        if clause:
            clauses.append(clause)

    for _, key in _sorted_numeric_keys(filters, "operator_"):
        value = filters[key]
        if isinstance(value, str):
            logical_operators.append(value.strip().upper())

    if not clauses:
        return None
    if len(clauses) == 1:
        return clauses[0]

    for operator in logical_operators:
        if operator == "AND":
            raise ValueError(
                "Sage Intacct subsidiary filters do not support AND between clauses; "
                "use OR or a single IN clause."
            )
        if operator != "OR":
            raise ValueError("Unsupported logical operator: {}".format(operator))

    return _combine_or_clauses(clauses)


def build_stream_filter(stream_filters: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Convert a stream's selected-filters subtree to an Intacct query filter."""
    if not stream_filters:
        return None
    return _parse_filters(stream_filters)

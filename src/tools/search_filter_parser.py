"""
RSQL Filter Parser for Search Library Tool

Parses RSQL (RESTful Service Query Language) filter strings into database-compatible
filter parameters. Supports basic operators for music search filtering.

RSQL Syntax:
- AND: ; (semicolon)
- OR: , (comma)
- Operators: ==, !=, >=, <=, >, <, =in=, =out=, =like=

Examples:
- genre==Rock;year>=1960,year<=1980
- artist=like=*beatles*;format==MP3
"""

import re
from typing import Dict, Any, List, Optional, Tuple
from enum import Enum


class RSQLParseError(Exception):
    """Raised when RSQL parsing fails"""
    pass


class FilterOperator(str, Enum):
    """Supported RSQL operators"""
    EQUAL = "=="
    NOT_EQUAL = "!="
    GREATER_EQUAL = ">="
    LESS_EQUAL = "<="
    GREATER = ">"
    LESS = "<"
    IN = "=in="
    OUT = "=out="
    LIKE = "=like="


class FilterField(str, Enum):
    """Supported filter fields"""
    GENRE = "genre"
    YEAR = "year"
    DURATION = "duration"
    FORMAT = "format"
    ARTIST = "artist"
    ALBUM = "album"


def parse_rsql_filter(filter_string: str) -> Dict[str, Any]:
    """
    Parse RSQL filter string into database filter parameters.

    Args:
        filter_string: RSQL filter string (e.g., "genre==Rock;year>=1960,year<=1980")

    Returns:
        Dictionary with database-compatible filter parameters

    Raises:
        RSQLParseError: If parsing fails
    """
    if not filter_string or not filter_string.strip():
        return {}

    # Split by AND (;) first
    and_parts = [part.strip() for part in filter_string.split(';') if part.strip()]

    filters = {}

    for and_part in and_parts:
        # Parse each AND clause (may contain OR)
        parsed_clause = _parse_rsql_clause(and_part)
        _merge_clause_into_filters(parsed_clause, filters)

    return filters


def _parse_rsql_clause(clause: str) -> List[Tuple[str, FilterOperator, Any]]:
    """
    Parse a single RSQL clause (may contain OR).

    Args:
        clause: Single clause like "year>=1960,year<=1980"

    Returns:
        List of (field, operator, value) tuples
    """
    # Split by OR (,) first
    or_parts = [part.strip() for part in clause.split(',') if part.strip()]

    parsed_conditions = []

    for or_part in or_parts:
        field, op, value = _parse_single_condition(or_part)
        parsed_conditions.append((field, op, value))

    return parsed_conditions


def _parse_single_condition(condition: str) -> Tuple[str, FilterOperator, Any]:
    """
    Parse a single condition like "genre==Rock" or "year>=1960".

    Args:
        condition: Single condition string

    Returns:
        Tuple of (field, operator, value)
    """
    # Find the operator
    op_match = None
    for op in FilterOperator:
        if op.value in condition:
            # Use the longest match first to avoid partial matches
            if op_match is None or len(op.value) > len(op_match.value):
                op_match = op

    if not op_match:
        raise RSQLParseError(f"No valid operator found in condition: '{condition}'")

    # Split by operator
    parts = condition.split(op_match.value, 1)
    if len(parts) != 2:
        raise RSQLParseError(f"Invalid condition format: '{condition}'")

    field_name = parts[0].strip()
    value_str = parts[1].strip()

    # Validate field
    try:
        field = FilterField(field_name)
    except ValueError:
        raise RSQLParseError(f"Unsupported field: '{field_name}'. Supported: {[f.value for f in FilterField]}")

    # Parse value based on field and operator
    value = _parse_value(value_str, field, op_match)

    return field_name, op_match, value


def _parse_value(value_str: str, field: FilterField, op: FilterOperator) -> Any:
    """
    Parse value string based on field type and operator.

    Args:
        value_str: Raw value string
        field: Filter field enum
        op: Filter operator enum

    Returns:
        Parsed value (appropriate type)
    """
    # Handle special operators
    if op in [FilterOperator.IN, FilterOperator.OUT]:
        # Parse comma-separated list, remove parentheses
        value_str = value_str.strip('()')
        values = [v.strip() for v in value_str.split(',') if v.strip()]
        return [_parse_single_value(v, field) for v in values]

    elif op == FilterOperator.LIKE:
        # Remove wildcards for LIKE operations
        return value_str.strip('*')

    else:
        # Single value
        return _parse_single_value(value_str, field)


def _parse_single_value(value_str: str, field: FilterField) -> Any:
    """
    Parse single value based on field type.

    Args:
        value_str: Raw value string
        field: Filter field enum

    Returns:
        Parsed value with appropriate type
    """
    # Type conversion based on field
    if field in [FilterField.YEAR]:
        try:
            return int(value_str)
        except ValueError:
            raise RSQLParseError(f"Invalid integer value for {field.value}: '{value_str}'")

    elif field == FilterField.DURATION:
        try:
            return float(value_str)
        except ValueError:
            raise RSQLParseError(f"Invalid numeric value for {field.value}: '{value_str}'")

    else:
        # String fields
        return value_str


def _merge_clause_into_filters(clause_conditions: List[Tuple[str, FilterOperator, Any]],
                               filters: Dict[str, Any]) -> None:
    """
    Merge parsed clause conditions into the filters dictionary.

    Handles operator precedence and converts to database filter format.

    Args:
        clause_conditions: List of (field, operator, value) tuples from one clause
        filters: Target filters dictionary to update
    """
    for field, op, value in clause_conditions:
        db_field = _map_field_to_db(field)

        if op == FilterOperator.EQUAL:
            filters[f"{db_field}_filter"] = value

        elif op == FilterOperator.NOT_EQUAL:
            # For NOT EQUAL, we need to handle this in the query logic
            # For now, store as exclusion filter
            if f"{db_field}_exclude" not in filters:
                filters[f"{db_field}_exclude"] = []
            filters[f"{db_field}_exclude"].append(value)

        elif op in [FilterOperator.GREATER_EQUAL, FilterOperator.GREATER,
                   FilterOperator.LESS_EQUAL, FilterOperator.LESS]:
            range_key = f"{db_field}_min" if op in [FilterOperator.GREATER_EQUAL, FilterOperator.GREATER] else f"{db_field}_max"

            # For >= and >, we use min filter
            # For <= and <, we use max filter
            if range_key not in filters:
                filters[range_key] = value
            else:
                # If we have multiple conditions, take the most restrictive
                if range_key.endswith("_min"):
                    filters[range_key] = max(filters[range_key], value)
                else:
                    filters[range_key] = min(filters[range_key], value)

        elif op == FilterOperator.IN:
            # For IN operations, convert to list
            filters[f"{db_field}_in"] = value

        elif op == FilterOperator.OUT:
            # For OUT operations, convert to exclusion list
            if f"{db_field}_not_in" not in filters:
                filters[f"{db_field}_not_in"] = []
            filters[f"{db_field}_not_in"].extend(value)

        elif op == FilterOperator.LIKE:
            # For LIKE operations
            filters[f"{db_field}_like"] = value


def _map_field_to_db(field_name: str) -> str:
    """
    Map filter field names to database parameter names.

    Args:
        field_name: Filter field name

    Returns:
        Database parameter prefix
    """
    field_mapping = {
        "genre": "genre",
        "year": "year",
        "duration": "duration",
        "format": "format",
        "artist": "artist",
        "album": "album"
    }

    if field_name not in field_mapping:
        raise RSQLParseError(f"Unknown field mapping: {field_name}")

    return field_mapping[field_name]


# Cursor encoding/decoding utilities

def encode_cursor(score: float, created_at: str, track_id: str) -> str:
    """
    Encode pagination cursor from sort values.

    Args:
        score: Relevance score
        created_at: ISO timestamp string
        track_id: Track UUID

    Returns:
        Base64-encoded cursor string
    """
    import base64
    import json

    cursor_data = {
        "score": score,
        "created_at": created_at,
        "id": track_id
    }

    cursor_json = json.dumps(cursor_data, separators=(',', ':'))
    return base64.b64encode(cursor_json.encode()).decode()


def decode_cursor(cursor: str) -> Tuple[float, str, str]:
    """
    Decode pagination cursor to sort values.

    Args:
        cursor: Base64-encoded cursor string

    Returns:
        Tuple of (score, created_at, track_id)
    """
    import base64
    import json

    try:
        cursor_json = base64.b64decode(cursor.encode())
        cursor_data = json.loads(cursor_json)

        return (
            cursor_data["score"],
            cursor_data["created_at"],
            cursor_data["id"]
        )
    except Exception as e:
        raise ValueError(f"Invalid cursor format: {e}")


# Field selection utilities

def parse_field_selection(fields_str: str) -> List[str]:
    """
    Parse comma-separated field selection string.

    Args:
        fields_str: Comma-separated field list

    Returns:
        List of field names
    """
    if not fields_str:
        return []

    return [field.strip() for field in fields_str.split(',') if field.strip()]


def apply_field_selection(result_dict: Dict[str, Any], fields: List[str]) -> Dict[str, Any]:
    """
    Apply field selection to a result dictionary.

    Args:
        result_dict: Full result dictionary
        fields: List of fields to include

    Returns:
        Filtered dictionary with only requested fields
    """
    if not fields:
        return result_dict

    filtered = {}
    for field in fields:
        if field in result_dict:
            filtered[field] = result_dict[field]

    return filtered

"""
Tabular format transforms: JSON ↔ CSV ↔ XML ↔ YAML ↔ TOML

Uses orjson (10x faster JSON), polars (Rust-based CSV), lxml/xmltodict,
ruamel.yaml, and stdlib tomllib + tomli_w.
"""

from __future__ import annotations

import io
import tomllib
from typing import Any

import orjson
import polars as pl
import xmltodict
from defusedxml import minidom as safe_minidom
from ruamel.yaml import YAML
import tomli_w


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _json_loads(data: bytes) -> Any:
    return orjson.loads(data)


def _json_dumps(obj: Any, indent: bool = False) -> bytes:
    opts = orjson.OPT_INDENT_2 | orjson.OPT_NON_STR_KEYS if indent else orjson.OPT_NON_STR_KEYS
    return orjson.dumps(obj, option=opts)


def _yaml_instance() -> YAML:
    y = YAML()
    y.default_flow_style = False
    return y


def _ensure_list_of_dicts(obj: Any) -> list[dict]:
    """Normalise input to a list of flat dicts for tabular conversion."""
    if isinstance(obj, list):
        return [r if isinstance(r, dict) else {"value": r} for r in obj]
    if isinstance(obj, dict):
        return [obj]
    return [{"value": obj}]


# ---------------------------------------------------------------------------
# JSON → *
# ---------------------------------------------------------------------------

async def json_to_csv(data: bytes, options: dict | None = None) -> bytes:
    obj = _json_loads(data)
    rows = _ensure_list_of_dicts(obj)
    df = pl.DataFrame(rows)
    buf = io.BytesIO()
    sep = (options or {}).get("delimiter", ",")
    df.write_csv(buf, separator=sep)
    return buf.getvalue()


async def json_to_xml(data: bytes, options: dict | None = None) -> bytes:
    obj = _json_loads(data)
    root = (options or {}).get("root_tag", "root")
    item_tag = (options or {}).get("item_tag", "item")
    if isinstance(obj, list):
        obj = {item_tag: obj}
    xml_str: str = xmltodict.unparse({root: obj}, pretty=True)
    return xml_str.encode()


async def json_to_yaml(data: bytes, options: dict | None = None) -> bytes:
    obj = _json_loads(data)
    y = _yaml_instance()
    buf = io.BytesIO()
    y.dump(obj, buf)
    return buf.getvalue()


async def json_to_toml(data: bytes, options: dict | None = None) -> bytes:
    obj = _json_loads(data)
    if not isinstance(obj, dict):
        obj = {"data": obj}
    return tomli_w.dumps(obj).encode()


async def json_to_plain_text(data: bytes, options: dict | None = None) -> bytes:
    obj = _json_loads(data)
    return _json_dumps(obj, indent=True)


# ---------------------------------------------------------------------------
# CSV → *
# ---------------------------------------------------------------------------

async def csv_to_json(data: bytes, options: dict | None = None) -> bytes:
    sep = (options or {}).get("delimiter", ",")
    df = pl.read_csv(io.BytesIO(data), separator=sep, infer_schema_length=1000)
    rows = df.to_dicts()
    return _json_dumps(rows)


async def csv_to_xml(data: bytes, options: dict | None = None) -> bytes:
    sep = (options or {}).get("delimiter", ",")
    df = pl.read_csv(io.BytesIO(data), separator=sep, infer_schema_length=1000)
    rows = df.to_dicts()
    root = (options or {}).get("root_tag", "root")
    item_tag = (options or {}).get("item_tag", "row")
    xml_str: str = xmltodict.unparse({root: {item_tag: rows}}, pretty=True)
    return xml_str.encode()


async def csv_to_yaml(data: bytes, options: dict | None = None) -> bytes:
    sep = (options or {}).get("delimiter", ",")
    df = pl.read_csv(io.BytesIO(data), separator=sep, infer_schema_length=1000)
    rows = df.to_dicts()
    y = _yaml_instance()
    buf = io.BytesIO()
    y.dump(rows, buf)
    return buf.getvalue()


async def csv_to_plain_text(data: bytes, options: dict | None = None) -> bytes:
    return data  # CSV is already text


async def csv_to_excel(data: bytes, options: dict | None = None) -> bytes:
    sep = (options or {}).get("delimiter", ",")
    df = pl.read_csv(io.BytesIO(data), separator=sep, infer_schema_length=1000)
    buf = io.BytesIO()
    df.write_excel(buf)
    return buf.getvalue()


# ---------------------------------------------------------------------------
# XML → *
# ---------------------------------------------------------------------------

async def xml_to_json(data: bytes, options: dict | None = None) -> bytes:
    obj = xmltodict.parse(data)
    return _json_dumps(obj)


async def xml_to_csv(data: bytes, options: dict | None = None) -> bytes:
    obj = xmltodict.parse(data)
    # Flatten: find the first list-like structure
    flat = _flatten_xml_to_rows(obj)
    df = pl.DataFrame(flat)
    buf = io.BytesIO()
    df.write_csv(buf)
    return buf.getvalue()


async def xml_to_yaml(data: bytes, options: dict | None = None) -> bytes:
    obj = xmltodict.parse(data)
    y = _yaml_instance()
    buf = io.BytesIO()
    y.dump(_ordered_to_dict(obj), buf)
    return buf.getvalue()


async def xml_to_plain_text(data: bytes, options: dict | None = None) -> bytes:
    obj = xmltodict.parse(data)
    return _json_dumps(obj, indent=True)


def _flatten_xml_to_rows(obj: Any) -> list[dict]:
    """Walk the parsed XML tree and find the first list of dicts."""
    if isinstance(obj, list):
        return [r if isinstance(r, dict) else {"value": r} for r in obj]
    if isinstance(obj, dict):
        for v in obj.values():
            result = _flatten_xml_to_rows(v)
            if result and len(result) > 1:
                return result
        # Single dict — return as one row
        flat: dict[str, Any] = {}
        _flatten_dict(obj, flat, "")
        return [flat]
    return [{"value": str(obj)}]


def _flatten_dict(d: dict, out: dict, prefix: str) -> None:
    for k, v in d.items():
        key = f"{prefix}{k}" if not prefix else f"{prefix}.{k}"
        if isinstance(v, dict):
            _flatten_dict(v, out, key)
        elif isinstance(v, list):
            out[key] = str(v)
        else:
            out[key] = v


def _ordered_to_dict(obj: Any) -> Any:
    """Convert OrderedDict (from xmltodict) to plain dict for YAML."""
    if isinstance(obj, dict):
        return {k: _ordered_to_dict(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_ordered_to_dict(i) for i in obj]
    return obj


# ---------------------------------------------------------------------------
# YAML → *
# ---------------------------------------------------------------------------

async def yaml_to_json(data: bytes, options: dict | None = None) -> bytes:
    y = _yaml_instance()
    obj = y.load(io.BytesIO(data))
    return _json_dumps(obj)


async def yaml_to_xml(data: bytes, options: dict | None = None) -> bytes:
    y = _yaml_instance()
    obj = y.load(io.BytesIO(data))
    root = (options or {}).get("root_tag", "root")
    if isinstance(obj, list):
        obj = {"item": obj}
    xml_str: str = xmltodict.unparse({root: obj}, pretty=True)
    return xml_str.encode()


async def yaml_to_toml(data: bytes, options: dict | None = None) -> bytes:
    y = _yaml_instance()
    obj = y.load(io.BytesIO(data))
    if not isinstance(obj, dict):
        obj = {"data": obj}
    return tomli_w.dumps(obj).encode()


async def yaml_to_plain_text(data: bytes, options: dict | None = None) -> bytes:
    return data  # YAML is already human-readable


# ---------------------------------------------------------------------------
# TOML → *
# ---------------------------------------------------------------------------

async def toml_to_json(data: bytes, options: dict | None = None) -> bytes:
    obj = tomllib.loads(data.decode())
    return _json_dumps(obj)


async def toml_to_yaml(data: bytes, options: dict | None = None) -> bytes:
    obj = tomllib.loads(data.decode())
    y = _yaml_instance()
    buf = io.BytesIO()
    y.dump(obj, buf)
    return buf.getvalue()


async def toml_to_plain_text(data: bytes, options: dict | None = None) -> bytes:
    return data  # TOML is already text

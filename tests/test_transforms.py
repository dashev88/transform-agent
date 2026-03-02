"""Tests for all transform pairs."""

from __future__ import annotations

import base64
import json

import pytest

# We test handlers directly (no HTTP) for speed
from transform_agent.transforms import tabular, markup, documents, encoding
from transform_agent.transforms.schema import reshape_json


# ===== Tabular =====

class TestJSONConversions:
    @pytest.mark.asyncio
    async def test_json_to_csv(self):
        data = b'[{"name":"Alice","age":30},{"name":"Bob","age":25}]'
        result = await tabular.json_to_csv(data)
        text = result.decode()
        assert "name" in text
        assert "Alice" in text
        assert "Bob" in text

    @pytest.mark.asyncio
    async def test_json_to_xml(self):
        data = b'{"name":"Alice","age":30}'
        result = await tabular.json_to_xml(data)
        text = result.decode()
        assert "<root>" in text
        assert "<name>Alice</name>" in text

    @pytest.mark.asyncio
    async def test_json_to_yaml(self):
        data = b'{"name":"Alice","age":30}'
        result = await tabular.json_to_yaml(data)
        text = result.decode()
        assert "name: Alice" in text
        assert "age: 30" in text

    @pytest.mark.asyncio
    async def test_json_to_toml(self):
        data = b'{"name":"Alice","age":30}'
        result = await tabular.json_to_toml(data)
        text = result.decode()
        assert 'name = "Alice"' in text

    @pytest.mark.asyncio
    async def test_json_to_plain_text(self):
        data = b'{"name":"Alice"}'
        result = await tabular.json_to_plain_text(data)
        assert b"Alice" in result


class TestCSVConversions:
    @pytest.mark.asyncio
    async def test_csv_to_json(self):
        data = b"name,age\nAlice,30\nBob,25"
        result = await tabular.csv_to_json(data)
        obj = json.loads(result)
        assert len(obj) == 2
        assert obj[0]["name"] == "Alice"

    @pytest.mark.asyncio
    async def test_csv_to_xml(self):
        data = b"name,age\nAlice,30"
        result = await tabular.csv_to_xml(data)
        assert b"<root>" in result
        assert b"Alice" in result

    @pytest.mark.asyncio
    async def test_csv_to_yaml(self):
        data = b"name,age\nAlice,30"
        result = await tabular.csv_to_yaml(data)
        assert b"Alice" in result

    @pytest.mark.asyncio
    async def test_csv_to_plain_text(self):
        data = b"name,age\nAlice,30"
        result = await tabular.csv_to_plain_text(data)
        assert result == data


class TestXMLConversions:
    @pytest.mark.asyncio
    async def test_xml_to_json(self):
        data = b"<root><name>Alice</name><age>30</age></root>"
        result = await tabular.xml_to_json(data)
        obj = json.loads(result)
        assert obj["root"]["name"] == "Alice"

    @pytest.mark.asyncio
    async def test_xml_to_yaml(self):
        data = b"<root><name>Alice</name></root>"
        result = await tabular.xml_to_yaml(data)
        assert b"Alice" in result


class TestYAMLConversions:
    @pytest.mark.asyncio
    async def test_yaml_to_json(self):
        data = b"name: Alice\nage: 30\n"
        result = await tabular.yaml_to_json(data)
        obj = json.loads(result)
        assert obj["name"] == "Alice"

    @pytest.mark.asyncio
    async def test_yaml_to_toml(self):
        data = b"name: Alice\nage: 30\n"
        result = await tabular.yaml_to_toml(data)
        assert b'name = "Alice"' in result


class TestTOMLConversions:
    @pytest.mark.asyncio
    async def test_toml_to_json(self):
        data = b'name = "Alice"\nage = 30\n'
        result = await tabular.toml_to_json(data)
        obj = json.loads(result)
        assert obj["name"] == "Alice"

    @pytest.mark.asyncio
    async def test_toml_to_yaml(self):
        data = b'name = "Alice"\n'
        result = await tabular.toml_to_yaml(data)
        assert b"Alice" in result


# ===== Markup =====

class TestMarkupConversions:
    @pytest.mark.asyncio
    async def test_html_to_markdown(self):
        data = b"<h1>Title</h1><p>Hello <strong>world</strong></p>"
        result = await markup.html_to_markdown(data)
        text = result.decode()
        assert "Title" in text
        assert "**world**" in text

    @pytest.mark.asyncio
    async def test_html_to_plain_text(self):
        data = b"<h1>Title</h1><p>Hello world</p>"
        result = await markup.html_to_plain_text(data)
        text = result.decode()
        assert "Title" in text
        assert "Hello world" in text
        assert "<" not in text

    @pytest.mark.asyncio
    async def test_markdown_to_html(self):
        data = b"# Title\n\nHello **world**"
        result = await markup.markdown_to_html(data)
        text = result.decode()
        assert "<h1>" in text
        assert "<strong>world</strong>" in text

    @pytest.mark.asyncio
    async def test_markdown_to_plain_text(self):
        data = b"# Title\n\nHello **world**"
        result = await markup.markdown_to_plain_text(data)
        text = result.decode()
        assert "Title" in text
        assert "world" in text
        assert "**" not in text


# ===== Documents =====

class TestDocumentConversions:
    @pytest.mark.asyncio
    async def test_json_to_html_table(self):
        data = b'[{"name":"Alice","age":30}]'
        result = await documents.json_to_html(data)
        text = result.decode()
        assert "<table>" in text
        assert "Alice" in text

    @pytest.mark.asyncio
    async def test_json_to_markdown_table(self):
        data = b'[{"name":"Alice","age":30}]'
        result = await documents.json_to_markdown_table(data)
        text = result.decode()
        assert "| name |" in text or "| name | age |" in text
        assert "Alice" in text

    @pytest.mark.asyncio
    async def test_csv_to_html(self):
        data = b"name,age\nAlice,30"
        result = await documents.csv_to_html(data)
        assert b"<table>" in result
        assert b"Alice" in result

    @pytest.mark.asyncio
    async def test_json_to_excel_roundtrip(self):
        data = b'[{"name":"Alice","age":30}]'
        excel_bytes = await documents.json_to_excel(data)
        assert len(excel_bytes) > 0
        # Round-trip: Excel → JSON
        result = await documents.excel_to_json(excel_bytes)
        obj = json.loads(result)
        assert obj[0]["name"] == "Alice"


# ===== Encoding =====

class TestEncodingConversions:
    @pytest.mark.asyncio
    async def test_base64_roundtrip(self):
        original = b"Hello, World!"
        encoded = await encoding.to_base64(original)
        decoded = await encoding.from_base64(encoded)
        assert decoded == original

    @pytest.mark.asyncio
    async def test_url_encode_roundtrip(self):
        original = b"hello world&foo=bar"
        encoded = await encoding.to_url_encoded(original)
        assert b" " not in encoded
        decoded = await encoding.from_url_encoded(encoded)
        assert decoded == original

    @pytest.mark.asyncio
    async def test_hex_roundtrip(self):
        original = b"Hello"
        encoded = await encoding.to_hex(original)
        assert encoded == b"48656c6c6f"
        decoded = await encoding.from_hex(encoded)
        assert decoded == original


# ===== Schema Reshaping =====

class TestSchemaReshape:
    @pytest.mark.asyncio
    async def test_simple_reshape(self):
        data = b'{"response":{"data":{"user":{"name":"Alice","id":42}}}}'
        options = {"mapping": {"name": "response.data.user.name", "user_id": "response.data.user.id"}}
        result = await reshape_json(data, options)
        obj = json.loads(result)
        assert obj["name"] == "Alice"
        assert obj["user_id"] == 42

    @pytest.mark.asyncio
    async def test_array_reshape(self):
        data = b'[{"a":{"b":1}},{"a":{"b":2}}]'
        options = {"mapping": {"value": "a.b"}}
        result = await reshape_json(data, options)
        obj = json.loads(result)
        assert len(obj) == 2
        assert obj[0]["value"] == 1
        assert obj[1]["value"] == 2

    @pytest.mark.asyncio
    async def test_nested_target(self):
        data = b'{"first":"Alice","last":"Smith"}'
        options = {"mapping": {"user.first_name": "first", "user.last_name": "last"}}
        result = await reshape_json(data, options)
        obj = json.loads(result)
        assert obj["user"]["first_name"] == "Alice"
        assert obj["user"]["last_name"] == "Smith"

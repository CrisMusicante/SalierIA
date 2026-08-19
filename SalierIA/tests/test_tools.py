import json
from pathlib import Path

import pytest

TOOLS_PATH = Path(__file__).parent.parent / 'docs' / 'tools.json'
EXPECTED_TOOLS = {
    'add_note', 'add_chord', 'add_rest', 'set_dynamic', 'set_articulation',
    'add_slur', 'add_hairpin', 'set_tempo', 'add_measures', 'delete_notes',
    'get_score_info', 'set_key_signature', 'set_time_signature', 'add_text',
    'export_score', 'undo', 'select_passage', 'transpose_passage',
}


def _load():
    return json.loads(TOOLS_PATH.read_text(encoding='utf-8'))


def test_tools_file_exists():
    assert TOOLS_PATH.exists()


def test_tools_is_valid_json():
    _load()


def test_tools_has_tools_key():
    data = _load()
    assert 'tools' in data
    assert isinstance(data['tools'], list)


def test_minimum_tool_count():
    data = _load()
    assert len(data['tools']) >= 18


def test_no_duplicate_tool_names():
    data = _load()
    names = [t['name'] for t in data['tools']]
    assert len(names) == len(set(names))


def test_each_tool_has_required_fields():
    data = _load()
    for tool in data['tools']:
        assert isinstance(tool.get('name'), str)
        assert isinstance(tool.get('description'), str)
        assert isinstance(tool.get('input_schema'), dict)


def test_input_schema_structure():
    data = _load()
    for tool in data['tools']:
        schema = tool['input_schema']
        assert schema.get('type') == 'object'
        assert isinstance(schema.get('properties'), dict)
        assert isinstance(schema.get('required'), list)


def test_known_tools_present():
    data = _load()
    names = {t['name'] for t in data['tools']}
    assert EXPECTED_TOOLS.issubset(names)


def test_add_note_required_fields():
    data = _load()
    add_note = next(t for t in data['tools'] if t['name'] == 'add_note')
    required = add_note['input_schema']['required']
    assert 'pitch' in required
    assert 'duration' in required
    assert 'measure' in required


def test_export_score_formats():
    data = _load()
    export = next(t for t in data['tools'] if t['name'] == 'export_score')
    formats = export['input_schema']['properties']['format']['enum']
    for fmt in ('musicxml', 'pdf', 'midi', 'mp3', 'wav'):
        assert fmt in formats

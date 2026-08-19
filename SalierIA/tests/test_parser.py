import pytest
from src.agent.parser import parse, ParsedIntent

DEFAULT_STATE = {
    'current_measure': 1,
    'last_pitch': 'C4',
    'key': 'C',
    'time_num': 4,
    'time_den': 4,
}


# --- Pitch detection ---

def test_pitch_fa_in_compas_tres():
    result = parse("agrega una negra en fa en el compás tres", DEFAULT_STATE)
    assert result.detected_pitch == 'F4'

def test_pitch_fa_sostenido():
    result = parse("fa sostenido", DEFAULT_STATE)
    assert result.detected_pitch == 'F#4'

def test_pitch_re_bemol():
    result = parse("re bemol", DEFAULT_STATE)
    assert result.detected_pitch == 'Db4'

def test_pitch_do():
    result = parse("do", DEFAULT_STATE)
    assert result.detected_pitch == 'C4'

def test_pitch_sol():
    result = parse("sol", DEFAULT_STATE)
    assert result.detected_pitch == 'G4'

def test_pitch_la():
    result = parse("la", DEFAULT_STATE)
    assert result.detected_pitch == 'A4'

def test_pitch_si():
    result = parse("si", DEFAULT_STATE)
    assert result.detected_pitch == 'B4'

def test_pitch_mi():
    result = parse("mi", DEFAULT_STATE)
    assert result.detected_pitch == 'E4'

def test_pitch_fa_doble_sostenido():
    result = parse("fa doble sostenido", DEFAULT_STATE)
    assert result.detected_pitch == 'F##4'

def test_pitch_re_doble_bemol():
    result = parse("re doble bemol", DEFAULT_STATE)
    assert result.detected_pitch in ('Db4', 'Dbb4')

def test_pitch_missing():
    result = parse("agrega en el compás dos", DEFAULT_STATE)
    assert result.detected_pitch is None

def test_pitch_chord_c_major():
    result = parse("acorde de do mayor", DEFAULT_STATE)
    assert result.detected_pitches == ['C4', 'E4', 'G4']


# --- Duration detection ---

def test_duration_redonda():
    result = parse("redonda", DEFAULT_STATE)
    assert result.detected_duration == 'whole'

def test_duration_blanca():
    result = parse("blanca", DEFAULT_STATE)
    assert result.detected_duration == 'half'

def test_duration_negra():
    result = parse("negra", DEFAULT_STATE)
    assert result.detected_duration == 'quarter'

def test_duration_corchea():
    result = parse("corchea", DEFAULT_STATE)
    assert result.detected_duration == 'eighth'

def test_duration_semicorchea():
    result = parse("semicorchea", DEFAULT_STATE)
    assert result.detected_duration == 'sixteenth'

def test_duration_negra_con_punto():
    result = parse("negra con punto", DEFAULT_STATE)
    assert result.detected_duration == 'quarter'
    assert result.is_dotted is True

def test_duration_blanca_con_puntillo():
    result = parse("blanca con puntillo", DEFAULT_STATE)
    assert result.detected_duration == 'half'
    assert result.is_dotted is True

def test_duration_missing():
    result = parse("do en el compás uno", DEFAULT_STATE)
    assert result.detected_duration is None


# --- Measure detection ---

def test_measure_compas_tres():
    result = parse("compás tres", DEFAULT_STATE)
    assert result.detected_measure == 3

def test_measure_compas_7():
    result = parse("compás 7", DEFAULT_STATE)
    assert result.detected_measure == 7

def test_measure_siguiente():
    state = {**DEFAULT_STATE, 'current_measure': 4}
    result = parse("el siguiente compás", state)
    assert result.detected_measure == 5

def test_measure_mismo():
    state = {**DEFAULT_STATE, 'current_measure': 6}
    result = parse("el mismo compás", state)
    assert result.detected_measure == 6

def test_measure_compas_veinte():
    result = parse("compás veinte", DEFAULT_STATE)
    assert result.detected_measure == 20

def test_measure_no_mention_uses_current():
    state = {**DEFAULT_STATE, 'current_measure': 3}
    result = parse("do negra", state)
    assert result.detected_measure == 3


# --- Dynamic detection ---

def test_dynamic_forte():
    result = parse("forte", DEFAULT_STATE)
    assert result.detected_dynamic == 'f'

def test_dynamic_fortissimo():
    result = parse("fortissimo", DEFAULT_STATE)
    assert result.detected_dynamic == 'ff'

def test_dynamic_piano():
    result = parse("toca en piano la nota do", DEFAULT_STATE)
    assert result.detected_dynamic == 'p'

def test_dynamic_pianissimo():
    result = parse("pianissimo", DEFAULT_STATE)
    assert result.detected_dynamic == 'pp'

def test_dynamic_none():
    result = parse("do negra compás uno", DEFAULT_STATE)
    assert result.detected_dynamic is None


# --- needs_claude flag ---

def test_needs_claude_deshaz():
    result = parse("deshaz el último cambio", DEFAULT_STATE)
    assert result.needs_claude is True

def test_needs_claude_transporta():
    result = parse("transporta los compases tres al cinco", DEFAULT_STATE)
    assert result.needs_claude is True

def test_needs_claude_false_simple_command():
    result = parse("agrega una negra en do en el compás uno", DEFAULT_STATE)
    assert result.needs_claude is False

def test_needs_claude_exporta():
    result = parse("exporta como PDF", DEFAULT_STATE)
    assert result.needs_claude is True


# --- Confidence ---

def test_confidence_full_command():
    result = parse("agrega una negra en do en el compás dos", DEFAULT_STATE)
    assert result.confidence >= 0.9

def test_confidence_missing_measure():
    result = parse("agrega una negra en do", DEFAULT_STATE)
    assert result.confidence >= 0.6

def test_confidence_gibberish():
    result = parse("xyz qwerty blorp", DEFAULT_STATE)
    assert result.confidence <= 0.4

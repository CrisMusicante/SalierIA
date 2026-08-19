from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List, Optional

SOLFEO_MAP = {
    'do': 'C', 're': 'D', 'mi': 'E', 'fa': 'F',
    'sol': 'G', 'la': 'A', 'si': 'B',
}

DURATION_MAP = {
    'redonda': 'whole',
    'blanca': 'half',
    'negra': 'quarter',
    'corchea': 'eighth',
    'semicorchea': 'sixteenth',
    'fusa': 'thirty_second',
}

ORDINAL_MAP = {
    'primero': 1, 'primer': 1, 'segundo': 2, 'tercero': 3, 'tercer': 3,
    'cuarto': 4, 'quinto': 5, 'sexto': 6, 'séptimo': 7, 'octavo': 8,
    'noveno': 9, 'décimo': 10,
    'uno': 1, 'dos': 2, 'tres': 3, 'cuatro': 4, 'cinco': 5, 'seis': 6,
    'siete': 7, 'ocho': 8, 'nueve': 9, 'diez': 10, 'once': 11, 'doce': 12,
    'trece': 13, 'catorce': 14, 'quince': 15, 'dieciséis': 16, 'diecisiete': 17,
    'dieciocho': 18, 'diecinueve': 19, 'veinte': 20,
    '1': 1, '2': 2, '3': 3, '4': 4, '5': 5, '6': 6,
    '7': 7, '8': 8, '9': 9, '10': 10,
}

DYNAMIC_MAP = {
    'pianissimo': 'pp',
    'pianíssimo': 'pp',
    'piano': 'p',
    'mezzo piano': 'mp',
    'mezzo forte': 'mf',
    'forte': 'f',
    'fortissimo': 'ff',
    'sforzando': 'sfz',
    'sforzato': 'sfz',
}

ARTICULATION_MAP = {
    'staccato': 'staccato',
    'tenuto': 'tenuto',
    'acento': 'accent',
    'marcato': 'marcato',
    'fermata': 'fermata',
    'trino': 'trill',
    'mordente': 'mordent',
    'grupeto': 'turn',
}

MAJOR_INTERVALS = [0, 4, 7]
MINOR_INTERVALS = [0, 3, 7]

MIDI_BASE = {'C': 0, 'D': 2, 'E': 4, 'F': 5, 'G': 7, 'A': 9, 'B': 11}

_CHROMATIC = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']

_NEEDS_CLAUDE_WORDS = {
    'transporta', 'crescendo', 'decrescendo', 'exporta', 'elimina',
    'deshaz', 'deshacer', 'importa', 'guarda', 'abre', 'cierra',
    'copia', 'pega', 'corta', 'selecciona', 'imprime',
}


@dataclass
class ParsedIntent:
    raw_transcript: str
    detected_pitch: Optional[str]
    detected_duration: Optional[str]
    detected_measure: Optional[int]
    detected_beat: Optional[float]
    detected_dynamic: Optional[str]
    detected_articulation: Optional[str]
    detected_pitches: Optional[List[str]]
    is_dotted: bool
    confidence: float
    needs_claude: bool


def build_chord_pitches(root_pitch: str, quality: str) -> List[str]:
    letter = root_pitch[0]
    acc = ''
    i = 1
    while i < len(root_pitch) and root_pitch[i] in ('#', 'b'):
        acc += root_pitch[i]
        i += 1
    octave = int(root_pitch[i:]) if i < len(root_pitch) else 4

    root_midi = MIDI_BASE[letter] + acc.count('#') - acc.count('b')
    intervals = MAJOR_INTERVALS if quality == 'major' else MINOR_INTERVALS

    result = []
    for semitones in intervals:
        midi_val = (root_midi + semitones) % 12
        note = _CHROMATIC[midi_val]
        result.append(f"{note}{octave}")
    return result


def _extract_measure(text: str, score_state: dict) -> Optional[int]:
    if 'siguiente compás' in text or 'siguiente compas' in text:
        return score_state.get('current_measure', 1) + 1
    if 'mismo compás' in text or 'mismo compas' in text:
        return score_state.get('current_measure', 1)

    match = re.search(r'(?:el\s+)?comp[aá]s\s+(\S+)', text)
    if match:
        token = match.group(1)
        if token in ORDINAL_MAP:
            return ORDINAL_MAP[token]
    return None


def _extract_beat(text: str) -> Optional[float]:
    match = re.search(r'tiempo\s+(\S+)', text)
    if match:
        token = match.group(1)
        if token in ORDINAL_MAP:
            return float(ORDINAL_MAP[token])
    return None


def _extract_pitch(text: str, score_state: dict) -> Optional[str]:
    last_pitch = score_state.get('last_pitch', 'C4')
    try:
        default_octave = int(last_pitch[-1])
    except (ValueError, IndexError):
        default_octave = 4

    match = re.search(r'\b(do|re|mi|fa|sol|la|si)\b', text)
    if not match:
        return None

    note_name = match.group(1)
    letter = SOLFEO_MAP[note_name]
    remainder = text[match.end():]

    accidental = ''
    if re.match(r'\s+doble\s+sostenido', remainder):
        accidental = '##'
        remainder = re.sub(r'^\s+doble\s+sostenido', '', remainder)
    elif re.match(r'\s+doble\s+bemol', remainder):
        accidental = 'bb'
        remainder = re.sub(r'^\s+doble\s+bemol', '', remainder)
    elif re.match(r'\s+sostenido', remainder):
        accidental = '#'
        remainder = re.sub(r'^\s+sostenido', '', remainder)
    elif re.match(r'\s+bemol', remainder):
        accidental = 'b'
        remainder = re.sub(r'^\s+bemol', '', remainder)

    octave_match = re.match(r'\s+(\d)', remainder)
    octave = int(octave_match.group(1)) if octave_match else default_octave

    return f"{letter}{accidental}{octave}"


def _extract_duration(text: str):
    for key in sorted(DURATION_MAP.keys(), key=len, reverse=True):
        if key in text:
            duration = DURATION_MAP[key]
            idx = text.index(key)
            after = text[idx + len(key):]
            is_dotted = bool(re.search(r'con\s+punt(?:o|illo)', after[:30]))
            return duration, is_dotted
    return None, False


def _extract_chord(text: str, score_state: dict) -> Optional[List[str]]:
    match = re.search(r'acorde\s+de\s+(\S+)\s+(mayor|menor)', text)
    if not match:
        return None
    root_solfeo = match.group(1)
    quality_es = match.group(2)
    if root_solfeo not in SOLFEO_MAP:
        return None
    letter = SOLFEO_MAP[root_solfeo]
    quality = 'major' if quality_es == 'mayor' else 'minor'
    last_pitch = score_state.get('last_pitch', 'C4')
    try:
        octave = int(last_pitch[-1])
    except (ValueError, IndexError):
        octave = 4
    return build_chord_pitches(f"{letter}{octave}", quality)


def _extract_dynamic(text: str) -> Optional[str]:
    for key in sorted(DYNAMIC_MAP.keys(), key=len, reverse=True):
        if re.search(r'\b' + re.escape(key) + r'\b', text):
            return DYNAMIC_MAP[key]
    return None


def _extract_articulation(text: str) -> Optional[str]:
    for key in sorted(ARTICULATION_MAP.keys(), key=len, reverse=True):
        if key in text:
            return ARTICULATION_MAP[key]
    return None


def parse(transcript: str, score_state: dict) -> ParsedIntent:
    normalized = transcript.lower().strip()

    measure = _extract_measure(normalized, score_state)
    beat = _extract_beat(normalized)
    chord_pitches = _extract_chord(normalized, score_state)
    pitch = _extract_pitch(normalized, score_state) if not chord_pitches else chord_pitches[0]
    duration, is_dotted = _extract_duration(normalized)
    dynamic = _extract_dynamic(normalized)
    articulation = _extract_articulation(normalized)

    has_measure_explicit = measure is not None
    if not has_measure_explicit:
        measure = score_state.get('current_measure', 1)

    has_pitch = pitch is not None or chord_pitches is not None
    has_duration = duration is not None

    if has_pitch and has_duration and has_measure_explicit:
        confidence = 1.0
    elif has_pitch and has_duration:
        confidence = 0.7
    elif has_pitch or has_duration:
        confidence = 0.5
    else:
        confidence = 0.3

    words = set(re.findall(r'\b\w+\b', normalized))
    needs_claude = confidence < 0.5 or bool(words & _NEEDS_CLAUDE_WORDS)

    return ParsedIntent(
        raw_transcript=transcript,
        detected_pitch=pitch,
        detected_duration=duration,
        detected_measure=measure,
        detected_beat=beat,
        detected_dynamic=dynamic,
        detected_articulation=articulation,
        detected_pitches=chord_pitches,
        is_dotted=is_dotted,
        confidence=confidence,
        needs_claude=needs_claude,
    )

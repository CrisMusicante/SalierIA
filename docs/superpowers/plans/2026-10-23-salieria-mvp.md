# SalierIA MVP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** The owner says "Salieri, …" in Spanish, with hands on the piano, and the score open in Sibelius 8.2 changes exactly as dictated. Supported commands cover structure, passage edits, expression and instrumentation. A short spoken confirmation lists the steps, and the whole command can be undone.

**Architecture:**
- **Python pipeline:** wake word on the voice channel → endpointing → speech-to-text → a configurable LLM (Claude or an OpenAI-compatible endpoint such as NVIDIA NIM) that emits structured tool calls → a Python music core that validates, resolves targets, transforms passages and checks fit → a batch of primitive commands written to a text file.
- **Sibelius side:** a thin ManuScript plugin executes the batch in one run, triggered by a keyboard shortcut sent to the Sibelius window. ManuScript in 8.2 has no timers, so the plugin cannot poll.
- **Where the logic lives:** all musical logic is in Python (spec §7). The plugin only reads and writes the score.

**Tech Stack:**
- Python 3.13 in a venv. 3.14 is installed but is too new for several wheels.
- pytest.
- `anthropic`, `openai` (for OpenAI-compatible and NVIDIA endpoints).
- `faster-whisper` (CPU, int8).
- `vosk` with the Spanish small model, for the wake word.
- `webrtcvad-wheels`, `sounddevice`, `numpy`, `scipy`.
- `pyttsx3` (SAPI), `pystray`, `Pillow`, `pywinauto`.
- ManuScript (Sibelius 8.2).

**Spec:** `docs/superpowers/specs/2026-10-23-salieria-mvp-design.md`. Read it before any task.

**Paths:** code paths below are relative to the inner project dir `SalierIA/` (git root is one level up). Run all commands from there.

## Global Constraints

- Windows 11 only. Sibelius 8.2.0 is the only target. No Mac, installers or other editors.
- ManuScript 8.2-era API only. There is no `Sibelius.Execute`, no Sibelius Connect, no timers, and no `GetEnvironmentVariable`, `SaveTextFile`, `SetTimerAction` or `Sibelius.Undo`. Reference: the ManuScript Language Guide 2018.1 PDF from Avid.
- Positions and durations are in ManuScript units: 1 quarter = 256. Whole = 1024, half = 512, eighth = 128, sixteenth = 64, thirty-second = 32. A dot multiplies by 1.5.
- Bar numbers are 1-based. Beats are 1-based. Stave numbers are 1-based, top to bottom, the way ManuScript numbers them.
- ManuScript has no JSON parser. The bridge file format is tab-separated lines (Task 6).
- All user-facing speech is Spanish.
- Preferences and API keys live in `%APPDATA%\SalierIA\preferences.json`, never in the repo.
- Default execution mode is `act_then_announce`. The other mode is `announce_then_wait`.
- Latency target: about 3 s from end of utterance to result in the score.
- On an ambiguous target ("el piano" with no staff) or a duration/rest change that does not fit its range, the assistant asks and does not execute, in both modes.
- Paste overwrites the destination.
- Retrograde is strict (pitches and rhythm, chords as a block). Ties, slurs, dynamics and articulations are not carried over. The confirmation ends with the warning: `Aviso: las ligaduras, dinámicas y articulaciones no se copiaron.`

## Review Focus

1. **A passage that crosses a time-signature change** (for example, bars 5–10 with a 3/4 bar inside). Beat-to-tick math must use each bar's own meter. Test: `test_range_across_meter_change` in Task 2.
2. **Durations or rests that make notes cross a barline.** They must be split into tied notes, not dropped or truncated. Test: `test_split_note_across_barline` in Task 3.
3. **An instrument name the transcription mangles** ("violín uno", "Violin 1", "violin I" vs. score name "Violin 1"). It must resolve, or ask. It must never pick the wrong stave silently. Test: `test_name_variants_resolve` in Task 4.
4. **Sibelius not running, not focused, or a dialog open.** Expect a clear spoken error and no partial state assumed. Test: `test_timeout_raises_and_no_undo_recorded` in Task 6.
5. **"Deshaz eso" with nothing to undo, or right after a failed command.** It must say there is nothing to undo, not send Ctrl+Z. Test: `test_undo_with_empty_history` in Task 12.

---

### Task 0: Spike — validate the Sibelius trigger path (manual, with the owner)

Everything downstream depends on this (spec §6). It is a throwaway, and no tests are written.

**Files:**
- Create: `spikes/SalieriSpike.plg`
- Create: `spikes/trigger_spike.py`
- Create: `../docs/superpowers/spikes/2026-10-23-sibelius-trigger.md` (results)

- [ ] **Step 1: Write `SalieriSpike.plg`.** It reads `C:\Temp\salieri\cmd.txt` with `Sibelius.ReadTextFile`, adds 3 notes to bar 1 of stave 1 with `Bar.AddNote`, inserts 1 bar with `Score.InsertBars`, then writes `C:\Temp\salieri\resp.txt` with `Sibelius.CreateTextFile` + `AppendTextFile` containing the cmd id and elapsed ms (`ResetStopWatch` / `GetElapsedMilliSeconds`).
- [ ] **Step 2: Owner installs the plugin.** Copy it to `%APPDATA%\Avid\Sibelius\Plugins\Salieri\`, restart Sibelius, and assign the shortcut **Ctrl+Alt+Shift+S** in File > Preferences > Keyboard Shortcuts.
- [ ] **Step 3: Write `trigger_spike.py`.** It writes `cmd.txt`, focuses the window matching `.*Sibelius.*` with `pywinauto` (`Application(backend='uia').connect(title_re=...)`, `set_focus()`), sends the shortcut with `send_keys('^%+s')`, and polls `resp.txt` every 50 ms for 8 s. It prints the round-trip time.
- [ ] **Step 4: Owner runs it 10 times.** Run with Sibelius in the foreground, then with another window focused.
  - Expected: 10/10 responses and a median round trip under 1000 ms.
- [ ] **Step 5: Owner presses Ctrl+Z once in Sibelius.**
  - Record whether the whole run (3 notes + bar) disappears in one undo step, or how many steps it takes.
- [ ] **Step 6: Record the results in the spike doc.** Include success rate, latency, undo steps per run, and any dialog that appeared.
  - **Gate:** if responses fail or focus cannot be forced, STOP and go back to the owner (spec §6 plan B).
  - If one run is more than one undo step, Task 12 uses the counted-Ctrl+Z path (already designed in).
- [ ] **Step 7: Commit.** `git add spikes ../docs/superpowers/spikes && git commit -m "spike: validate Sibelius shortcut trigger"`

---

### Task 1: Project setup and removal of dead code

**Files:**
- Create: `pyproject.toml` (pytest config only: `[tool.pytest.ini_options] pythonpath = ["."]`, `testpaths = ["tests"]`)
- Modify: `requirements.txt`
- Delete: `src/agent/parser.py`, `src/agent/score_state.py`, `src/agent/claude_agent.py`, `src/bridge/ipc.py`, `src/bridge/ui_fallback.py`, `tests/test_parser.py`, `tests/test_ipc.py`, `sibelius_plugin/VoiceAgentBridge.plg`, `files/` (duplicate of `docs/`)
- Modify: `../CLAUDE.md` (architecture section → point to the spec and plan; Python 3.13 venv command)

- [ ] **Step 1: Create the venv.** `py -3.13 -m venv .venv`, then `.venv\Scripts\python -m pip install -r requirements.txt`.
  - `requirements.txt`: anthropic, openai, faster-whisper, vosk, webrtcvad-wheels, sounddevice, numpy, scipy, pyttsx3, pystray, Pillow, pywinauto, pytest.
  - Remove `openai-whisper`, `keyboard` and `python-dotenv`.
  - Expected: install succeeds.
- [ ] **Step 2: Delete the listed files.** Keep `tests/test_tools.py` for now; Task 5 rewrites it.
- [ ] **Step 3: Run the suite.** `.venv\Scripts\python -m pytest`
  - Expected: `test_tools.py` passes and nothing else errors on import.
- [ ] **Step 4: Commit.** `git commit -am "chore: py3.13 venv, new deps, remove untested v1 code"` (stage the deletions with `git add -A`).

---

### Task 2: Music core — positions, durations, ranges

**Files:**
- Create: `src/music/__init__.py`, `src/music/time.py`
- Test: `tests/music/test_time.py`

**Interfaces:**
- Produces:
  - `QUARTER = 256`.
  - `DURATIONS: dict[str, int]` with the keys `whole, half, quarter, eighth, sixteenth, thirty_second`.
  - `duration_ticks(name: str, dots: int = 0) -> int`.
  - `@dataclass(frozen=True) class Meter(num: int, den: int)` with `.bar_ticks -> int` and `.beat_ticks -> int`.
    - A beat is the denominator's note value, so 6/8 has six beats. This is my call; it is stated in the system prompt.
  - `@dataclass(frozen=True) class BarPos(bar: int, tick: int)`.
  - `beat_start(bar: int, beat: int, meter: Meter) -> BarPos`.
  - `beat_end(bar: int, beat: int | Literal["last"], meter: Meter) -> BarPos`. Exclusive end: the start of the next beat, or the bar end.
  - `@dataclass(frozen=True) class Span(start: BarPos, end: BarPos)`.
  - `span_length(span: Span, meters: dict[int, Meter]) -> int` — total ticks across bars.
  - `to_absolute(pos: BarPos, origin: BarPos, meters: dict[int, Meter]) -> int` and its inverse `from_absolute(ticks: int, origin: BarPos, meters) -> BarPos`.

- [ ] **Step 1: Write the failing tests.**

```python
def test_beat_start_4_4():
    assert beat_start(5, 2, Meter(4, 4)) == BarPos(5, 256)

def test_last_beat_end_is_bar_end():
    assert beat_end(10, "last", Meter(4, 4)) == BarPos(10, 1024)

def test_6_8_beat_is_eighth():
    assert Meter(6, 8).beat_ticks == 128 and Meter(6, 8).bar_ticks == 768

def test_dotted_quarter():
    assert duration_ticks("quarter", dots=1) == 384

def test_span_length_reference_example():
    meters = {b: Meter(4, 4) for b in range(1, 20)}
    span = Span(beat_start(5, 2, meters[5]), beat_end(10, "last", meters[10]))
    assert span_length(span, meters) == 768 + 5 * 1024

def test_range_across_meter_change():
    meters = {5: Meter(4, 4), 6: Meter(3, 4), 7: Meter(4, 4)}
    span = Span(BarPos(5, 0), BarPos(7, 1024))
    assert span_length(span, meters) == 1024 + 768 + 1024
    assert from_absolute(1024 + 768 + 10, BarPos(5, 0), meters) == BarPos(7, 10)

def test_beat_out_of_range_raises():
    with pytest.raises(ValueError):
        beat_start(3, 5, Meter(4, 4))
```

- [ ] **Step 2: Run the tests.** `.venv\Scripts\python -m pytest tests/music/test_time.py -v`
  - Expected: FAIL (module missing).
- [ ] **Step 3: Implement `src/music/time.py`** with the signatures above.
- [ ] **Step 4: Run the tests again.** Same command.
  - Expected: PASS.
- [ ] **Step 5: Commit.** `git commit -m "feat(music): ticks, meters, beat positions and spans"`

---

### Task 3: Music core — events, retrograde, durations, fit, bar splitting

**Files:**
- Create: `src/music/events.py`, `src/music/transform.py`
- Test: `tests/music/test_transform.py`

**Interfaces:**
- Consumes: Task 2 (`BarPos`, `Meter`, `to_absolute`, `from_absolute`).
- Produces:
  - `@dataclass(frozen=True) class Event(start: int, duration: int, pitches: tuple[int, ...], tied: bool = False)`. `start` is absolute ticks from the passage origin. An empty `pitches` is a rest.
  - `retrograde(events: list[Event], length: int) -> list[Event]`. Each event moves to `length - (start + duration)`, the list is reversed and `tied` is cleared.
  - `with_durations(events: list[Event], durations: list[int]) -> list[Event]`. Events are laid end to end from 0. If one duration is given, it applies to every note. Otherwise `len(durations) == len(events)`; on mismatch raise `ValueError`.
  - `@dataclass class Fit(status: Literal["exact", "short", "overflow"], delta: int)`.
  - `check_fit(events: list[Event], length: int) -> Fit`.
  - `fill_rests(events, length) -> list[Event]`: appends rests to reach `length`.
  - `notes_to_rests(events) -> list[Event]`.
  - `insert_rest(events, at: int, duration: int) -> list[Event]`: shifts the following events.
  - `@dataclass(frozen=True) class BarEvent(bar: int, pos: int, duration: int, pitches: tuple[int, ...], tied: bool)`.
  - `split_into_bars(events: list[Event], origin: BarPos, meters: dict[int, Meter]) -> list[BarEvent]`. A note crossing a barline becomes two notes, and the first is `tied=True`. A rest crossing a barline becomes two rests.

- [ ] **Step 1: Write the failing tests.**

```python
def test_retrograde_strict():
    ev = [Event(0, 256, (60,)), Event(256, 128, (62,)), Event(384, 128, (64,)), Event(512, 512, ())]
    assert retrograde(ev, 1024) == [Event(0, 512, ()), Event(512, 128, (64,)), Event(640, 128, (62,)), Event(768, 256, (60,))]

def test_retrograde_chord_is_block_and_ties_cleared():
    ev = [Event(0, 512, (60, 64, 67), tied=True), Event(512, 512, (62,))]
    assert retrograde(ev, 1024) == [Event(0, 512, (62,)), Event(512, 512, (60, 64, 67))]

def test_with_durations_single_value():
    ev = [Event(0, 256, (60,)), Event(256, 256, (62,))]
    assert with_durations(ev, [128]) == [Event(0, 128, (60,)), Event(128, 128, (62,))]

def test_fit_short_when_sixteen_quarters_become_eighths():
    ev = [Event(i * 256, 256, (60,)) for i in range(16)]
    assert check_fit(with_durations(ev, [128]), 4 * 1024) == Fit("short", 2048)

def test_fit_overflow():
    ev = [Event(0, 256, (60,))] * 4
    assert check_fit(with_durations(ev, [512]), 1024).status == "overflow"

def test_split_note_across_barline():
    meters = {1: Meter(4, 4), 2: Meter(4, 4)}
    out = split_into_bars([Event(768, 512, (60,))], BarPos(1, 0), meters)
    assert out == [BarEvent(1, 768, 256, (60,), True), BarEvent(2, 0, 256, (60,), False)]

def test_insert_rest_shifts_following():
    ev = [Event(0, 256, (60,)), Event(256, 256, (62,))]
    assert insert_rest(ev, 256, 256) == [Event(0, 256, (60,)), Event(256, 256, ()), Event(512, 256, (62,))]
```

- [ ] **Step 2: Run the tests.** `.venv\Scripts\python -m pytest tests/music/test_transform.py -v`
  - Expected: FAIL.
- [ ] **Step 3: Implement `src/music/events.py` and `src/music/transform.py`.** All functions are pure.
- [ ] **Step 4: Run the tests again.** Same command.
  - Expected: PASS.
- [ ] **Step 5: Commit.** `git commit -m "feat(music): events, strict retrograde, durations, fit check, bar split"`

---

### Task 4: Score snapshot and target resolution

**Files:**
- Create: `src/score/__init__.py`, `src/score/snapshot.py`, `src/score/targeting.py`
- Test: `tests/score/test_targeting.py`

**Interfaces:**
- Consumes: Task 2 (`Meter`).
- Produces:
  - `@dataclass(frozen=True) class Stave(number: int, instrument: str, clef: str, index_in_instrument: int, staves_in_instrument: int)`. `clef` is `"treble" | "bass" | "alto" | "tenor" | "percussion"`.
  - `@dataclass class ScoreSnapshot(staves: list[Stave], meters: dict[int, Meter], bar_count: int)`.
  - `@dataclass(frozen=True) class Target(stave: int, voice: int, label: str)`. `label` is spoken, e.g. `"Piano, mano derecha, voz 1"` or `"Violín 1"`.
  - `@dataclass(frozen=True) class Ambiguity(question: str)`.
  - `resolve_target(instrument: str | None, staff: str | None, voice: int | None, snap: ScoreSnapshot, last: Target | None) -> Target | Ambiguity`.
- Rules (spec §3.2):
  - Names are normalized before matching: lowercase, accents stripped, `uno|dos|tres|i|ii|iii` → `1|2|3`.
  - The `staff` hints are: `upper` for "mano derecha", "arriba", "clave de sol"; `lower` for "mano izquierda", "abajo", "clave de fa". The LLM sends `"upper" | "lower" | None`.
  - A multi-stave instrument with `staff=None` gives `Ambiguity("¿Qué pentagrama del <instrumento> y qué voz?")`.
  - `instrument=None` reuses `last`, or the only stave if there is exactly one. Otherwise it gives `Ambiguity("¿En qué instrumento?")`.
  - `voice=None` means voice 1 (my call).
  - No match gives `Ambiguity("No encuentro el instrumento <x>. ¿Cuál es?")`.

- [ ] **Step 1: Write the failing tests.** Fixture `snap`: Violin 1 (stave 1), Violin 2 (2), Piano treble (3), Piano bass (4), all in 4/4, 32 bars.

```python
def test_name_variants_resolve(snap):
    for spoken in ["violín 1", "Violin uno", "violin I"]:
        assert resolve_target(spoken, None, None, snap, None) == Target(1, 1, "Violin 1, voz 1")

def test_piano_without_staff_asks(snap):
    assert isinstance(resolve_target("piano", None, None, snap, None), Ambiguity)

def test_piano_right_hand_voice_1(snap):
    assert resolve_target("piano", "upper", 1, snap, None).stave == 3

def test_omitted_instrument_reuses_last(snap):
    last = Target(2, 1, "Violin 2, voz 1")
    assert resolve_target(None, None, None, snap, last) == last

def test_unknown_instrument_asks(snap):
    assert "flauta" in resolve_target("flauta", None, None, snap, None).question
```

- [ ] **Step 2: Run the tests.** `.venv\Scripts\python -m pytest tests/score -v`
  - Expected: FAIL.
- [ ] **Step 3: Implement the snapshot and targeting modules.**
- [ ] **Step 4: Run the tests again.** Same command.
  - Expected: PASS.
- [ ] **Step 5: Commit.** `git commit -m "feat(score): snapshot model and instrument/staff/voice resolution"`

---

### Task 5: Tool schema and operation models

**Files:**
- Modify: `docs/tools.json` (full rewrite)
- Create: `src/commands/__init__.py`, `src/commands/ops.py`
- Modify: `tests/test_tools.py` (rewrite)

**Interfaces:**
- Produces:
  - `parse_tool_call(name: str, args: dict) -> Op` (raises `ValueError` on schema violations).
  - One frozen dataclass per op, each subclassing `Op`.
- Shared shapes:
  - Target fields: `instrument: str|None, staff: "upper"|"lower"|None, voice: int|None`.
  - Location: `{"bar": int, "beat": int}`, where an end beat may be `"last"`.
- Interval: `{"number": 1..15, "quality": "perfect"|"major"|"minor"|"augmented"|"diminished", "direction": "up"|"down"}`.
  - "Un tono" = `{2, major, up}`.
  - `to_manuscript(interval) -> tuple[int, int]` returns (degree = `±(number-1)`, interval type).
  - Interval-type values: Perfect/Major = 5, Minor/Diminished = 4, Augmented = 6.
- Tools: there are 18 in all, one per operation in spec §3.1, plus undo, correction and asking.
  - `add_bars(count, after_bar)`, `delete_bars(start_bar, end_bar)`.
  - `set_time_signature(bar, num, den)`, `set_key_signature(bar, key, mode)`, `set_tempo(bar, bpm, text?)`.
  - `set_durations(target, start, end, durations: list[{figure, dots}])`.
  - `write_rests(target, start, end, kind: "notes_to_rests"|"insert", figure?, dots?)`.
  - `copy_passage(target, start, end, dest_target, dest_start, retrograde: bool, transpose: Interval|null)`. This one tool covers the §3.3 compound case.
  - `transpose_passage(target, start, end, interval)`, `retrograde_passage(target, start, end)`.
  - `add_dynamic(target, at, text: "ppp".."fff"|"sfz"|"fp")`, `add_hairpin(target, start, end, kind: "cresc"|"dim")`.
  - `add_slur(target, start, end)`, `add_articulation(target, start, end, name: "staccato"|"staccatissimo"|"tenuto"|"accent"|"marcato"|"wedge")`.
  - `add_instrument(name)`, `change_instrument(target, at_bar, new_instrument)`.
  - `undo_last()`.
  - `replace_last(calls: list[tool call])` for "no, era el compás 16".
  - `ask_user(question)`.
  - `resolve_pending(choice: "shift"|"fill_rests"|"overwrite"|"cancel"|"confirm")`.

- [ ] **Step 1: Rewrite `tests/test_tools.py`.**
  - It asserts that the tool names in `docs/tools.json` equal the exact set above.
  - It asserts that every tool has `name`, `description` (Spanish) and `input_schema` with `type: object`.
  - It adds `test_reference_example_parses`: the §3.3 call `copy_passage` with `start {5,2}`, `end {10,"last"}`, `dest_start {15,1}`, `retrograde: True`, transpose `{2,"major","up"}` parses to a `CopyPassage` op.
  - It adds `test_tone_up_maps_to_manuscript`: `to_manuscript(Interval(2,"major","up")) == (1, 5)`.
  - It adds `test_bad_beat_rejected`: `beat: 0` raises `ValueError`.
- [ ] **Step 2: Run the tests.** `.venv\Scripts\python -m pytest tests/test_tools.py -v`
  - Expected: FAIL.
- [ ] **Step 3: Write `docs/tools.json`** in Anthropic tool format (`{"tools": [...]}`), then implement `src/commands/ops.py`.
- [ ] **Step 4: Run the tests again.** Same command.
  - Expected: PASS.
- [ ] **Step 5: Commit.** `git commit -m "feat(commands): MVP tool schema and op models"`

---

### Task 6: Bridge protocol and Sibelius client (Python side)

**Files:**
- Create: `src/bridge/protocol.py`, `src/bridge/sibelius_client.py`, `tests/fixtures/protocol/`
- Test: `tests/bridge/test_protocol.py`, `tests/bridge/test_client.py`

**Interfaces:**
- Consumes: Task 3 (`BarEvent`).
- Produces:
  - `Primitive = tuple[str, ...]`, one tab-separated line. Each primitive takes the plugin's arguments in this order:
    - `score_info`
    - `read <stave> <voice> <startBar> <startPos> <endBar> <endPos>`
    - `clear <stave> <voice> <startBar> <startPos> <endBar> <endPos>`
    - `note <stave> <voice> <bar> <pos> <dur> <tied 0|1> <pitch,pitch,...>` (an empty pitch list is a rest)
    - `copy <stave> <startBar> <startPos> <endBar> <endPos> <destStave> <destBar> <destPos>`
    - `transpose <stave> <startBar> <startPos> <endBar> <endPos> <degree> <type>`
    - `insert_bars <count> <beforeBar>` and `delete_bars <start> <end>`
    - `time_sig <bar> <num> <den>`, `key_sig <bar> <sharps> <major 0|1>`, `tempo <bar> <bpm> <text>`
    - `text <stave> <voice> <bar> <pos> <style> <text>`
    - `line <stave> <voice> <bar> <pos> <dur> <style>`
    - `artic <stave> <voice> <startBar> <startPos> <endBar> <endPos> <constant>`
    - `add_instrument <styleId>` and `change_instrument <stave> <bar> <pos> <styleId>`
  - Command file `cmd.txt`: line 1 is `SALIERI1\t<cmd_id>`, then one primitive per line.
  - Response file `resp.txt`:
    - line 1: `<cmd_id>\tok|error\t<message>`;
    - then data lines `stave\t<n>\t<instrument>\t<clef>\t<idx>\t<count>`, `bar\t<n>\t<num>\t<den>` and `ev\t<bar>\t<pos>\t<dur>\t<tied>\t<pitches>`.
  - `encode_command(cmd_id: str, prims: list[Primitive]) -> str`.
  - `decode_response(text: str) -> Response(cmd_id, ok: bool, message: str, data: list[list[str]])`.
  - `parse_snapshot(resp) -> ScoreSnapshot` and `parse_events(resp, origin: BarPos, meters) -> list[Event]`.
  - `class SibeliusClient(bridge_dir: Path, trigger: Callable[[], None], timeout: float = 8.0)` with:
    - `run(prims) -> Response`: atomic write (tmp + `os.replace`), delete any old response first, call `trigger()`, poll every 50 ms. Timeout raises `SibeliusTimeout`. `ok=False` raises `SibeliusError(message)`.
    - `undo(steps: int)`: sends Ctrl+Z `steps` times via the trigger's window helper.
  - `class HotkeyTrigger(title_re=".*Sibelius.*", keys="^%+s")`, a pywinauto implementation. It is not unit-tested; Task 0 proved it.
- Bridge dir: `%LOCALAPPDATA%\SalierIA\bridge`. The plugin has this path hardcoded and gets it from `Sibelius.GetUserApplicationDataFolder`/... if that exists in 8.2; otherwise `C:\Temp\salieri`. **Confirm in Task 0 and use the same constant in both places.**

- [ ] **Step 1: Write the failing tests.**
  - Round-trip `encode_command`, and `decode_response` on the fixture files `tests/fixtures/protocol/score_info_resp.txt` and `read_resp.txt` (write these fixtures by hand from the format above).
  - `test_client_returns_response` uses a fake trigger that writes the matching `resp.txt`.
  - `test_timeout_raises_and_no_undo_recorded` uses a no-op trigger with `timeout=0.3`, expects `SibeliusTimeout`, and checks that `cmd.txt` was cleaned up.
  - `test_error_status_raises` covers the `ok=False` path.
- [ ] **Step 2: Run the tests.** `.venv\Scripts\python -m pytest tests/bridge -v`
  - Expected: FAIL.
- [ ] **Step 3: Implement the protocol and the client.**
- [ ] **Step 4: Run the tests again.** Same command.
  - Expected: PASS.
- [ ] **Step 5: Commit.** `git commit -m "feat(bridge): line protocol and shortcut-triggered Sibelius client"`

---

### Task 7: ManuScript plugin `SalieriExec.plg` (manual verification)

**Files:**
- Create: `sibelius_plugin/SalieriExec.plg`
- Create: `sibelius_plugin/README.md` (install path, shortcut, bridge dir)
- Create: `tools/send_primitives.py` (CLI: `python -m tools.send_primitives "<prim line>" ...` that sends a batch through `SibeliusClient` + `HotkeyTrigger` and prints the response)

**Interfaces:**
- Consumes: the Task 6 protocol, exactly.
- ManuScript calls to use (Guide 2018.1):
  - Score structure: `Score.NthStave`, `Stave.NthBar`, `Bar.Length`, `Score.SystemStaff` (time signatures), `Stave.InstrumentName`.
  - Reading notes: `NoteRest` iteration with `.Position`, `.Duration`, `.VoiceNumber`, `NoteCount`, `Note.Pitch`, `Note.Tied`.
  - Writing notes: `Bar.AddNote(pos, pitch, dur, tied, voice)`, `Bar.Clear(voice)` for whole bars, and per-object `Delete()` for partial ranges.
  - Selection and pitch: `Score.Selection.SelectPassage`, `Selection.Copy(1)`, `Selection.PasteToPosition`, `Selection.Transpose(degree, type)`.
  - Bars and signatures: `Score.InsertBars(n, barNum)`, `Bar.Delete()`, `Bar.AddTimeSignature(num, den, True, True)`, `Bar.AddKeySignature(pos, sharps, major)`.
  - Text and lines: `Bar.AddText(pos, text, "text.staff.expression" | "text.system.tempo" | "text.system.metronome", voice)`, `Bar.AddLine(pos, dur, "line.staff.slur.up" | "line.staff.hairpin.crescendo" | "line.staff.hairpin.diminuendo", 0, 0, voice)`.
  - Articulations: `NoteRest.SetArticulation(const, True)`. The constants are Staccato 1, Staccatissimo 2, Wedge 3, Tenuto 4, Accent 5, Marcato 6.
  - Instruments: `Score.CreateInstrumentAtBottom(styleId)`, `Bar.AddInstrumentChange(pos, styleId)`.
  - Files: `ReadTextFile`, `CreateTextFile`, `AppendTextFile`.
- All primitives of one command run inside a single plugin run (one undo step, per Task 0). On the first failing primitive, write `error` with the line number and stop. Never show a dialog.

- [ ] **Step 1: Write the plugin.** Do the read side first (`score_info`, `read`), then the write side.
- [ ] **Step 2: Owner checks the read side.** Install the plugin and open `tests/fixtures/scores/salieri_test.sib`; the owner creates it: Violin 1, Violin 2, Piano, 4/4, 16 bars, a known melody in bars 5–10 of Violin 1.
  - Run `python -m tools.send_primitives "score_info"` and `"read\t1\t1\t5\t256\t10\t1024"`.
  - Expected: the stave list matches the score, and the events match the written melody.
- [ ] **Step 3: Owner checks each write primitive.** Run one `send_primitives` call per primitive type against the test score, check the result visually, and press Ctrl+Z once.
  - Expected: the change appears and one Ctrl+Z removes the whole batch.
  - Record pass/fail per primitive in `sibelius_plugin/README.md`.
- [ ] **Step 4: Commit.** `git commit -m "feat(plugin): SalieriExec ManuScript executor"`

---

### Task 8: Planner and executor (op → primitives, fit questions)

**Files:**
- Create: `src/commands/executor.py`
- Test: `tests/commands/test_executor.py`

**Interfaces:**
- Consumes:
  - Task 3: `retrograde`, `with_durations`, `check_fit`, `fill_rests`, `notes_to_rests`, `insert_rest`, `split_into_bars`.
  - Task 4: `resolve_target`, `Ambiguity`.
  - Task 5: op classes and `to_manuscript`.
  - Task 6: `SibeliusClient`, `parse_events`, `parse_snapshot`.
- Produces:
  - `@dataclass class Done(steps: list[str], target_label: str | None, warnings: list[str], undo_steps: int)`. `steps` are the spoken step phrases.
  - `@dataclass class Ask(question: str, pending: PendingOp | None)`.
  - `class Executor(client: SibeliusClient)` with:
    - `refresh() -> ScoreSnapshot` (runs `score_info`);
    - `describe(ops, snap, last) -> Done | Ask` (dry run: resolves targets and builds the step phrases, no writes);
    - `execute(ops, snap, last) -> Done | Ask`.
- Behaviour:
  - **Plain copy, no transform:** a single `copy` primitive (keeps slurs and dynamics).
  - **Copy with retrograde and/or transpose:**
    1. `read` the source.
    2. Apply `retrograde` in Python.
    3. `clear` the destination span and write `note` primitives from `split_into_bars`.
    4. Then `transpose` over the destination span.
    5. Add the warning `Aviso: las ligaduras, dinámicas y articulaciones no se copiaron.`
    - Step phrases for §3.3, exactly: `["seleccionar compás 5 tiempo 2 a compás 10", "copiar", "retrogradar", "subir un tono", "pegar en compás 15 tiempo 1"]`.
  - **`set_durations` and `write_rests`:** `read`, transform and `check_fit` against the span length.
    - `exact`: clear + write.
    - Otherwise: `Ask("No cabe: sobran|faltan <n> tiempos en ese rango. ¿Recorro la música siguiente, relleno con silencios, invado lo que sigue o cancelo?", pending)`.
    - `resolve_pending` maps the choices:
      - `fill_rests` → `fill_rests`;
      - `overwrite` → write past the span;
      - `shift` → read from the span start to the stave end, rebuild, add bars with `insert_bars` if needed, rewrite;
      - `cancel` → nothing.
  - **Every other op** maps 1:1 to its primitive.
  - **One user command → one `client.run` for all writes.** `undo_steps` = 1, or the per-run count measured in Task 0.

- [ ] **Step 1: Write the failing tests.** Use a `FakeClient` that records primitives and returns canned `read` / `score_info` responses built from the Task 4 fixture.
  - `test_reference_example_primitives_and_steps`: the §3.3 op gives exactly one write `run`. It contains `clear` (stave 1, 15:0 → end of the span), `note` lines whose pitches equal the retrograde of the canned read, and `transpose ... 1 5`. `Done.steps` equals the five phrases above, and the warning is present.
  - `test_plain_copy_uses_native_copy`.
  - `test_durations_short_asks_with_four_options`: `Ask.question` contains "relleno con silencios", and nothing is written.
  - `test_resolve_fill_rests_writes_rests`.
  - `test_ambiguous_target_asks_and_writes_nothing`: "piano" with no staff.
  - `test_describe_does_not_write` for `announce_then_wait`.
- [ ] **Step 2: Run the tests.** `.venv\Scripts\python -m pytest tests/commands -v`
  - Expected: FAIL.
- [ ] **Step 3: Implement `src/commands/executor.py`.**
- [ ] **Step 4: Run the tests again.** Same command.
  - Expected: PASS.
- [ ] **Step 5: Commit.** `git commit -m "feat(commands): executor with retrograde/transpose copy and fit questions"`

---

### Task 9: Spoken announcements

**Files:**
- Create: `src/speech/__init__.py`, `src/speech/announce.py`
- Test: `tests/speech/test_announce.py`

**Interfaces:**
- Consumes: Task 8 (`Done`, `Ask`).
- Produces: `announce(result: Done | Ask, mode: Literal["act_then_announce", "announce_then_wait"]) -> str`.
- Format, as exact copy:
  - `"<target_label>. Uno: <s1>. Dos: <s2>. … Listo."`, with `"¿Lo hago?"` instead of `"Listo."` in `announce_then_wait`.
  - Warnings are appended after it.
  - Ordinals are Spanish number words from uno to veinte.
  - `Ask` gives its question verbatim.
  - No target label: omit the label sentence.

- [ ] **Step 1: Write the failing test.**

```python
def test_reference_example_announcement():
    done = Done(steps=["seleccionar compás 5 tiempo 2 a compás 10", "copiar", "retrogradar", "subir un tono", "pegar en compás 15 tiempo 1"],
                target_label="Violin 1, voz 1", warnings=["Aviso: las ligaduras, dinámicas y articulaciones no se copiaron."], undo_steps=1)
    assert announce(done, "act_then_announce") == (
        "Violin 1, voz 1. Uno: seleccionar compás 5 tiempo 2 a compás 10. Dos: copiar. Tres: retrogradar. "
        "Cuatro: subir un tono. Cinco: pegar en compás 15 tiempo 1. Listo. "
        "Aviso: las ligaduras, dinámicas y articulaciones no se copiaron.")
```

  Plus `test_wait_mode_ends_with_question` and `test_ask_is_verbatim`.

- [ ] **Step 2: Run the tests.** `.venv\Scripts\python -m pytest tests/speech -v`
  - Expected: FAIL.
- [ ] **Step 3: Implement `announce`.**
- [ ] **Step 4: Run the tests again.** Same command.
  - Expected: PASS.
- [ ] **Step 5: Commit.** `git commit -m "feat(speech): step-by-step Spanish announcements"`

---

### Task 10: Preferences

**Files:**
- Create: `src/config/__init__.py`, `src/config/preferences.py`
- Test: `tests/config/test_preferences.py`

**Interfaces:**
- Produces:
  - `@dataclass class LLMConfig(provider: Literal["anthropic", "openai_compatible"], model: str, api_key: str, base_url: str | None)`.
  - NVIDIA = `openai_compatible` with `base_url="https://integrate.api.nvidia.com/v1"`.
  - `@dataclass class Preferences`, with these defaults:
    - `mode="act_then_announce"`, `llm=LLMConfig("anthropic", "claude-sonnet-5-5", "", None)`, `tts_rate=175`;
    - `input_device: str | None = None` and `input_channel=1` (1-based, the voice on Scarlett ch 1);
    - `output_device: str | None = None`;
    - `asr="faster-whisper"`, `asr_model="small"`;
    - `wake_word="salieri"`, `bridge_dir=<constant from Task 6>`.
  - `load_preferences(path: Path = default_path()) -> Preferences`: a missing file writes the defaults and returns them, and unknown keys are ignored. An invalid `mode`/`provider`, or `input_channel < 1`, raises `ValueError` with the field name.
  - `save_preferences(p, path)`.
  - `default_path() -> Path` = `%APPDATA%\SalierIA\preferences.json`.
  - Env override: if `ANTHROPIC_API_KEY` / `NVIDIA_API_KEY` is set and `api_key` is empty, use it.

- [ ] **Step 1: Write the failing tests.** Cover defaults-on-missing-file, round-trip, unknown keys ignored, `test_invalid_mode_rejected`, `test_env_key_fallback` (monkeypatch), and the NVIDIA preset base_url.
- [ ] **Step 2: Run the tests.** `.venv\Scripts\python -m pytest tests/config -v`
  - Expected: FAIL.
- [ ] **Step 3: Implement the preferences module.**
- [ ] **Step 4: Run the tests again.** Same command.
  - Expected: PASS.
- [ ] **Step 5: Commit.** `git commit -m "feat(config): preferences file with LLM, audio and mode settings"`

---

### Task 11: LLM providers and system prompt

**Files:**
- Create: `src/llm/__init__.py`, `src/llm/base.py`, `src/llm/anthropic_provider.py`, `src/llm/openai_compat_provider.py`, `src/llm/system_prompt.txt`
- Delete: `src/agent/` (the now-empty package plus the old `system_prompt.txt`)
- Test: `tests/llm/test_providers.py`

**Interfaces:**
- Consumes: Task 10 (`LLMConfig`) and `docs/tools.json` (Task 5).
- Produces:
  - `@dataclass class ToolCall(name: str, args: dict)`.
  - `@dataclass class LLMReply(tool_calls: list[ToolCall], text: str)`.
  - `class LLMProvider(Protocol): def complete(self, system: str, messages: list[dict], tools: list[dict]) -> LLMReply`.
  - `make_provider(cfg: LLMConfig) -> LLMProvider`.
  - The OpenAI-compatible provider converts Anthropic-format tools (`input_schema`) to `{"type": "function", "function": {name, description, parameters}}` and parses `tool_calls[].function.arguments` JSON. Invalid JSON gives `LLMReply([], text)` plus a logged warning.
- `system_prompt.txt` (Spanish) must state:
  - The coordinate system: bar + beat, where a beat is the denominator value and "último tiempo" means `"last"`.
  - Staff words map to `upper`/`lower`.
  - "un tono" is a major second and "medio tono"/"semitono" a minor second.
  - Always call tools, never chat.
  - Call `ask_user` when the instrument, staff or range is unclear.
  - `replace_last` for corrections ("no, era…"), `undo_last` for "deshaz eso", and `resolve_pending` when a question is pending.
  - The current score snapshot and session context arrive in the user message as JSON.

- [ ] **Step 1: Write the failing tests.** Mock `anthropic.Anthropic().messages.create` and `openai.OpenAI().chat.completions.create` with fakes.
  - `test_anthropic_reply_mapped`.
  - `test_openai_tools_converted` checks that the parameters equal `input_schema`.
  - `test_openai_bad_json_returns_no_calls`.
  - `test_make_provider_nvidia_uses_base_url`.
- [ ] **Step 2: Run the tests.** `.venv\Scripts\python -m pytest tests/llm -v`
  - Expected: FAIL.
- [ ] **Step 3: Implement the providers and write the system prompt.**
- [ ] **Step 4: Run the tests again.** Same command.
  - Expected: PASS.
- [ ] **Step 5: Commit.** `git commit -m "feat(llm): pluggable Claude / OpenAI-compatible (NVIDIA) providers"`

---

### Task 12: Session and assistant (text in → spoken text out)

**Files:**
- Create: `src/assistant.py`
- Test: `tests/test_assistant.py`

**Interfaces:**
- Consumes: Tasks 5, 8, 9, 10 and 11.
- Produces:
  - `class Assistant(provider: LLMProvider, executor: Executor, prefs: Preferences, tools: list[dict], system: str)` with `handle(transcript: str) -> str`, which returns the text to speak.
  - Session fields:
    - `last_target: Target | None`;
    - `history: list[CommandRecord(transcript, ops, undo_steps)]`;
    - `pending: Ask | None`;
    - `awaiting_confirm: list[Op] | None` (wait mode).
- Flow for `handle`:
  1. Refresh the snapshot.
  2. The user message is JSON `{command, score: {staves, bar_count, meters}, last_target, last_command, pending_question}`.
  3. Call `provider.complete`.
  4. Parse the tool calls.
  5. Dispatch:
     - `undo_last`: `client.undo(last.undo_steps)` and pop the record. If the history is empty, return `"No hay nada que deshacer."`.
     - `replace_last`: undo the last record, then execute the new calls.
     - `resolve_pending`: forward to the executor.
     - `ask_user`: speak the question.
     - In wait mode, run `describe`, store `awaiting_confirm` and speak it. `resolve_pending("confirm")` executes it.
     - Otherwise, run `execute`.
  6. Announce the result.
  - No tool calls: return `"No entendí la orden. ¿Puedes repetirla?"`.
  - `SibeliusTimeout`: `"Sibelius no respondió. Verifica que esté abierto y sin diálogos."`.
  - `SibeliusError`: `"Sibelius marcó un error: <message>."`.

- [ ] **Step 1: Write the failing tests.** Use `FakeProvider(scripted replies)` and the `FakeClient` from Task 8.
  - `test_reference_example_end_to_end`: the announcement equals the Task 9 string.
  - `test_undo_with_empty_history`: no Ctrl+Z is sent.
  - `test_undo_after_command_sends_recorded_steps`.
  - `test_correction_undoes_then_reexecutes`.
  - `test_wait_mode_describes_then_confirms`.
  - `test_fit_question_then_resolve`.
  - `test_timeout_message`.
- [ ] **Step 2: Run the tests.** `.venv\Scripts\python -m pytest tests/test_assistant.py -v`
  - Expected: FAIL.
- [ ] **Step 3: Implement `src/assistant.py`.**
- [ ] **Step 4: Run the tests again.** Same command.
  - Expected: PASS.
- [ ] **Step 5: Commit.** `git commit -m "feat: assistant session with undo, corrections, modes and questions"`

---

### Task 13: Audio input, wake word and endpointing

**Files:**
- Create: `src/voice/audio_input.py`, `src/voice/endpointer.py`, `src/voice/listener.py`
- Delete: `src/voice/capture.py`
- Test: `tests/voice/test_audio.py`

**Interfaces:**
- Consumes: Task 10 (`input_device`, `input_channel`, `wake_word`).
- Produces:
  - `list_input_devices() -> list[str]`.
  - `select_channel(block: np.ndarray, channel: int) -> np.ndarray` (1-based; out of range raises `ValueError`).
  - `to_16k(mono: np.ndarray, rate: int) -> np.ndarray` (int16; `scipy.signal.resample_poly`; the Scarlett is usually 48000).
  - `class Endpointer(frame_ms=30, silence_ms=800, max_ms=12000)` with `push(is_speech: bool) -> Literal["continue", "done"]`.
  - `class Listener(prefs, on_utterance: Callable[[bytes], None])` with `run()` (blocking) and `stop()`.
    - Vosk `KaldiRecognizer` on `vosk-model-small-es-0.42` with grammar `["salieri", "[unk]"]`. The model path is `%LOCALAPPDATA%\SalierIA\models\` and is downloaded on first run.
    - After the wake word, frames go to `webrtcvad` (aggressiveness 2) + `Endpointer`. When the endpointer returns done, it calls `on_utterance(pcm16)`.
    - Only the configured voice channel is read, so the piano on ch 3–4 never reaches it (spec §3.5).
  - Tray state: listening / hearing command / processing.

- [ ] **Step 1: Write the failing tests.**
  - `test_select_channel_1_based`.
  - `test_channel_out_of_range`.
  - `test_resample_48k_length`: 48000 samples → 16000.
  - `test_endpointer_done_after_silence`: 10 speech frames + 27 silence frames → done on the 27th.
  - `test_endpointer_max_length`.
- [ ] **Step 2: Run the tests.** `.venv\Scripts\python -m pytest tests/voice -v`
  - Expected: FAIL.
- [ ] **Step 3: Implement `audio_input.py`, `endpointer.py` and `listener.py`.**
- [ ] **Step 4: Run the tests again.** Same command.
  - Expected: PASS.
- [ ] **Step 5: Owner checks the wake word manually.** Run `python -m src.voice.listener --debug`, which prints the detections.
  - Expected: "Salieri" triggers 9/10 times, and 2 minutes of piano playing with no speech triggers 0 times.
- [ ] **Step 6: Commit.** `git commit -m "feat(voice): channel-selectable input, Vosk wake word, VAD endpointing"`

---

### Task 14: Transcription

**Files:**
- Modify: `src/voice/transcribe.py` (rewrite)
- Test: `tests/voice/test_transcribe.py`

**Interfaces:**
- Produces:
  - `class Transcriber(Protocol): def transcribe(self, pcm16: bytes) -> str`.
  - `FasterWhisperTranscriber(model_size: str)`: `WhisperModel(model_size, device="cpu", compute_type="int8")`, `language="es"`, `beam_size=1`, with an `initial_prompt` of musical vocabulary.
  - `clean_transcript(text: str, wake_word: str) -> str`: strips a leading wake word plus punctuation, matched case- and accent-insensitively.
  - `make_transcriber(prefs) -> Transcriber`. It accepts `asr="faster-whisper"`; anything else raises `ValueError`. NVIDIA cloud ASR is Task 17.

- [ ] **Step 1: Write the failing tests.** Cover `clean_transcript` with "Salieri, agrega dos compases", "salieri agrega…" and "Salieri. Deshaz eso", plus `test_unknown_asr_rejected`.
- [ ] **Step 2: Run the tests.** `.venv\Scripts\python -m pytest tests/voice/test_transcribe.py -v`
  - Expected: FAIL.
- [ ] **Step 3: Implement the transcription module.**
- [ ] **Step 4: Run the tests again.** Same command.
  - Expected: PASS.
- [ ] **Step 5: Owner measures latency.** Record 5 utterances of the §3.3 sentence and run `python -m tools.measure_asr --model small` and `--model base`.
  - Pick the default that keeps transcription ≤ 1.5 s on this CPU. Set it in the preferences defaults.
- [ ] **Step 6: Commit.** `git commit -m "feat(voice): faster-whisper CPU transcription"`

---

### Task 15: Speech output, tray, main wiring

**Files:**
- Create: `src/speech/tts.py`
- Modify: `src/ui/tray.py` (states plus menu items "Preferencias", which opens `preferences.json` in Notepad, and "Recargar preferencias")
- Modify: `src/main.py` (rewrite)
- Test: `tests/test_main_wiring.py`

**Interfaces:**
- Consumes: everything above.
- Produces:
  - `class Speaker(prefs)` with `say(text)`: pyttsx3 `save_to_file` to a temp WAV, then plays it with `sounddevice` on `prefs.output_device`, so the output device is selectable.
  - `build_app(prefs) -> App`, a factory used by `main` and by the test.
  - `main()`.
  - Log file: `%LOCALAPPDATA%\SalierIA\salieri.log`.

- [ ] **Step 1: Write the failing test.** `test_build_app_wires_components` monkeypatches Listener, Transcriber, Speaker and HotkeyTrigger with fakes, then asserts that an utterance callback produces `Speaker.say` with the assistant's text.
- [ ] **Step 2: Run the test.** `.venv\Scripts\python -m pytest tests/test_main_wiring.py -v`
  - Expected: FAIL.
- [ ] **Step 3: Implement `tts.py`, the tray changes and `main.py`.**
- [ ] **Step 4: Run the test again** together with the full suite: `.venv\Scripts\python -m pytest`.
  - Expected: all PASS.
- [ ] **Step 5: Commit.** `git commit -m "feat: wire wake word → ASR → assistant → Sibelius → speech"`

---

### Task 16: Command battery and model comparison

**Files:**
- Create: `tests/battery/commands.json`, `tools/run_battery.py`
- Test: `tests/battery/test_battery_file.py`

**Interfaces:**
- Consumes: Task 5 (`parse_tool_call`), Task 11 (`make_provider`), and the Task 4 fixture snapshot.
- Entry format: `{"id", "utterance", "expected": [{"name", "args"}]}`.
- Seed entries: one per §3.1 operation, plus:
  - the §3.3 sentence;
  - "piano compases 3 a 6 en corcheas" (expected: `ask_user`);
  - "deshaz eso";
  - "no, era el compás 16" after the §3.3 sentence;
  - "en el violín 1 compases 5 a 8 staccato".
  - Expected args use the exact schema of Task 5.
- `python -m tools.run_battery --provider anthropic|nvidia --model <id>` prints a pass/fail table and an overall percentage.
  - An entry passes when the parsed op equals the expected op, field by field.
  - It is a manual run and not part of pytest, because it needs the network.

- [ ] **Step 1: Write `test_battery_file.py`.** It checks that every entry's `expected` calls parse with `parse_tool_call` and that the ids are unique.
- [ ] **Step 2: Run it.** `.venv\Scripts\python -m pytest tests/battery -v`
  - Expected: FAIL before the file exists, PASS after.
- [ ] **Step 3: Write the battery file and the runner.**
- [ ] **Step 4: Run the battery against one model.** Run it once with Claude and once with one NVIDIA model, and record both percentages in `tests/battery/RESULTS.md`.
- [ ] **Step 5: Commit.** `git commit -m "test: command battery and provider comparison runner"`

---

### Task 17: Optional NVIDIA cloud ASR

Only do this task if Task 14's measured latency misses the target, or if the owner asks for it.

**Files:**
- Modify: `src/voice/transcribe.py`, `src/config/preferences.py` (`asr="nvidia"`, `asr_model`)
- Test: `tests/voice/test_transcribe.py`

- [ ] **Step 1: Write the failing test.** `test_make_transcriber_nvidia`: with a mocked client, `make_transcriber(prefs)` returns an `NvidiaTranscriber`, and `transcribe()` returns the mocked text.
- [ ] **Step 2: Implement `NvidiaTranscriber`** against NVIDIA's hosted Parakeet/Riva ASR API, using the key from preferences. Verify the current endpoint and client package in NVIDIA's docs at implementation time.
- [ ] **Step 3: Run the tests.** `.venv\Scripts\python -m pytest tests/voice -v`
  - Expected: PASS.
- [ ] **Step 4: Commit.** `git commit -m "feat(voice): optional NVIDIA cloud ASR"`

---

### Task 18: Acceptance session in Sibelius (manual, with the owner)

**Files:**
- Create: `../docs/superpowers/acceptance/2026-mvp-acceptance.md`

- [ ] **Step 1: Owner runs the session.** With `salieri_test.sib` open and hands on the piano, the owner runs every spoken command from the battery, the §3.3 example, "deshaz eso" after it, a correction, and one command in `announce_then_wait` mode.
- [ ] **Step 2: Record per command:**
  - whether it was right the first time (y/n);
  - the latency (stopwatch);
  - whether the undo removed the whole command;
  - whether it was faster than doing it by hand (the owner's judgement; this is spec §5).
- [ ] **Step 3: Check against the spec.** The MVP is accepted when every §3.1 operation passes and the §3.3 example is right first time. Every failing line becomes an issue.
- [ ] **Step 4: Commit.** `git commit -m "docs: MVP acceptance results"`

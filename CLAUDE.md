# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

SalierIA ("Salieri") is a Windows voice agent for Sibelius (music notation): hold F9, speak a Spanish command, and it gets turned into Sibelius edits. The README is only "Personal music assistant"; the real design lives in `SalierIA/docs/PRD_Sibelius_Voice_Agent.docx` and `SPEC_Sibelius_Voice_Agent.docx`.

The repo has a nested layout: the git root contains a single project folder, `SalierIA/`. **All code, commands and relative paths below are relative to that inner `SalierIA/` directory**, not the git root.

## Commands

Run everything from the inner `SalierIA/` directory. `main.py` loads `docs/tools.json` and `src/agent/system_prompt.txt` by cwd-relative path, so it breaks from any other directory.

```
pip install -r requirements.txt
python -m src.main                 # run the agent (needs the env vars below)
pytest                             # all tests
pytest tests/test_parser.py::test_name   # single test
```

There is no linter or build config. Required env (a `.env` is loaded via python-dotenv): `ANTHROPIC_API_KEY`, `SVA_BRIDGE_DIR`. Optional: `SVA_TTS_RATE` (default 175), `SVA_WHISPER_MODEL` (default `small`). Logs go to `%LOCALAPPDATA%\SiberiusVoiceAgent\salieri.log`.

## Architecture

Pipeline (orchestrated in `src/main.py`, class `SiberiusOrchestrator`):

voice capture (`src/voice/capture.py`, F9 hold via `keyboard`) → Whisper transcription (`src/voice/transcribe.py`) → rule-based `parse()` (`src/agent/parser.py`, Spanish solfège/durations/dynamics/ordinals → `Intent`) → Claude tool-use call (`src/agent/claude_agent.py`) → each returned `tool_use` block is sent to Sibelius through the IPC bridge → confirmation spoken with pyttsx3. A pystray tray icon (`src/ui/tray.py`) shows state.

Key points that span files:

- **Tool schema is the contract.** `docs/tools.json` defines the 18 tools given to Claude *and* the commands the Sibelius plugin must implement. `tests/test_tools.py` asserts the expected tool set. Adding or renaming a tool means updating `tools.json`, `VoiceAgentBridge.plg`, and the test's `EXPECTED_TOOLS`.
- **File-based IPC with Sibelius.** `src/bridge/ipc.py` writes `agent_cmd.json` (atomically via tmp+rename) into `SVA_BRIDGE_DIR`, then polls `agent_resp.json` for a matching `cmd_id` (8s timeout → `TimeoutError`; `status: error` → `IPCError`). The other side is `sibelius_plugin/VoiceAgentBridge.plg`, a ManuScript plugin that polls the same files on a 500ms timer and reads the same `SVA_BRIDGE_DIR` (falls back to `%TEMP%`). Changes to the JSON envelope must be made on both sides.
- **Context sent to Claude is one JSON user message** containing the transcript, the parser's `parsed_intent`, and `ScoreState`. `ScoreState` (`src/agent/score_state.py`) is a local mirror (current measure, key, time signature, last pitch/duration) updated optimistically from tool calls via `update_from_tool`, and from `get_score_info` results via `update_score_from_info`. There is no conversation history; each command is stateless apart from `ScoreState`.
- `export_score` may return `status: use_fallback`; the intended handler is `src/bridge/ui_fallback.py` (pywinauto UI automation of Sibelius menus), but `main.py` currently only logs that it is "not implemented in v1" and does not call it.
- Windows-only dependencies (`pywinauto`, `keyboard`, `pyttsx3` SAPI, AppData paths).

## Gotchas

- `docs/` and `files/` hold duplicate copies of the PRD, SPEC and `tools.json`. Code and tests read **`docs/tools.json`**; keep `files/tools.json` in sync or treat it as stale.
- The model is hardcoded in `SiberiusAgent.MODEL` (`claude_agent.py`), and user-facing speech strings are in Spanish.
- Naming is inconsistent across the codebase (`Siberius`/`Sibilius`/`Salieri`/`SalierIA`); classes like `SiberiusAgent` and `SibiliusUIFallback` are the real identifiers, so don't "fix" spellings in isolated places.
- `__pycache__/*.pyc` files are committed and there is no `.gitignore`.

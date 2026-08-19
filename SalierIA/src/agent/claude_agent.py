import json
from dataclasses import dataclass
from pathlib import Path

import anthropic

from .score_state import ScoreState


@dataclass
class AgentResult:
    tool_calls: list
    confirmation: str
    raw_response: object


class SiberiusAgent:
    MODEL = 'claude-sonnet-4-20250514'
    MAX_TOKENS = 1024

    def __init__(self, tools_path: str, prompt_path: str):
        self.client = anthropic.Anthropic()
        self.tools = json.loads(Path(tools_path).read_text(encoding='utf-8'))['tools']
        self.system = Path(prompt_path).read_text(encoding='utf-8')
        self.score_state = ScoreState()

    def process(self, transcript: str, intent) -> AgentResult:
        user_content = json.dumps(
            {
                'command': transcript,
                'parsed_intent': intent.__dict__,
                'score_state': self.score_state.to_dict(),
            },
            ensure_ascii=False,
        )

        response = self.client.messages.create(
            model=self.MODEL,
            max_tokens=self.MAX_TOKENS,
            system=self.system,
            tools=self.tools,
            messages=[{'role': 'user', 'content': user_content}],
        )

        tool_calls = [b for b in response.content if b.type == 'tool_use']
        text_blocks = [b for b in response.content if b.type == 'text']

        for block in tool_calls:
            self.score_state.update_from_tool(block.name, block.input)

        confirmation = text_blocks[0].text if text_blocks else ''
        return AgentResult(tool_calls=tool_calls, confirmation=confirmation, raw_response=response)

    def update_score_from_info(self, info: dict):
        if 'total_measures' in info:
            self.score_state.total_measures = info['total_measures']
        if 'key' in info:
            self.score_state.key = info['key']
        if 'time_num' in info:
            self.score_state.time_num = info['time_num']
        if 'time_den' in info:
            self.score_state.time_den = info['time_den']
        if 'instrument_count' in info:
            self.score_state.instrument_count = info['instrument_count']

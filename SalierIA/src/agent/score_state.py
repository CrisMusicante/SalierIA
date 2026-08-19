from dataclasses import dataclass


@dataclass
class ScoreState:
    current_measure: int = 1
    total_measures: int = 0
    key: str = 'C'
    time_num: int = 4
    time_den: int = 4
    last_pitch: str = 'C4'
    last_duration: str = 'quarter'
    instrument_count: int = 1

    def advance_measure(self):
        if self.total_measures > 0:
            self.current_measure = min(self.current_measure + 1, self.total_measures)
        else:
            self.current_measure += 1

    def to_dict(self) -> dict:
        return self.__dict__.copy()

    def update_from_tool(self, tool_name: str, params: dict):
        if tool_name == 'add_note':
            if 'pitch' in params:
                self.last_pitch = params['pitch']
            if 'duration' in params:
                self.last_duration = params['duration']
            if 'measure' in params:
                self.current_measure = params['measure']
        elif tool_name == 'set_key_signature':
            if 'key' in params:
                self.key = params['key']
        elif tool_name == 'set_time_signature':
            if 'numerator' in params:
                self.time_num = params['numerator']
            if 'denominator' in params:
                self.time_den = params['denominator']
        elif tool_name == 'add_measures':
            if 'count' in params:
                self.total_measures += params['count']

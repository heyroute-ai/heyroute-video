from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from typing import Any, TextIO


@dataclass
class EventSink:
    json_events: bool = False
    stream: TextIO = sys.stdout

    def emit(self, event: str, **data: Any) -> None:
        payload = {"event": event, **data}
        if self.json_events:
            self.stream.write(json.dumps(payload, ensure_ascii=False) + "\n")
            self.stream.flush()
        else:
            message = data.get("message") or data.get("artifact") or ""
            print(f"[{event}] {message}", file=sys.stderr)

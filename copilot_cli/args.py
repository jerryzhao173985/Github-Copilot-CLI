from __future__ import annotations
from dataclasses import dataclass
from typing import Optional


@dataclass
class Args:
    path: str
    prompt: Optional[str]
    model: str
    system_prompt: str
    action: Optional[str]
    no_stream: bool
    no_spinner: bool
    copy_to_clipboard: bool
    list: bool

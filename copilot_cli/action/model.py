# Postpone evaluation of annotations for Python <3.10
# Postpone evaluation of annotations for Python <3.10
from __future__ import annotations
from typing import Optional

from pydantic import BaseModel, Field
# *typing_extensions* might be absent in minimal environments. Fallback to the
# built-in *typing* module which provides *Callable* since Python 3.5.

try:
    from typing_extensions import Callable  # type: ignore
except ModuleNotFoundError:  # pragma: no cover – runtime fallback
    from typing import Callable  # type: ignore

from ..args import Args


class Output(BaseModel):
    to_stdout: bool = Field(default=True)
    to_file: Optional[str] = None


class Options(BaseModel):
    stream: bool = Field(default=True)
    spinner: bool = Field(default=True)


class Action(BaseModel):
    description: str
    prompt: str
    system_prompt: str
    model: str
    commands: Optional[dict[str, list[str]]] = None
    on_complete: Optional[Callable[[str, Args], None]] = None
    output: Output = Field(default_factory=Output)
    options: Options = Field(default_factory=Options)

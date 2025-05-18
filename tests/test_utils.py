import pytest
from typing import Optional

from copilot_cli.utils import should_enable_spinner
from copilot_cli.args import Args


class DummyOptions:
    def __init__(self, spinner: Optional[bool]):
        self.spinner = spinner


class DummyAction:
    def __init__(self, spinner: Optional[bool] = None):
        self.options = DummyOptions(spinner) if spinner is not None else None


@pytest.mark.parametrize(
    ("no_spinner_flag", "action_obj", "expected"),
    [
        (True, None, True),
        (False, None, False),
        (True, DummyAction(spinner=False), False),
        (True, DummyAction(spinner=True), True),
        (True, DummyAction(spinner=None), True),
        (False, DummyAction(spinner=False), False),
        (False, DummyAction(spinner=True), False),
        (False, DummyAction(spinner=None), False),
    ],
)
def test_should_enable_spinner(no_spinner_flag, action_obj, expected):
    args = Args(
        path="",
        prompt=None,
        model="",
        system_prompt="",
        action=None,
        no_stream=False,
        no_spinner=no_spinner_flag,
        copy_to_clipboard=False,
        list=False,
    )
    assert should_enable_spinner(args, action_obj) == expected
"""Utility helper functions for *copilot_cli*.

This module collects small, self-contained helpers that do not warrant their
own top-level package but are used by different parts of the code base.  The
goal is to

*   keep the public surface of the main modules (*copilot.py*, *args.py*, …)
    focused on their primary responsibilities and
*   avoid code duplication by providing a single source of truth for common
    logic.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover – import heavy modules lazily at runtime
    from .action.model import Action
    from .args import Args


def should_enable_spinner(cli_args: "Args", action_obj: "Action | None") -> bool:  # noqa: D401
    """Determine whether the animated spinner should be active.

    The decision is influenced by **two** independent configuration layers:

    1. A *global* command-line switch – the presence of ``--no-spinner``
       disables the spinner unconditionally.
    2. An *action-local* preference set in *actions.yml* which allows the
       author of pre-defined actions to opt-out of the spinner for an
       individual workflow (e.g. when the output is streamed).

    Both layers **must** allow the spinner for it to be active.  The helper is
    therefore effectively the logical *AND* of the two flags.

    Args:
        cli_args: Parsed command-line arguments.
        action_obj: The currently executed *Action* – may be *None* when the
            user did not choose an action via ``--action``.

    Returns:
        ``True`` if the spinner should be displayed, ``False`` otherwise.
    """

    # ---------------------------------------------------------------------
    # Global CLI flag (store_false) – *True* means spinner allowed
    # ---------------------------------------------------------------------
    spinner_allowed_globally = bool(cli_args.no_spinner)

    # ---------------------------------------------------------------------
    # Per-action configuration – default to *True* when absent so that legacy
    # actions without an explicit *spinner* key keep their original behaviour.
    # ---------------------------------------------------------------------
    if action_obj is not None:
        try:
            action_pref = (
                action_obj.options.spinner  # type: ignore[attr-defined]
                if action_obj.options is not None
                else True
            )
        except AttributeError:
            # *options* may be a raw dict when the light-weight *pydantic* stub
            # is active – handle that gracefully.
            options_dict = getattr(action_obj, "options", {}) or {}
            action_pref = bool(options_dict.get("spinner", True))
    else:
        action_pref = True

    return spinner_allowed_globally and action_pref

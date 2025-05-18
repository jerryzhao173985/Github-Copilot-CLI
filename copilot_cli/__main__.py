"""Module execution entry point for ``python -m copilot_cli``.

This thin wrapper simply forwards the execution to the *stand-alone* CLI
implementation that lives in the project root directory (``copilot-cli.py``).

Keeping the actual logic in a single place avoids code duplication while still
supporting both invocation styles:

1. ``python copilot-cli.py --prompt "hello"`` (direct script execution)
2. ``python -m copilot_cli --prompt "hello"`` (module execution)

The former is convenient when cloning the repository, whereas the latter is
required when the package is installed into a virtual environment or when a
test-runner launches the CLI via the *-m* switch.
"""

from __future__ import annotations

import runpy
from pathlib import Path
import sys


def _run_cli() -> None:  # noqa: D401
    """Locate *copilot-cli.py* and execute it with the current argv."""

    script_path = (Path(__file__).resolve().parent.parent / "copilot-cli.py")

    if not script_path.exists():
        print("Error: copilot-cli.py not found next to the package directory.", file=sys.stderr)
        sys.exit(1)

    # *run_path* executes the target file in a fresh global namespace while
    # reusing the current ``sys.argv`` – this mimics the behaviour of running
    # the script directly.
    sys.path.insert(0, str(script_path.parent))  # Make sure relative imports work as in direct execution
    runpy.run_path(str(script_path), run_name="__main__")


if __name__ == "__main__":  # pragma: no cover – module execution guard
    _run_cli()

"""Action manager handling pre-defined CLI actions.

This module tries to use *PyYAML* for parsing the YAML configuration file. If
*PyYAML* is not available (for instance in restricted execution environments),
it falls back to a dummy implementation that treats the file as empty and
therefore disables the action subsystem.  All other CLI functionality (e.g.
simple prompt forwarding) keeps working without external dependencies.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

# Optional dependency ---------------------------------------------------------
try:
    import yaml  # type: ignore

    def _safe_load_yaml(text: str) -> Dict[str, Any]:  # noqa: D401
        return yaml.safe_load(text)  # type: ignore[arg-type]

except ModuleNotFoundError:  # pragma: no cover – runtime fallback

    def _safe_load_yaml(_text: str) -> Dict[str, Any]:  # noqa: D401
        # Minimal YAML fallback: return an empty mapping so the rest of the CLI
        # can still operate without predefined actions.
        # Very simple YAML subset parser supporting the limited features used
        # inside *actions.yml*: top-level mapping, nested mappings and
        # multi-line scalar / list values introduced with a dash.

        def _strip_quotes(val: str) -> str:
            if (val.startswith("\"") and val.endswith("\"")) or (
                val.startswith("'") and val.endswith("'")
            ):
                return val[1:-1]
            return val

        root: Dict[str, Any] = {}

        # Each entry on the stack keeps: (indent_level, container)
        # container is either a *dict* or *list* that is currently being
        # populated.  The parent container is always the previous element in
        # the stack.
        stack: list[tuple[int, Dict[str, Any] | list[Any]]] = [(-1, root)]

        for raw_line in _text.splitlines():
            # ----------------------------------------------------------------
            # Pre-processing – ignore blanks and comments
            # ----------------------------------------------------------------
            if not raw_line.strip() or raw_line.lstrip().startswith("#"):
                continue

            indent = len(raw_line) - len(raw_line.lstrip())
            line = raw_line.lstrip()

            # Pop the stack until we find the parent container for the current
            # indentation level.
            while stack and indent <= stack[-1][0]:
                stack.pop()

            parent = stack[-1][1]

            # ----------------------------------------------------------------
            # YAML list item ("- value")
            # ----------------------------------------------------------------
            if line.startswith("- "):
                value = _strip_quotes(line[2:].strip())

                # If the parent container is a mapping, it means that we
                # previously encountered a key with an empty value ("key:") and
                # now realize that the value should actually be a list.  We
                # therefore replace the placeholder mapping with a proper
                # list.
                if isinstance(parent, dict):
                    # Locate the key in the grand-parent mapping whose value is
                    # this *parent* mapping.
                    for gp_key, gp_val in stack[-2][1].items():  # type: ignore[index]
                        if gp_val is parent:
                            new_list: list[Any] = []
                            stack[-2][1][gp_key] = new_list  # type: ignore[index]
                            stack[-1] = (stack[-1][0], new_list)
                            parent = new_list
                            break

                # Guarantee that *parent* is now a list.
                if isinstance(parent, list):
                    parent.append(value)
                continue

            # ----------------------------------------------------------------
            # YAML mapping entry ("key: value")
            # ----------------------------------------------------------------
            if ":" in line:
                key, rest = line.split(":", 1)
                key = key.strip()
                value_part = rest.strip()

                if value_part == "":
                    # The mapping value spans multiple subsequent lines – we
                    # insert a placeholder dict which may later be converted to
                    # a list when we encounter list items.
                    new_container: Dict[str, Any] = {}

                    if isinstance(parent, dict):
                        parent[key] = new_container
                    elif isinstance(parent, list):
                        parent.append({key: new_container})

                    # Push the new container onto the stack.
                    stack.append((indent, new_container))
                else:
                    scalar_val = _strip_quotes(value_part)
                    if isinstance(parent, dict):
                        parent[key] = scalar_val
                    elif isinstance(parent, list):
                        parent.append({key: scalar_val})

        return root


from pydantic import BaseModel

from .model import Action


class ActionsYAML(BaseModel):
    actions: dict[str, Action]


class ActionManager:
    def __init__(self, config_path: str):
        self._actions = self.load_actions(config_path)

    def load_actions(self, config_path: str) -> dict[str, Action]:  # noqa: D401
        """Load actions from a YAML file.

        The file is parsed via *PyYAML* when available.  Otherwise, an empty
        mapping is returned which effectively disables the *Action* feature
        while still allowing the rest of the CLI to function.
        """

        cfg_path = Path(config_path)
        if not cfg_path.exists():
            return {}

        try:
            actions_raw = _safe_load_yaml(cfg_path.read_text())
            if not actions_raw or "actions" not in actions_raw:
                return {}

            actions_section = actions_raw["actions"]
            actions: dict[str, Action] = {}
            for name, conf in actions_section.items():
                if isinstance(conf, dict):
                    try:
                        actions[name] = Action(**conf)  # type: ignore[arg-type]
                    except Exception:
                        # Skip invalid entries – maintain robustness.
                        pass

            return actions
        except Exception:
            # Any issue during parsing – fall back to empty mapping to keep
            # the CLI working without actions.
            return {}

    def get_action(self, action: str) -> Action:
        """
        Get an action by name.

        Args:
            action: The name of the action.

        Returns:
            Action: The action object.
        """
        if action not in self._actions:
            raise ValueError(f"Invalid action: {action}")

        return self._actions[action]

    def get_actions_list(self) -> list[str]:
        """
        Get a list of all available actions.

        Returns:
            list: A list of action names.
        """
        return list(self._actions.keys())

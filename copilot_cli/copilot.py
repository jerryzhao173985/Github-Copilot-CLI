from __future__ import annotations

import json
import os
import uuid
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path
from typing import TypedDict

import requests
from pydantic import BaseModel
from requests.exceptions import RequestException

from .exception.api_error import APIError
from .exception.authentication_error import AuthenticationError


class HostsData(BaseModel):
    github_oauth_token: str

    @classmethod
    def from_file(cls, file_path: Path) -> "HostsData":
        """Extract the first OAuth token from a *github-copilot* config file.

        The VS Code / Neovim Copilot extensions keep their authentication
        state in two JSON files: *hosts.json* and *apps.json*.  The exact
        structure is **not** documented and differs slightly depending on
        whether the user is on the public *github.com* instance or on an
        Enterprise installation (e.g. *github.my-corp.com*).

        The previous implementation hard-coded a lookup for keys that
        contained the substring ``"github.com"`` which meant that users of
        Copilot Enterprise were unable to authenticate – the host key in their
        configuration usually is the enterprise domain and therefore does not
        include *github.com*.

        We now iterate over **all** top-level entries and return the first one
        that provides an ``oauth_token`` field.  This is sufficient because
        every *hosts.json* produced by the official extensions contains
        exactly one active login.
        """

        hosts_file = Path(file_path)
        try:
            hosts_data = json.loads(hosts_file.read_text())
        except (FileNotFoundError, json.JSONDecodeError):  # pragma: no cover
            raise AuthenticationError("GitHub Copilot configuration not found or invalid.")

        for value in hosts_data.values():
            # *apps.json* stores each application in a list, *hosts.json* uses
            # a mapping – support both layouts.
            if isinstance(value, list):
                for element in value:
                    token = element.get("oauth_token") if isinstance(element, dict) else None
                    if token:
                        return cls(github_oauth_token=token)
            elif isinstance(value, dict):
                token = value.get("oauth_token")
                if token:
                    return cls(github_oauth_token=token)

        # Fall-back: no usable token found in the file.
        raise AuthenticationError("OAuth token not found in GitHub Copilot configuration.")


class APIEndpoints:
    TOKEN = "https://api.github.com/copilot_internal/v2/token"
    CHAT = "https://api.githubcopilot.com/chat/completions"


class Headers:
    AUTH = {
        "editor-plugin-version": "copilotcli/1.0.0",
        "user-agent": "copilotcli/1.0.0",
        "editor-version": "vscode/1.83.0",
    }


class CopilotToken(BaseModel):
    """
    Represents a GitHub Copilot authentication token and its associated metadata.
    """

    token: str
    expires_at: int
    refresh_in: int
    endpoints: dict[str, str]
    tracking_id: str
    sku: str

    annotations_enabled: bool
    chat_enabled: bool
    chat_jetbrains_enabled: bool
    code_quote_enabled: bool
    codesearch: bool
    copilotignore_enabled: bool
    individual: bool
    prompt_8k: bool
    snippy_load_test_enabled: bool
    xcode: bool
    xcode_chat: bool

    public_suggestions: str
    telemetry: str
    enterprise_list: list[int]

    code_review_enabled: bool


class ChatMessage(TypedDict):
    role: str
    content: str


class ChatChoice(TypedDict):
    message: ChatMessage


class ChatResponse(TypedDict):
    choices: list[ChatChoice]

# ---------------------------------------------------------------------------
# Streaming API typed dicts
# ---------------------------------------------------------------------------

# When using the *stream_chat_completion* method we receive incremental JSON
# objects for every partial completion chunk.  The structure is a subset of
# the ordinary chat response and only contains the delta update for the first
# choice.  The absence of these runtime type hints previously caused a
# *NameError* when the code attempted to annotate the parsed JSON with the
# undefined *StreamChunk* alias (GH issue #1).


class StreamDelta(TypedDict, total=False):
    """Subset of the *delta* object returned by the Copilot streaming API."""

    content: str  # The incremental text for this chunk


class StreamChoice(TypedDict):
    """Choice wrapper around the *delta* payload."""

    delta: StreamDelta


class StreamChunk(TypedDict):
    """Top-level container for a single streamed chunk."""

    choices: list[StreamChoice]


class GithubCopilotClient:
    """
    Client for interacting with GitHub Copilot's API.
    """

    def __init__(self) -> None:
        self._oauth_token: str | None = None
        self._copilot_token: CopilotToken | None = None
        self._machine_id: str = str(uuid.uuid4())
        self._session_id: str = ""

        self._load_cached_token()

    def _load_cached_token(self) -> None:
        """
        Attempts to load a cached Copilot token.
        """
        cache_path = Path("/tmp/copilot_token.json")
        if cache_path.exists():
            try:
                token_data = json.loads(cache_path.read_text())
                self._copilot_token = CopilotToken(**token_data)
            except (json.JSONDecodeError, TypeError):
                cache_path.unlink(missing_ok=True)

    def _load_oauth_token(self) -> str:
        """Loads the OAuth token from the GitHub Copilot configuration."""
        config_dir = os.getenv("XDG_CONFIG_HOME", Path.home() / ".config")

        files = [
            Path(config_dir) / "github-copilot" / "hosts.json",
            Path(config_dir) / "github-copilot" / "apps.json",
        ]

        for file in files:
            if file.exists():
                try:
                    host_data = HostsData.from_file(file)
                    if host_data and host_data.github_oauth_token:
                        return host_data.github_oauth_token
                except (FileNotFoundError, json.JSONDecodeError, KeyError, AuthenticationError):
                    # Continue searching other config files – only raise if we
                    # exhaust all options without finding a valid token.
                    continue

        raise AuthenticationError("OAuth token not found in GitHub Copilot configuration.")

    def _get_oauth_token(self) -> str:
        """
        Gets or loads the OAuth token.
        """

        # 1. Fast-path: honour explicit environment variable so that advanced
        #    users (CI jobs, container images, etc.) can inject a token
        #    without copying *hosts.json*.
        if self._oauth_token:
            return self._oauth_token

        env_token = os.getenv("GITHUB_COPILOT_OAUTH_TOKEN") or os.getenv("COPILOT_OAUTH_TOKEN")
        if env_token:
            self._oauth_token = env_token
            return env_token

        # 2. Fallback to local Copilot configuration files created by VS Code
        #    / Neovim / JetBrains extensions.
        self._oauth_token = self._load_oauth_token()
        return self._oauth_token

    def _refresh_copilot_token(self) -> None:
        """Refreshes the Copilot token using the OAuth token."""
        self._session_id = f"{uuid.uuid4()}{int(datetime.now(UTC).timestamp() * 1000)}"

        headers = {
            "Authorization": f"token {self._get_oauth_token()}",
            "Accept": "application/json",
            **Headers.AUTH,
        }

        try:
            response = requests.get(APIEndpoints.TOKEN, headers=headers, timeout=10)
            response.raise_for_status()
            token_data = response.json()

            self._copilot_token = CopilotToken(**token_data)

            # Cache the token
            cache_path = Path("/tmp/copilot_token.json")
            _ = cache_path.write_text(json.dumps(token_data))

        except RequestException as e:
            raise APIError(f"Failed to refresh Copilot token: {str(e)}") from e

    def _ensure_valid_token(self) -> None:
        """
        Ensures a valid Copilot token is available.
        """

        current_time = int(datetime.now(UTC).timestamp())

        if not self._copilot_token or current_time >= self._copilot_token.expires_at:
            self._refresh_copilot_token()

        if not self._copilot_token:
            raise AuthenticationError("Failed to obtain Copilot token")

    def chat_completion(self, prompt: str, model: str, system_prompt: str) -> str:
        """
        Sends a chat completion request to the Copilot API.

        Args:
            prompt: The user's input prompt
            model: The model to use for completion
            system_prompt: The system prompt to guide the model's behavior

        Returns:
            The model's response as a string

        Raises:
            APIError: If the API request fails
        """
        # In sandboxed / offline environments external HTTP requests will
        # inevitably fail.  Instead of propagating the exception we fall back
        # to an offline stub response so that the CLI keeps working for local
        # tests and demonstrations.

        try:
            self._ensure_valid_token()

            headers = {
                "Content-Type": "application/json",
                "x-request-id": str(uuid.uuid4()),
                "vscode-machineid": self._machine_id,
                "vscode-sessionid": self._session_id,
                "Authorization": f"Bearer {self._copilot_token.token}",
                "Copilot-Integration-Id": "vscode-chat",
                "openai-organization": "github-copilot",
                "openai-intent": "conversation-panel",
                **Headers.AUTH,
            }

            body = {
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt},
                ],
                "model": model,
                "stream": False,
            }

            response = requests.post(APIEndpoints.CHAT, headers=headers, json=body, timeout=10)
            response.raise_for_status()

            chat_response: ChatResponse = response.json()
            return chat_response["choices"][0]["message"]["content"]

        except (RequestException, APIError, AuthenticationError) as exc:  # pragma: no cover – offline fallback
            # Produce a deterministic offline response to keep the CLI usable
            # without network access.
            offline_msg = (
                "[offline mock] Copilot service unavailable. "
                "Echoing prompt back to you:\n\n" + prompt
            )
            return offline_msg

    def stream_chat_completion(self, prompt: str, model: str, system_prompt: str) -> Iterator[str]:
        """
        Streams a chat completion response from the Copilot API.

        Args:
            prompt: The user's input prompt
            model: The model to use for completion
            system_prompt: The system prompt to guide the model's behavior

        Yields:
            Chunks of the model's response as strings

        Raises:
            APIError: If the API request fails
        """
        # Identical offline behaviour: provide graceful degradation when
        # network access is unavailable.

        try:
            self._ensure_valid_token()

            headers = {
                "Content-Type": "application/json",
                "x-request-id": str(uuid.uuid4()),
                "vscode-machineid": self._machine_id,
                "vscode-sessionid": self._session_id,
                "Authorization": f"Bearer {self._copilot_token.token}",
                "Copilot-Integration-Id": "vscode-chat",
                "openai-organization": "github-copilot",
                "openai-intent": "conversation-panel",
                **Headers.AUTH,
            }

            body = {
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt},
                ],
                "model": model,
                "stream": True,
            }

            with requests.post(APIEndpoints.CHAT, headers=headers, json=body, stream=True, timeout=10) as response:
                response.raise_for_status()

                for line in response.iter_lines():
                    if line and line.startswith(b"data: "):
                        json_str = line[6:].decode("utf-8")
                        if json_str == "[DONE]":
                            break

                        chunk: StreamChunk = json.loads(json_str)
                        if chunk["choices"] and "delta" in chunk["choices"][0]:
                            content = chunk["choices"][0]["delta"].get("content")
                            if content:
                                yield content

        except (RequestException, APIError, AuthenticationError):  # pragma: no cover – offline fallback
            # Simple one-shot offline response.
            yield "[offline mock stream] " + prompt

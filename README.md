# 🚀 Copilot CLI

[![CI](https://github.com/jerryzhao173985/Github-Copilot-CLI/actions/workflows/ci.yml/badge.svg)](https://github.com/jerryzhao173985/Github-Copilot-CLI/actions/workflows/ci.yml)

**Copilot CLI** is a standalone command-line interface that brings GitHub Copilot’s chat and action capabilities directly to your terminal. It enables conversational AI-driven code assistance, predefined workflows (actions), and flexible customization, all with first-class offline fallbacks and minimal external dependencies.

## Table of Contents

- [Features](#features)
- [Architecture](#architecture)
- [Installation](#installation)
- [Authentication](#authentication)
- [Usage](#usage)
  - [Global Options](#global-options)
  - [Examples](#examples)
- [Actions](#actions)
- [Configuration (`actions.yml`)](#configuration-actionsyml)
- [Project Structure](#project-structure)
- [Implementation Details](#implementation-details)
- [Development](#development)
- [Contributing](#contributing)
- [Acknowledgements](#acknowledgements)

## Features

- **Interactive Chat**: Send prompts to GitHub Copilot or other supported models (`gpt-4o`, Gemini, etc.) and receive single-shot or streaming responses.
- **Predefined Actions**: Invoke curated workflows (e.g., generate `.gitignore`, conventional commit messages, translations, text enhancements, shell commands) via `--action` and customize with `actions.yml`.
- **Configurable Prompts**: Control both user and system prompts (`--prompt`, `--system-prompt`) to guide AI behavior.
- **Streaming & Spinner UX**: Real-time markdown rendering with Rich, or animated spinner feedback when streaming is disabled.
- **Offline Fallbacks**: Graceful degradation in sandboxed or offline environments (HTTP stubs echo your prompt) to keep the CLI always responsive.
- **Minimal Dependencies**: Runtime stubs for Pydantic, YAML, Rich, Pyperclip, Halo, and typing_extensions ensure core functionality works even if optional packages are missing.
- **Clipboard Integration**: Copy AI responses directly to the clipboard with `--copy-to-clipboard`.
- **Wrapper & Module Modes**: Call via the thin `copilot` script, `python copilot-cli.py`, or Python module (`python -m copilot_cli`).

## Architecture

**High-level execution pipeline:**

```text
┌────────────────┐   parse      ┌──────────────────┐  hydrate  ┌───────────────────┐
│  CLI (argparse)│────────────►│  Args dataclass   │──────────►│  Action Manager   │
└────────────────┘              └──────────────────┘           └───────────────────┘
        │                               │                           │
        │                               │ fetch action              │
        ▼                               ▼                           ▼
┌────────────────────┐   prompt   ┌──────────────────┐  HTTP/stream  ┌───────────────────┐
│ process_action_cmd │──────────►│ GithubCopilot    │──────────────►│ MarkdownStreamer │
└────────────────────┘            │      Client      │               └───────────────────┘
        │                           │                               ▲
        │ spinner / write-file      │                               │
        └──────────────────────────►└───────────────────────────────┘
```

1. **Argument parsing**: `create_parser()` → `Args` dataclass  
2. **Action resolution**: load & validate workflows from `actions.yml` via `ActionManager`  
3. **Prompt preprocessing**: execute in-flight shell commands, interpolate placeholders (`$path`, `$diff`, etc.)  
4. **Copilot request**: authenticate (OAuth & Copilot tokens), send chat or streaming API calls  
5. **Result handling**: render with `MarkdownStreamer` or spinner & write to stdout/file  

## Installation

### Prerequisites
- **Python**: 3.9 or newer (tested on 3.11)  
- **GitHub Copilot Authentication**: A valid OAuth token from the GitHub Copilot extension or via environment variable.

### Clone & Setup
```sh
# Clone this repository (adjust owner/URL as needed)
git clone https://github.com/rachartier/copilot-cli.git
cd copilot-cli

# Install Python dependencies
pip install --upgrade pip
pip install -r requirements.txt
```

### (Optional) Wrapper Installation
```sh
# Make the thin wrapper executable and add to PATH
chmod +x copilot
mv copilot /usr/local/bin/

# Now invoke with the short command:
copilot --prompt "Explain recursion in Python"
```

### (Optional) Standalone Binary
Use PyInstaller to build a single-file executable (see `.github/workflows/main.yml`):
```sh
pyinstaller --onefile copilot-cli.py --add-data ./actions.yml:.
# Move the resulting binary in `dist/` into your PATH.
```

## Authentication

Copilot CLI locates your GitHub Copilot OAuth token from:
- `$GITHUB_COPILOT_OAUTH_TOKEN` or `$COPILOT_OAUTH_TOKEN` for Copilot-specific tokens; `$GITHUB_TOKEN` or `$GH_TOKEN` for personal GitHub.com tokens  
- Local Copilot extension config (`hosts.json`/`apps.json`):
  - Linux/XDG: `~/.config/github-copilot/{hosts,apps}.json`
  - VS Code globalStorage Copilot extension state:
    - Linux: `~/.config/Code/User/globalStorage/github.copilot/{hosts,apps}.json`
    - macOS: `~/Library/Application Support/Code/User/globalStorage/github.copilot/{hosts,apps}.json`
    - Windows: `%APPDATA%/Code/User/globalStorage/github.copilot/{hosts,apps}.json`

Set one of the above if you are not using an IDE plugin.

When multiple Copilot configurations are detected (e.g. personal GitHub.com and an Enterprise host),
the CLI prefers the personal GitHub.com token by default. To force an Enterprise or other token,
set one of the environment variables explicitly (e.g. `$GITHUB_COPILOT_OAUTH_TOKEN`, `$COPILOT_OAUTH_TOKEN`,
`$GITHUB_TOKEN`, or `$GH_TOKEN`).

By default, Copilot CLI uses the public GitHub Cloud endpoints. To work with
GitHub Copilot Enterprise or a custom Copilot deployment, override the token
and chat endpoints and the organization header via environment variables:

```bash
export GITHUB_COPILOT_TOKEN_URL="https://github.mycompany.com/copilot_internal/v2/token"
export GITHUB_COPILOT_CHAT_URL="https://github.mycompany.com/chat/completions"
export GITHUB_COPILOT_ORGANIZATION="mycompany"
```

## Usage

Run the CLI via script, module, or wrapper—options are identical:

| Invocation                  | Notes                                          |
|-----------------------------|------------------------------------------------|
| `python copilot-cli.py`     | Direct script (requires editable checkout)     |
| `python -m copilot_cli`     | Module mode (works after `pip install .`)      |
| `copilot`                   | Thin wrapper (after installing `copilot` file) |

### Global Options
| Option                   | Description                                                                                  |
|--------------------------|----------------------------------------------------------------------------------------------|
| `--prompt <text>`        | User prompt (question, command, or free-form)                                                |
| `--system-prompt <text>` | Override the AI system prompt guide (defaults to GitHub Copilot assistant prompt)            |
| `--model <name>`         | Model identifier (e.g. `gpt-4o`, `o3-mini`, `gemini-2.0-flash-001`)                          |
| `--action <name>`        | Predefined action (see [Actions](#actions))                                                  |
| `--path <dir>`           | Working directory for action commands (default `.`)                                          |
| `--no-stream`            | Disable API streaming; fetch full response in one shot                                       |
| `--no-spinner`           | Disable the animated spinner                                                                 |
| `--copy-to-clipboard`    | Copy final response to the system clipboard                                                  |
| `--list`                 | List all available actions and exit                                                          |

### Examples
```sh
# Simple chat prompt
copilot --prompt "Explain Python decorators"

# Specify a model and system prompt
copilot --model "gemini-2.0-flash-001" \
        --system-prompt "You are a helpful AI assistant." \
        --prompt "Summarize this repository structure."

# Run an action to generate a .gitignore
copilot --action gitignore --prompt "Python project" --path ~/myapp

# List all predefined actions
copilot --list
```

## Actions

Built-in workflows are defined in `actions.yml`. List them with:

```sh
copilot --list
```

Example output:
```
Available actions:
  - gitignore: Generate a .gitignore file
  - lazygit-conventional-commit: Generate a commit message with Conventional Commit format
  - translate: Translate text to a specified language
  - enhance: Improve wording of a given text
  - correct: Correct spelling and grammar
  - generate-command: POSIX shell command assistant
  - ask: Answer an arbitrary user question
```

Each action includes:
- **description**: human-readable summary  
- **system_prompt & prompt**: AI instruction templates  
- **model**: default model name  
- **commands**: optional shell commands whose output is inlined  
- **options**: `stream`/`spinner` toggles  
- **output**: `to_stdout`/`to_file` directives  

Edit `actions.yml` to add or customize actions; see [Configuration](#configuration-actionsyml).

## Configuration (`actions.yml`)

Define custom workflows by editing `actions.yml`. Actions follow this schema:

```yaml
actions:
  <name>:
    description: "Short description"
    system_prompt: |
      # System prompt template...
    prompt: "<base user prompt>"
    model: "<model-name>"
    commands:
      key: ["shell", "commands", "--flags"]
    options:
      stream: true
      spinner: false
    output:
      to_stdout: true
      to_file: "$path/<output-file>"
```

Refer to the existing entries in `actions.yml` for examples.

## Project Structure

```
├── actions.yml           # Predefined action definitions
├── copilot-cli.py        # Main CLI entry point with optional dependency stubs
├── copilot               # Thin wrapper for `python -m copilot_cli`
├── requirements.txt      # Python dependencies
├── explanation.md        # Internal architecture & refactoring overview
└── copilot_cli/          # Core Python package
    ├── __main__.py       # Module entry bridging to copilot-cli.py
    ├── args.py           # Dataclass for CLI arguments
    ├── constants.py      # DEFAULT_SYSTEM_PROMPT
    ├── copilot.py        # GitHubCopilotClient (token & chat logic)
    ├── action/           # ActionManager & Pydantic models
    ├── streamer/         # MarkdownStreamer using Rich
    ├── utils.py          # Helper functions (spinner logic)
    └── log.py            # Simple CLI logging
```

## Implementation Details

- **Optional Dependency Stubs**: Fallback shims for Pydantic, typing_extensions, YAML, Pyperclip, Halo, and Rich so core logic survives in restricted environments.
- **Authentication Flow**: Reads OAuth token from IDE config or environment; exchanges it for a Copilot API token and caches it under `/tmp/copilot_token.json`.
- **Offline Fallback**: In absence of HTTP connectivity or token errors, requests fall back to a deterministic stub echoing the prompt.
- **Spinner Logic**: `should_enable_spinner()` centralizes global (`--no-spinner`) and per-action toggles.

## Development

- See `explanation.md` for an in-depth technical analysis and recent refactorings.
- CI/Release automation builds a standalone binary via PyInstaller (`.github/workflows/main.yml`).
- **Continuous Integration**: Run tests and lint on push/PR via `.github/workflows/ci.yml`.
- **Running tests**:
  ```sh
  pip install --upgrade pip
  pip install -e .
  pip install -r requirements.txt
  pytest --maxfail=1 --disable-warnings -q
  ```

## Contributing

Contributions are welcome! Please open issues or pull requests, follow the existing code style, and include tests where applicable.

## Acknowledgements

- [GitHub Copilot](https://github.com/features/copilot)  
- [OpenAI GPT-4](https://openai.com/research/gpt-4)  
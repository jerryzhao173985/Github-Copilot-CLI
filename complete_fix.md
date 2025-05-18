# Copilot CLI Updates (Previous changes)

## Previous Authentication Logic Enhancements (Reference)

I’ve bolstered the authentication logic so that:

1.  `enterprise_list` no longer blows up when missing from GitHub’s token JSON (we default it to `[]`).
2.  We now catch Pydantic’s `ValidationError` in the chat paths so any unexpected token‐shapes just fall back to the offline stub, instead of crashing.
3.  You’ll automatically pick up your personal Copilot token wherever VS Code stores it on macOS, Linux or Windows (in addition to the old `~/.config/github-copilot` paths).
4.  The README has been updated to document all of the above.

---

### 1. Import `ValidationError` and `sys`, Wire in the Default for `enterprise_list`

**File:** `copilot_cli/copilot.py`
**(Path:** `/Users/jerry/Downloads/copilot-cli/copilot_cli/copilot.py`)

```diff
--- a/copilot_cli/copilot.py
+++ b/copilot_cli/copilot.py
@@
-from pydantic import BaseModel, Field
+from pydantic import BaseModel, Field, ValidationError
@@ class CopilotToken(BaseModel):
-    enterprise_list: list[int]
+    enterprise_list: list[int] = Field(default_factory=list)
````

-----

### 2\. Catch Token-model Validation Errors in the “Offline Fallback” Paths

**File:** `copilot_cli/copilot.py`
**(Path:** `/Users/jerry/Downloads/copilot-cli/copilot_cli/copilot.py`)

```diff
--- a/copilot_cli/copilot.py
+++ b/copilot_cli/copilot.py
@@    def chat_completion(self, prompt: str, model: str, system_prompt: str) -> str:
-        except (RequestException, APIError, AuthenticationError):
+        except (RequestException, APIError, AuthenticationError, ValidationError):
@@    def stream_chat_completion(self, prompt: str, model: str, system_prompt: str) -> Iterator[str]:
-        except (RequestException, APIError, AuthenticationError):
+        except (RequestException, APIError, AuthenticationError, ValidationError):
```

-----

### 3\. Extend OAuth-token Lookup for VS Code’s `globalStorage` on macOS, Linux & Windows

**File:** `copilot_cli/copilot.py`
**(Path:** `/Users/jerry/Downloads/copilot-cli/copilot_cli/copilot.py`)

```diff
--- a/copilot_cli/copilot.py
+++ b/copilot_cli/copilot.py
@@
-import urllib.parse
+import urllib.parse
+import sys
@@    def _load_oauth_token(self) -> str:
-        config_dir = os.getenv("XDG_CONFIG_HOME", Path.home() / ".config")
-
-        files = [
-            Path(config_dir) / "github-copilot" / "hosts.json",
-            Path(config_dir) / "github-copilot" / "apps.json",
-        ]
+        # Default Copilot extension config directory (Linux/XDG), plus VS Code’s globalStorage
+        config_dir = Path(os.getenv("XDG_CONFIG_HOME", Path.home() / ".config"))
+
+        files = [
+            config_dir / "github-copilot" / "hosts.json",
+            config_dir / "github-copilot" / "apps.json",
+        ]
+
+        # Also check VS Code Copilot extension state under globalStorage
+        if sys.platform == "darwin":
+            base = Path.home() / "Library" / "Application Support"
+        elif sys.platform == "win32":
+            base = Path(os.getenv("APPDATA", Path.home() / "AppData" / "Roaming"))
+        else:
+            base = config_dir
+        vsc_storage = base / "Code" / "User" / "globalStorage" / "github.copilot"
+        files.extend([
+            vsc_storage / "hosts.json",
+            vsc_storage / "apps.json",
+        ])
```

-----

### 4\. Document the New Lookup Locations in the README

**File:** `README.md`
**(Path:** `/Users/jerry/Downloads/copilot-cli/README.md`)

```diff
--- a/README.md
+++ b/README.md
@@ Copilot CLI locates your GitHub Copilot OAuth token from:
-- `$GITHUB_COPILOT_OAUTH_TOKEN`, `$COPILOT_OAUTH_TOKEN`, `$GITHUB_TOKEN`, or `$GH_TOKEN` environment variables  
-- `~/.config/github-copilot/hosts.json` or `apps.json` (VS Code/Neovim/JB extensions)

-Set one of the above if you are not using an IDE plugin.
+`$GITHUB_COPILOT_OAUTH_TOKEN`, `$COPILOT_OAUTH_TOKEN`, `$GITHUB_TOKEN`, or `$GH_TOKEN` environment variables  
+Local Copilot extension config (`hosts.json`/`apps.json`):
+  - Linux/XDG: `~/.config/github-copilot/{hosts,apps}.json`
+  - VS Code globalStorage Copilot extension state:
+    - Linux: `~/.config/Code/User/globalStorage/github.copilot/{hosts,apps}.json`
+    - macOS: `~/Library/Application Support/Code/User/globalStorage/github.copilot/{hosts,apps}.json`
+    - Windows: `%APPDATA%/Code/User/globalStorage/github.copilot/{hosts,apps}.json`
+
+Set one of the above if you are not using an IDE plugin.
```

-----

### What to do next (for previous changes)

1.  **Reinstall dependencies** (so you have `requests`, `pydantic`, etc.):
    ```bash
    pip install --upgrade pip
    pip install -r requirements.txt
    ```
2.  **Run your tests and smoke-test the CLI**:
    ```bash
    pytest --maxfail=1 --disable-warnings -q
    ./copilot --help
    ```
3.  **Try a quick prompt** to ensure you pick up your personal GitHub.com Copilot token:
    ```bash
    ./copilot --prompt "hello" --model gpt-4
    ```
    – If you’re signed into VS Code on GitHub.com Copilot, the CLI should now automatically find that token.

With these changes the `enterprise_list` error goes away, the CLI won’t crash on unexpected token shapes, and it will “just work” with your personal GitHub.com Copilot credentials on macOS, Linux, or Windows.

-----

-----

---

## Copilot CLI Fixes and Enhancements (new changes)

This document outlines recent improvements to the Copilot CLI, focusing on enhanced token handling, documentation clarifications, and .gitignore updates. These changes aim to prevent crashes due to unexpected token shapes and provide a more robust user experience.

-----

### 1\. Don’t Crash on a Bad Cached Token

We have improved the handling of cached tokens. The CLI will now catch `ValidationError` when loading a cached token. If the token is malformed, the cache will be deleted, preventing the CLI from crashing.

**File:** `copilot_cli/copilot.py`
**(Path:** `/Users/jerry/Downloads/copilot-cli/copilot_cli/copilot.py`)

```diff
       def _load_cached_token(self) -> None:
   @@
   -         if cache_path.exists():
   -             try:
   -                 token_data = json.loads(cache_path.read_text())
   -                 self._copilot_token = CopilotToken(**token_data)
   -             except (json.JSONDecodeError, TypeError):
   -                 cache_path.unlink(missing_ok=True)
   +         if cache_path.exists():
   +             try:
   +                 token_data = json.loads(cache_path.read_text())
   +                 self._copilot_token = CopilotToken(**token_data)
   +             except (json.JSONDecodeError, TypeError, ValidationError):
   +                 cache_path.unlink(missing_ok=True)

```

-----

### 2\. Wrap the Pydantic-model Instantiation in `_refresh_copilot_token`

If GitHub’s `/token` endpoint returns an unexpected payload (e.g., missing `enterprise_list`), the CLI will now catch this and raise an `APIError`. Downstream paths, such as `chat_completion`, will then catch this error and fall back to the offline stub instead of crashing.

**File:** `copilot_cli/copilot.py`
**(Path:** `/Users/jerry/Downloads/copilot-cli/copilot_cli/copilot.py`)

```diff
       def _refresh_copilot_token(self) -> None:
   @@
   -             token_data = response.json()
   -
   -             self._copilot_token = CopilotToken(**token_data)
   +             token_data = response.json()
   +
   +             try:
   +                 self._copilot_token = CopilotToken(**token_data)
   +             except ValidationError as e:
   +                 raise APIError(f"Invalid Copilot token data received: {e}") from e

```

Additionally, `ValidationError` is now imported alongside `Field` at the top of the file:

**File:** `copilot_cli/copilot.py`
**(Path:** `/Users/jerry/Downloads/copilot-cli/copilot_cli/copilot.py`)

```python
    import requests
    from pydantic import BaseModel, Field, ValidationError
```

-----

### 3\. Clean Up Stray Files & Tighten `.gitignore`

Accidentally committed temporary `.pem` files and a `__pycache__` artifact have been removed. The `.gitignore` file has been updated to ignore common Python virtual environments and all `*.pem` files.

**File:** `.gitignore`
**(Path:** `/Users/jerry/Downloads/copilot-cli/.gitignore`)

```diff
     # Virtual environments
   -.env/
   -venv/
   -env/
   +.env/
   +venv/
   +env/
   +.venv/

     # OS files
   -*.DS_Store
   +*.pem
   +.DS_Store
```

-----

### 4\. Clarify Personal-token vs Copilot-specific-token in README

The README has been updated to clearly distinguish that `GITHUB_TOKEN`/`GH_TOKEN` are treated as your personal GitHub.com token, while Copilot-specific variables remain for enterprise or custom deployments.

**File:** `README.md`
**(Path:** `/Users/jerry/Downloads/copilot-cli/README.md`)

```diff
   -Copilot CLI locates your GitHub Copilot OAuth token from:
   --
   -- `$GITHUB_COPILOT_OAUTH_TOKEN`, `$COPILOT_OAUTH_TOKEN`, `$GITHUB_TOKEN`, or `$GH_TOKEN` environment variables  
   +- `$GITHUB_COPILOT_OAUTH_TOKEN` or `$COPILOT_OAUTH_TOKEN` for Copilot-specific tokens; `$GITHUB_TOKEN` or `$GH_TOKEN` for personal GitHub.com tokens  
   -Local Copilot extension config (`hosts.json`/`apps.json`):
   +Local Copilot extension config (`hosts.json`/`apps.json`):
   ...
    When multiple Copilot configurations are detected (e.g. personal GitHub.com and an Enterprise host),
    the CLI prefers the personal GitHub.com token by default. To force an Enterprise or other token,
    set one of the environment variables explicitly (e.g. `$GITHUB_COPILOT_OAUTH_TOKEN`, `$COPILOT_OAUTH_TOKEN`,
    `$GITHUB_TOKEN`, or `$GH_TOKEN`).
```

-----

## Next steps

1.  **Reinstall your dependencies** so you have `requests`, `pydantic`, etc. locally:
    ```bash
    pip install --upgrade pip
    pip install -r requirements.txt
    ```
2.  **Smoke-test the CLI.** It should no longer crash on missing fields and will fall back to the offline stub if you’re offline or misconfigured:
    ```bash
    ./copilot --help
    ./copilot --prompt "hello world" --model gpt-4
    ```
3.  **Use your personal token** by either signing into VS Code Copilot (the CLI will auto-discover it in `hosts.json`/`apps.json` or globalStorage), or simply export your GitHub.com token:
    ```bash
    export GITHUB_TOKEN="<your-personal-github-token>"
    ```

With these fixes in place, the `enterprise_list` error is resolved. The CLI now handles malformed or missing fields safely and will correctly pick up either your personal GitHub.com token or an enterprise Copilot token (or fall back to the offline stub) without crashing.



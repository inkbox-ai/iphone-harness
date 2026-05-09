iphone-harness is a thin layer that connects agents to a real iPhone via Appium/XCUITest.

The architecture and conventions are adapted from [browser-harness](https://github.com/browser-use/browser-harness) by Browser Use — when in doubt about a design choice, mirror what they did and translate to iOS.

# Code priorities
- Clarity
- Precision
- Low verbosity
- Versatility

# Overview

Core code lives in `src/iphone_harness/`:
- `daemon.py` — the long-lived middleman that owns the Appium WebDriver session
- `helpers.py` — public action API auto-imported into `-c` scripts
- `admin.py` — daemon lifecycle, doctor
- `run.py` — the `iphone-harness` CLI
- `_ipc.py` — AF_UNIX JSON-line RPC plumbing

`SKILL.md` tells agents how to use the harness and CLI.
`install.md` tells agents how to install it, attach a device, and troubleshoot.

An agent operating the harness only edits inside `agent-workspace/`:
- `agent_helpers.py` — task-specific helpers the agent adds
- `domain-skills/<bundleId>/` — per-app skills the agent writes and reads

# Contributing
Consider what is really needed. Prefer the smallest diff that fixes the bug.

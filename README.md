<!--
SPDX-FileCopyrightText: 2026 Ohad Livne <libohad-dev@proton.me>

SPDX-License-Identifier: CC-BY-SA-4.0
-->

# temper-edit

## Overview

temper-edit is a command-line tool that performs atomic file editing through a temporary copy. It provides a safe way to edit files by ensuring the original is only modified when the editing has finished successfully.

### How It Works

1. Creates a temporary copy of the target file
2. Launches your configured editor on the temporary copy
3. If the editor exits successfully and content changed, atomically replaces the original
4. Preserves the original file's ownership and permissions during replacement
5. If content is unchanged, the original file remains untouched

### Highlights

- **Privilege escalation protection**: Refuses to run when invoked via `sudo`, `doas`, or `pkexec` — use `--elevate` instead for editing privileged files
- **Atomic updates**: Other processes watching the file see either the old or new content, never a partial write
- **Secure replacement**: Uses a permission-controlled sequence to prevent race conditions and privilege attacks
- **Failure recovery**: Preserves the temporary file on editor failure, allowing manual recovery
- **Full test coverage**: Comprehensive test suite with 100% code coverage, tested across multiple Python versions in isolated containers

## Installation

### Requirements

- Python 3.10 or later
- No runtime dependencies

### From Source

```bash
pip install .
```

### Development Installation

```bash
pip install --editable ".[dev]"
```

## Usage

### Basic Usage

```bash
temper-edit <filename>
```

Edit a file using your configured editor. The original file is only updated if the editor exits successfully and the content has changed.

### Options

| Option | Description |
|--------|-------------|
| `filename` | Path to the file to edit (required) |
| `--tmpdir <path>` | Directory for temporary files (optional) |
| `--elevate <program>` | Privilege escalation program to use for editing root-owned files (e.g., `sudo`, `doas`) |

### Editor Selection

temper-edit selects the editor based on environment variables, checked in this order:

1. `SUDO_EDITOR` (highest priority)
2. `VISUAL`
3. `EDITOR`

If none are set, temper-edit exits with an error.

The editor value is parsed using shell quoting rules, so complex commands work:

```bash
export EDITOR="vim -u NONE"
temper-edit myfile.txt
```

### Temporary Directory

By default, temporary files are created in the system's default temporary directory. Override this with:

```bash
# Via command-line argument (highest priority)
temper-edit --tmpdir /my/tmpdir myfile.txt

# Via environment variable
TMPDIR=/my/tmpdir temper-edit myfile.txt
```

### Examples

Edit a configuration file:

```bash
temper-edit /etc/myapp/config.yaml
```

Edit with a specific temporary directory:

```bash
temper-edit --tmpdir /secure/tmp /etc/myapp/config.yaml
```

Edit a root-owned file (requires sudo/doas privileges):

```bash
temper-edit --elevate sudo /etc/hosts
temper-edit --elevate doas /etc/hosts
```
or other alternative programs.

### Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | Refused to run with escalated privileges, or editor not configured |
| Non-zero | Editor failed (exit code propagated) |

## Licensing

This project is distributed under the terms of [GPL-3.0-or-later](https://spdx.org/licenses/GPL-3.0-or-later.html). In addition, it uses
- [CC-BY-SA-4.0](https://spdx.org/licenses/CC-BY-SA-4.0.html) for documentation files
- [CC0-1.0](https://spdx.org/licenses/CC0-1.0.html) (equivalent to public domain) for project configuration files

The [REUSE](https://reuse.software/) tools is used to ensure license compliance.

© 2025-2026 [Ohad Livne](https://github.com/libohad-dev)

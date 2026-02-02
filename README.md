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
- No runtime dependencies (S3 support requires optional `boto3` dependency)

### From Source

```bash
pip install .
```

### With S3 Support

```bash
pip install ".[s3]"
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
| `filename` | Path to the file to edit |
| `--tmpdir <path>` | Directory for temporary files (optional) |
| `--elevate <program>` | Privilege escalation program to use for editing root-owned files (e.g., `sudo`, `doas`) |
| `--s3 <bucket>` | Treat filename as an S3 key in the specified bucket |
| `--force` | Force overwrite even if the S3 object was modified concurrently |

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

The `--elevate` option supports multi-component commands with additional flags:

```bash
temper-edit --elevate "sudo --askpass" /etc/hosts
```

### Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | Refused to run with escalated privileges, or editor not configured |
| Non-zero | Editor failed (exit code propagated) |

### S3 Editing

Edit an S3 object:

```bash
temper-edit --s3 my-bucket path/to/object.txt
```

AWS credentials are read from the standard environment variables (`AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`) or AWS configuration files.

#### Metadata Preservation

When editing S3 objects, the following attributes are preserved after a successful update:

| Attribute | Preserved |
|-----------|-----------|
| Custom metadata (`x-amz-meta-*`) | Yes |
| Content-Type | Yes |
| Content-Encoding | No |
| Content-Disposition | No |
| Cache-Control | No |
| Expires | No |

Attributes not listed above (such as ETag, Last-Modified, and storage class) are managed by S3 and may change as part of the update.

#### Concurrent Modification Detection

temper-edit uses S3 ETags to detect concurrent modifications. If the object is modified by another process after staging but before commit, the upload fails with an error:

```
Failed to update file: path/to/object.txt (concurrent modification detected). Temporary file preserved at: /tmp/tmpXXXXXX
```

This prevents silent data loss when multiple processes edit the same object. The temporary file containing your edits is preserved for manual recovery.

To force an overwrite regardless of concurrent modifications:

```bash
temper-edit --s3 my-bucket --force path/to/object.txt
```

**Recovery workflow** when concurrent modification is detected:

1. The error message shows the path to your preserved edits
2. Re-download the current object to see what changed: `aws s3 cp s3://bucket/key current.txt`
3. Manually merge your changes from the temp file
4. Either re-run temper-edit or use `--force` if you're certain your version should win

## Testing Philosophy

### Full Coverage

The test suite maintains 100% coverage of both lines and branches. This is enforced in CI and ensures that every code path is exercised. Full coverage is achievable and maintainable. Validation gaps tend to grow over time, so maintaining complete coverage prevents technical debt accumulation.

### Behavior-Driven Tests

Tests demonstrate actual behavior rather than implementation details. This includes verifying safety properties under anomalous conditions. For example:

- **Atomicity**: The original file is never left in a partial state, even when the editor crashes mid-edit
- **Permission preservation**: File ownership and mode bits survive the replacement sequence
- **Failure recovery**: Temporary files are preserved when operations fail, allowing manual recovery
- **Security**: The commit sequence prevents race conditions and privilege escalation attacks

### Mock-Free Testing

The test suite uses no mocks. Instead, it relies on:

- **Testability by design**: Code architecture uses dependency injection and factory patterns, making components naturally testable without stubbing internals
- **Containerized execution**: Tests run inside isolated containers across multiple Python versions, exercising real system calls, file operations, and privilege boundaries
- **Real services**: For example, S3 tests use MinIO containers rather than mocked AWS clients, ensuring the code works against actual S3-compatible APIs

This approach catches integration issues that mocks would hide and provides confidence that the code behaves correctly in production environments.

## Licensing

This project is distributed under the terms of [GPL-3.0-or-later](https://spdx.org/licenses/GPL-3.0-or-later.html). In addition, it uses
- [CC-BY-SA-4.0](https://spdx.org/licenses/CC-BY-SA-4.0.html) for documentation files
- [CC0-1.0](https://spdx.org/licenses/CC0-1.0.html) (equivalent to public domain) for project configuration files

The [REUSE](https://reuse.software/) tools is used to ensure license compliance.

© 2025-2026 [Ohad Livne](https://github.com/libohad-dev)

# Security model

Isolated Vision reduces one kind of parent-rollout exposure. It is not a
general security boundary.

## Protected path

Protection applies only when the parent routes an absolute local image path
through the Skill before any image-bearing tool call:

- an ephemeral child receives the image through `codex exec --image`;
- the launcher consumes child stdout privately and discards raw JSONL payloads
  and stderr;
- a run-specific schema fixes the expected source indices, attachment IDs,
  question indices, and counts;
- only a validated JSON report and fixed diagnostics reach the parent;
- Data URLs, base64-like data, image signatures and keys, Markdown images, HTML
  image tags, malformed reports, and incomplete coverage fail closed;
- handled timeouts and interrupts terminate the worker process group and remove
  the private image workspace;
- optional job records contain only coarse status and the validated result. Files
  are `0600` inside a `0700` text-only directory on POSIX systems. On Windows,
  job and private-workspace directories have a protected DACL for the current
  account, SYSTEM, and local Administrators, which child files inherit;
- on Windows, the worker is assigned to a kill-on-close Job Object so an abrupt
  launcher exit terminates its process tree.

A report recovered after timeout must pass the same safety, schema, and coverage
checks as an ordinary result.

## Outside the boundary

- Skill selection is behavioral; no Hook forcibly intercepts `view_image`.
- Pixels already attached to the parent or returned inline by another tool cannot
  be removed retroactively.
- The child uses the same OS account, Codex authentication, environment, and
  filesystem access allowed by its sandbox.
- Images still travel through the normal Codex model path. `--ephemeral` changes
  local session persistence, not service-side data policy.
- A normal link to a source may be fetched or proxied by the Codex UI.
  That UI-side transfer is outside this boundary; omit such links for sensitive
  material.
- Worker instructions are not an OS control. Pillow decodes source files locally,
  so keep it current and sandbox hostile inputs separately.
- Text reports can be incomplete or wrong. Recoverable job records persist until
  cleanup and may contain sensitive conclusions.
- `SIGKILL`, Windows `TerminateProcess`, host crashes, or power loss may leave
  temporary workspaces or job records behind. An abrupt Windows exit still
  terminates the assigned worker tree, but cannot run Python directory cleanup.

Do not use this project as the sole control for secrets, regulated data, hostile
files, or environments where the child must not read other local data.

## Reporting a vulnerability

Use GitHub private vulnerability reporting when available. Otherwise, open a
minimal non-sensitive issue and ask for a private channel. Never publish sensitive
images, transcripts, credentials, or raw rollout data.

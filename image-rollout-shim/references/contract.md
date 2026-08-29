# Image Rollout Shim Contract

## Boundary

The parent model may know image paths, labels, textual task context, and the final report. It must not receive an image content item, data URL, encoded image bytes, Markdown image, or raw child-process stream. Raw child stdout and stderr are discarded.

The routing point is immediately before any parent `view_image` call for a local path. The parent replaces that call with the launcher and supplies the visual brief derived from its current task and active domain skills. This contract cannot retroactively isolate pixels already returned by another screenshot/image tool or attached by the user.

For programmatic CUA or browser calls, an inner tool result may contain screenshot data without entering the parent rollout only when the outer exec does not forward that image content. Surface text or a stable absolute local screenshot path instead. A required screenshot may then be inspected through the launcher; a tool that can only emit pixels to the parent is outside this shim's isolatable path.

The launcher and ephemeral child process can read the source files. The child runs under the same OS account, inherits the launching process environment and normal Codex authentication/configuration, and may be able to read other files permitted by its sandbox. The child sends image inputs through the normal Codex model path. `--ephemeral` prevents local session rollout persistence; it does not create a separate OS identity or alter provider-side data policy.

## Review modes

- `standard` attaches each supported source once. Use it for ordinary images where small details are not decisive.
- `thorough` privately normalizes orientation, creates a whole-image overview, and adds overlapping native-resolution PNG tiles when the overview would lose detail. The report must account for every attachment region.

## Worker model

The launcher accepts one optional `--model` value. Omitted, empty, or whitespace-only input resolves to `gpt-5.6-sol`. A non-empty value must be a single 1–128 character model identifier: it starts with an ASCII letter or digit and then contains only ASCII letters, digits, `.`, `_`, `:`, `/`, `@`, `+`, or `-`. The launcher passes the validated value as one argv element after Codex's `--model` option, so it cannot add flags or shell syntax. The successful launch metadata reports the resolved value as `effective_model`.

## Report

The report separates observations from recommendations. Every finding includes severity, evidence, location, and confidence. Coordinates are normalized to the original source image; `-1` means that a precise box is not defensible. Coverage lists every inspected attachment ID and any limitations.

The worker report schema is [report.schema.json](../scripts/report.schema.json). The parent-facing success/error envelope, including non-image execution metadata, is [launcher-output.schema.json](../scripts/launcher-output.schema.json).

## Fail-closed behavior

The launcher returns only a safe error code when it cannot create its private workspace, the parent sandbox prevents the nested Codex worker from running, the worker times out, exits unsuccessfully, omits output, produces invalid JSON, fails schema checks, misses attachment coverage, or emits image-like payloads. It never forwards the rejected output and never asks the parent to inspect the image directly.

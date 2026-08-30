# Image Rollout Shim Contract

## Boundary

The parent model may know image paths, labels, textual task context, the final report, and fixed non-image diagnostics. It must not receive an image content item, data URL, encoded image bytes, Markdown image, or raw child-process stream. The launcher consumes the worker's JSONL stdout privately, retains only whitelisted event categories and aggregate timings, and discards every raw event payload plus stderr.

The routing point is immediately before any parent `view_image` call for a local path. The parent replaces that call with the launcher and supplies the visual brief derived from its current task and active domain skills. This contract cannot retroactively isolate pixels already returned by another screenshot/image tool or attached by the user.

For programmatic CUA or browser calls, an inner tool result may contain screenshot data without entering the parent rollout only when the outer exec does not forward that image content. Surface text or a stable absolute local screenshot path instead. A required screenshot may then be inspected through the launcher; a tool that can only emit pixels to the parent is outside this shim's isolatable path.

The launcher and ephemeral child process can read the source files. The child runs under the same OS account, inherits the launching process environment and normal Codex authentication/configuration, and may be able to read other files permitted by its sandbox. The child sends image inputs through the normal Codex model path. `--ephemeral` prevents local session rollout persistence; it does not create a separate OS identity or alter provider-side data policy.

## Review modes

- `standard` attaches each supported source once. Use it for ordinary images where small details are not decisive.
- `thorough` privately normalizes orientation, creates a whole-image overview, and adds overlapping native-resolution PNG tiles when the overview would lose detail. The report must account for every attachment region.

The maximum of eight source images and 48 prepared attachments is a validation ceiling, not a performance recommendation. Batch only images that need direct comparison or shared visual reasoning. Independent groups should run sequentially so each request stays semantically focused; `thorough` attachment expansion, total source pixels, and task complexity can matter more than the source-image count alone.

## Worker model

The launcher accepts one optional `--model` value. Omitted, empty, or whitespace-only input resolves to `gpt-5.6-sol`. A non-empty value must be a single 1–128 character model identifier: it starts with an ASCII letter or digit and then contains only ASCII letters, digits, `.`, `_`, `:`, `/`, `@`, `+`, or `-`. The launcher passes the validated value as one argv element after Codex's `--model` option, so it cannot add flags or shell syntax. The successful launch metadata reports the resolved value as `effective_model`.

## Report

The report separates observations from recommendations. Every finding includes severity, evidence, location, and confidence. Coordinates are normalized to the original source image; `-1` means that a precise box is not defensible. Coverage lists every inspected attachment ID and any limitations.

The worker report schema is [report.schema.json](../scripts/report.schema.json). The parent-facing success/error envelope, including non-image execution metadata, is [launcher-output.schema.json](../scripts/launcher-output.schema.json). Diagnostics contain only fixed phases, elapsed times, source/attachment counts, aggregate byte and pixel counts, the selected model and reasoning effort, whitelisted worker-event categories, exit state, and final-report recovery state. They never contain paths, labels, prompts, report text, stderr, or raw JSONL events.

## Fail-closed behavior

The launcher returns only a safe error code and fixed diagnostics when it cannot create its private workspace, the parent sandbox prevents the nested Codex worker from running, the worker times out, exits unsuccessfully, omits output, produces invalid JSON, fails schema checks, misses attachment coverage, or emits image-like payloads. If a timeout occurs after `final-report.json` was fully written, the launcher may recover it only after ordinary output-safety, schema, and coverage validation succeeds. Partial, invalid, incomplete, or image-like timeout output still fails closed. The launcher never forwards rejected output and never asks the parent to inspect the image directly.

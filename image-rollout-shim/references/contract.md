# Image Rollout Shim Contract

## Boundary

The parent may know source paths, labels, task context, the final text report, and
fixed non-image diagnostics. It must not receive image content, Data URLs, encoded
bytes, Markdown images, or raw child-process streams. The launcher keeps only
whitelisted event categories and aggregate timings; raw JSONL payloads and stderr
are discarded.

Routing happens immediately before a would-be parent `view_image` call. The parent
supplies the visual brief derived from the active task and any relevant domain
Skill. Pixels already attached to the parent or returned by another tool cannot be
isolated retroactively.

For CUA or browser automation, an outer exec may keep an inner screenshot out of
the parent rollout only when it forwards text or a stable local path—not image
content. Inspect that path through this launcher. Tools that can only return pixels
to the parent are outside the shim's path.

The parent may link a stable original source as a normal Markdown file link when
the user should see it. Do not use image syntax or worker-private prepared files.
The Codex UI may fetch or proxy the linked file for preview; that transfer is
outside this boundary, so omit optional links for sensitive sources.

The launcher and child can read the sources. The child uses the same OS account,
environment, Codex authentication, and filesystem access allowed by its sandbox.
Images use the normal Codex model path. `--ephemeral` prevents local child-session
persistence; it does not create a separate identity or change provider policy.

## Job control

An optional opaque `--job-id` creates a text-only record in the OS temporary
directory. `status.json` is updated atomically with fixed phase, state, timing,
counts, safe error code, and whitelisted event categories. `result.json` is written
before a terminal state is recorded. Files are `0600` inside a `0700` directory and
contain no source paths, labels, prompts, raw events, stderr, or report drafts.

The command runner's managed session remains the normal result path. If its handle
is lost, `status --job-id ID` gives coarse last-known progress but does not prove
process liveness. After a terminal state, `collect --job-id ID` returns the same
validated envelope without rerunning the review. `cleanup --job-id ID` removes a
terminal record and refuses a running job.

## Review modes

- `standard` attaches each supported source once.
- `thorough` normalizes orientation, creates a whole-image overview, and adds
  overlapping native-resolution PNG tiles when detail would otherwise be lost.
  The report must cover every attachment region.

Eight sources and 48 prepared attachments are validation ceilings, not recommended
batch sizes. Group only images that need direct comparison. Total pixels,
attachment expansion, and task complexity can matter more than source count.

## Worker model

Omitted or blank `--model` input resolves to `gpt-5.6-sol`. A supplied identifier
must be 1–128 ASCII characters, start with a letter or digit, and then use only
letters, digits, `.`, `_`, `:`, `/`, `@`, `+`, or `-`. It is passed as one argv
element and cannot become extra child-CLI flags. Successful diagnostics expose it
as `effective_model`.

## Report

Findings separate observations from recommendations and include severity,
evidence, location, and confidence. Coordinates refer to the original source;
`-1` means a precise box is not defensible. `answers` represents every requested
question exactly once by its 1-based `question_index`. Coverage lists every
attachment ID exactly once and records limitations.

The base worker schema is [report.schema.json](../scripts/report.schema.json). For
each run, the launcher specializes it with the exact mode, counts, source indices,
attachment IDs, and question indices; the local validator independently rechecks
the output. The parent envelope is
[launcher-output.schema.json](../scripts/launcher-output.schema.json).

Diagnostics are limited to fixed phases, elapsed times, counts, aggregate byte and
pixel totals, selected model and reasoning effort, whitelisted event categories,
exit/recovery state, and an optional fixed validation-rule ID. They never include
paths, labels, prompts, report text, stderr, or raw events.

## Fail-closed behavior

Workspace or job-state errors, blocked worker launch, timeout, nonzero exit,
missing output, invalid JSON, schema failure, incomplete coverage, and image-like
payloads return only a safe error code and fixed diagnostics. Handled interrupts
and ordinary timeouts terminate the worker process group and remove the private
image workspace. `SIGKILL`, host failure, or power loss can still leave temporary
files; job records intentionally remain until cleanup.

If a timeout occurs after `final-report.json` was fully written, the launcher may
recover it only after the normal safety, schema, and coverage checks pass. Partial
or rejected output is never forwarded, and the parent is never told to inspect the
image directly as a fallback.

# Isolated Vision Contract

## Boundary

The parent-side interface is limited to source paths, labels, task context, the
validated text report, and fixed non-image diagnostics. Image content and raw
worker streams remain inside the isolated path.

Routing begins before a parent image-bearing tool call. Pixels already attached
to the parent or returned inline by another tool are already part of the parent
context. Browser and CUA screenshots join this path when an outer exec can
provide a stable absolute local path without forwarding image content.

The parent may link a stable original source as an ordinary file link. The Codex
UI may fetch or proxy that source for preview; that UI-side transfer is outside
this boundary.

The launcher and worker use the current OS account, environment, Codex
authentication, and filesystem access allowed by the worker sandbox. Images use
the normal Codex model path. `--ephemeral` controls local child-session
persistence rather than provider data policy.

## Request

The request contains a required `objective` plus optional `context`, `focus`,
`questions`, `image_labels`, and `output_language`. `focus` provides attention
priorities within the complete visual field. One request may contain up to eight
sources that benefit from shared visual reasoning.

## Image preparation

Automatic preparation is the normal path. For each source, the launcher applies
EXIF orientation and creates a PNG whole-image overview with a maximum edge of
2048 pixels. Sources larger than the overview also receive overlapping
native-resolution PNG tiles.

Tiles overlap by 128 pixels. The launcher selects one tile size for the request
from 1600, 2048, 2560, 3072, or 4096 pixels, choosing the smallest candidate
that keeps the request within the 48-attachment ceiling.

`--original-only` attaches each directly supported PNG, JPEG, WEBP, or GIF
source once, unchanged. It applies to the whole request.

## Job control

A fresh opaque `--job-id` creates a text-only record in the operating system's
temporary directory. Job files are `0600` inside a `0700` directory and contain
no source paths, labels, prompts, raw events, stderr, image data, or report
drafts.

The command runner's managed foreground session is the normal result path. If
that handle is lost, `status --job-id ID` returns coarse persisted progress,
`collect --job-id ID` returns a terminal validated envelope, and
`cleanup --job-id ID` removes a terminal record. Status is a progress snapshot,
not a liveness probe or ETA.

## Worker model

An omitted or blank `--model` resolves to `gpt-5.6-sol`. A supplied identifier
must be 1–128 ASCII characters, begin with a letter or digit, and then use only
letters, digits, `.`, `_`, `:`, `/`, `@`, `+`, or `-`. Worker reasoning effort
defaults to `high` and may be selected independently with `--reasoning-effort`.

## Report

The report contains a holistic summary, localized observations, indexed
answers, uncertainties, and attachment coverage. Coordinates refer to the
original source; `-1` means a precise box is not supported by the visible
evidence.

For each run, the launcher specializes
[report.schema.json](../scripts/report.schema.json) with the exact source count,
attachment IDs, and question indices. The local validator independently checks
the result. The parent envelope is
[envelope.schema.json](../scripts/envelope.schema.json).

Diagnostics contain fixed phases, aggregate timings and counts, selected model
and reasoning effort, whitelisted event categories, recovery state, and an
optional fixed validation-rule ID.

## Safe failure

Workspace or job-state errors, blocked worker launch, timeout, nonzero exit,
missing output, invalid JSON, schema failure, incomplete coverage, and
image-like output return a fixed safe error envelope. Handled interrupts and
ordinary timeouts terminate the worker process group and remove the private
image workspace.

A fully written final report may be recovered after timeout when it passes the
same safety, schema, and coverage checks as an ordinary result. Host failure or
power loss may leave temporary workspaces or job records behind; a record left
in the `running` state by such a failure is removed manually, since `cleanup`
only removes terminal records.

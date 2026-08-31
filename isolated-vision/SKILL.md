---
name: isolated-vision
description: Route absolute local image paths through an ephemeral Codex exec visual worker when the parent task or another skill needs visual information, and return a validated text report to the parent. Images already attached to the parent message are outside this path; the internal worker marker selects the worker flow.
---

# Isolated Vision

This is an interim isolated visual path. An ephemeral Codex exec worker views
local images, and the parent task continues from validated text observations.
See [references/contract.md](references/contract.md) for the trust boundary.

It supports native Windows. It requires Python 3.10 or newer with Pillow, an
authenticated `codex` CLI on `PATH`, private temporary-directory access, and
service access for the nested Codex process.

## Parent flow

Use this flow unless the prompt contains `[isolated-vision-worker:v1]`.

- Invoke this Skill at the natural point where the parent or another active
  Skill needs visual information from absolute local image paths.
- Pass the image or comparison set naturally needed by the task. Single images,
  repeated views, and multi-image comparisons are all normal.
- When a source helps the user follow the work, show its stable absolute path
  as a Markdown image in a commentary update while visual processing runs.
- Provide a concise objective, relevant context, optional attention priorities,
  optional questions, useful image labels, and the output language. Images
  determine visible state; context explains the current purpose and hypotheses.
  Attention priorities guide the worker while the complete visual field remains
  in scope.
- Resolve `scripts/vision.py` relative to this file and invoke it with an
  available Python 3.10+ interpreter using `python`. Start the task with the
  explicit `run` subcommand, pass the request JSON on stdin, and provide one
  `--image` per source.
- Image preparation is automatic. Add `--original-only` only when the task
  intentionally needs each directly supported original attached once.
- Give each run a fresh random opaque `--job-id`. Keep the command runner's
  managed foreground session until it returns, with the `run` command's stdout
  redirected to PowerShell's `$null`. Retrieve the parent-facing envelope once
  with `collect --job-id ID`, then remove the terminal record with `cleanup
  --job-id ID` using the same interpreter. Read the contract only when progress
  or recovery details are needed.
- Pass a user-selected worker model with `--model`, or omit it to use
  `gpt-5.6-sol`.
- Keep the parent-side exchange to paths, text, and safe diagnostics. Continue
  the parent workflow from the launcher's final JSON envelope.

Request JSON:

```json
{
  "objective": "Why the parent needs visual information now",
  "context": "Relevant task context or working hypotheses",
  "focus": ["Optional attention priorities"],
  "questions": ["Optional direct questions"],
  "image_labels": ["Optional labels in --image order"],
  "output_language": "Match the user's language"
}
```

## Worker flow

When the prompt contains `[isolated-vision-worker:v1]`, inspect the images
already attached to that prompt. Follow the supplied request, attachment
manifest, and output schema, and return exactly one text-only JSON report.

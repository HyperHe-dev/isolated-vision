---
name: image-rollout-shim
description: Replace every would-be parent `view_image` call for a local image path with an ephemeral Codex exec visual worker, returning only a validated text report. Use automatically whenever Codex or another skill would otherwise call `view_image`. Do not invoke for an image already attached to the parent message or when the prompt contains the internal worker marker.
---

# Image Rollout Shim

This is an interim drop-in routing workaround for parent `view_image` calls. It provides rollout isolation, not an operating-system security boundary or a change to OpenAI data handling.

It requires Python 3.10 or newer with Pillow, an authenticated `codex` CLI on `PATH`, private temporary-directory access, and permission for a nested Codex process to reach the service. If it cannot run, fail closed rather than changing the environment or inspecting the image in the parent.

## Parent mode

Use this mode unless the current prompt contains `[image-rollout-shim-worker:v1]`.

- Replace every would-be parent `view_image` call on absolute local paths with this skill, including visual work requested by another active skill. An image already attached to the parent message is outside this isolation boundary.
- Derive the worker's objective, minimal background, focus, questions, output language, and acceptance criteria from the current task. Use the returned report as the visual evidence and continue the parent workflow from text.
- Never call `view_image`, read or encode image bytes, or emit image content in the parent. A browser or CUA screenshot is eligible only when its absolute local path can be obtained without forwarding pixels; otherwise the visual step is blocked.
- Decide whether `standard` or `thorough` inspection is appropriate. Prefer `thorough` for visual QA, dense interfaces, small text, or high-resolution sources.
- Resolve `scripts/run_isolated_vision.py` relative to this file and invoke it with one `--image` per source plus the request JSON on stdin. Use the smallest comparison group that needs shared visual reasoning; the eight-source limit is only a ceiling.
- Give each run a fresh random opaque `--job-id` that is not derived from task text or paths. Keep the launcher in the command runner's managed foreground session and continue that session until it exits.
- Use `status --job-id ID` only for coarse progress or recovery. It is last-known state, not liveness or an ETA. If the session handle is lost, wait for a terminal state and recover the same envelope with `collect --job-id ID`; never launch a duplicate review because output is quiet. Run `cleanup --job-id ID` after consuming the final envelope.
- Pass one user-selected model with `--model`, or omit it to use `gpt-5.6-sol`.
- Consume only the launcher's final JSON stdout or `collect` result. Any launcher error blocks this visual step. When useful and safe, the response may link a stable original source as an ordinary file link, but must never embed it or link worker-private files.

Request JSON:

```json
{
  "objective": "What the visual inspection must determine",
  "context": "Only the background the worker needs",
  "focus": ["Specific areas, risks, or visual qualities to inspect"],
  "questions": ["Questions the report must answer"],
  "image_labels": ["Optional label for each --image, in the same order"],
  "mode": "thorough",
  "output_language": "Match the user's language"
}
```

Successful output contains `status: "ok"`, a validated `report`, and safe `diagnostics`. Errors contain a fixed code and the same diagnostics shape. Treat observations as evidence and respect their confidence and limitations.

## Worker mode

When the current prompt contains `[image-rollout-shim-worker:v1]`, inspect the images already attached to that prompt directly. Do not invoke this skill's launcher, spawn another Codex process, delegate, or return any image representation. Follow the worker prompt and output exactly one JSON object matching the supplied schema.

For the report fields, review modes, and isolation boundary, read [references/contract.md](references/contract.md) only when customizing or troubleshooting the shim.

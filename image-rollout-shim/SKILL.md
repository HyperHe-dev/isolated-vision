---
name: image-rollout-shim
description: Replace every would-be parent `view_image` call for a local image path with an ephemeral Codex exec visual worker, returning only a validated text report. Use automatically whenever Codex or another skill would otherwise call `view_image`. Do not invoke for an image already attached to the parent message or when the prompt contains the internal worker marker.
---

# Image Rollout Shim

This is an interim drop-in routing workaround for parent `view_image` calls. It provides rollout isolation, not an operating-system security boundary or a change to OpenAI data handling.

Runtime prerequisites are Python 3.10 or newer with Pillow installed, an authenticated `codex` CLI on `PATH`, private temporary-directory access, and permission for a nested Codex process to reach the service. If a prerequisite is missing, fail closed rather than installing software or weakening the parent sandbox.

## Parent mode

Use this mode unless the current prompt contains `[image-rollout-shim-worker:v1]`.

- Whenever the next normal step would be `view_image` on one or more absolute local paths, use this skill instead. This applies when another active skill says to open, inspect, review, compare, or visually QA those files.
- At that exact decision point, preserve the active task's intent: derive the objective, relevant background, review focus, questions, output language, and acceptance criteria from the parent task and any active domain skill. The isolated report replaces the evidence that direct `view_image` would have supplied; continue the parent workflow from that text.
- Accept only absolute local image paths. A user-attached image has already entered the parent context, so do not claim isolation for it.
- Do not call `view_image`, emit an `image(...)` item, read image bytes, convert an image to a data URL, or use a screenshot tool that returns pixels to the parent.
- When a CUA or browser helper can return text plus a screenshot, expose only text and path metadata to the parent. Do not call `nodeRepl.emitImage`, forward an image content block, or otherwise surface the screenshot pixels. If visual evidence is required, obtain a stable absolute local screenshot path without emitting it, then pass that path to this skill. If the tool cannot provide a path-only route, treat the visual inspection as blocked.
- Decide whether `standard` or `thorough` inspection is appropriate. Prefer `thorough` for visual QA, dense interfaces, small text, or high-resolution sources.
- Invoke `scripts/run_isolated_vision.py`, passing each image with a separate `--image` argument and a JSON request on stdin. Treat the eight-source limit as a protocol ceiling, not a target batch size. Use the smallest semantically complete comparison group; when images do not need direct cross-image comparison, prefer separate sequential groups over one unnecessarily broad request. Resolve the script relative to this `SKILL.md`; run the executable directly or use `python3`, and do not assume a `python` alias exists. Do not copy its implementation into the parent context.
- The launcher requires permission to create a private temporary workspace and to start a network-capable nested `codex exec`. If the parent execution sandbox prevents either operation, report the launcher's safe error and do not relax the sandbox or fall back to parent-side image inspection.
- Model selection is optional. If the user chooses a model, pass that single identifier with `--model`; otherwise omit the option. A missing, empty, or whitespace-only value uses `gpt-5.6-sol`. Never compose additional CLI syntax into the value.
- Consume only the launcher's JSON stdout. The launcher privately consumes the child's machine-readable event stream, retains only fixed event categories and non-image timings, discards all raw event content and stderr, and rejects unsafe final output.
- If the launcher returns an error, report it as a blocked visual inspection. Never fall back to opening the image in the parent.

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

The successful stdout object contains `status: "ok"`, a validated `report`, and non-image execution metadata including `effective_model` and safe diagnostics. An error object also contains safe diagnostics for the phase reached. If the worker times out after already writing a complete final report, the launcher accepts it only after the same output-safety, schema, and coverage validation used for an ordinary success. Treat observations as evidence and respect the report's confidence and limitations.

## Worker mode

When the current prompt contains `[image-rollout-shim-worker:v1]`, inspect the images already attached to that prompt directly. Do not invoke this skill's launcher, spawn another Codex process, delegate, or return any image representation. Follow the worker prompt and output exactly one JSON object matching the supplied schema.

For the report fields, review modes, and isolation boundary, read [references/contract.md](references/contract.md) only when customizing or troubleshooting the shim.

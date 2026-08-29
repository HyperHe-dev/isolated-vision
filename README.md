# Image Rollout Shim

English | [简体中文](README.zh-CN.md)

Experimental Codex Skill that routes local-image inspection through an ephemeral
`codex exec` worker and returns a validated text-only report to the parent task.

The narrow goal is to keep image content, Data URLs, base64, and raw worker
streams out of the parent task's rollout when the parent would otherwise call
`view_image` on an absolute local path.

> [!IMPORTANT]
> This is a behavioral rollout-isolation workaround, not an OS sandbox, a data
> processing guarantee, or an OpenAI product. Read [SECURITY.md](SECURITY.md)
> before using it with sensitive material.

## How it works

1. The parent task derives a visual brief from its active task and domain Skill.
2. The launcher validates the brief and local image paths.
3. In `thorough` mode it privately creates an overview plus overlapping
   native-resolution tiles when needed.
4. An authenticated, ephemeral `codex exec --image` worker reviews those images.
5. The launcher discards the worker's stdout and stderr, validates its final JSON,
   rejects image-like output, and returns only the text report and safe metadata.

The parent remains responsible for deciding what to inspect and how to apply the
report. The worker only supplies visual evidence.

## Tested behavior and good-fit issues

On the author's local setup, a simple direct visual run took about 14 seconds;
the full implicit parent-to-worker flow took about 31 seconds. A private replay
covered 90 historical image inputs in 13 batches and reproduced the major visual
conclusions while also correcting several overconfident claims. In an end-to-end
smoke test, the parent JSONL contained zero `input_image` blocks, Data URLs, or
base64 markers. These are indicative observations, not portable benchmarks;
latency varies with the model, network, image count, resolution, and review brief.

The shim is a good fit for issues such as:

- UI clipping, overlap, spacing, alignment, typography, contrast, and visual
  regressions;
- before/after screenshot comparisons and iterative render reviews;
- rendered PDF, document, slide, or dashboard pages that already exist as local
  image files;
- high-resolution screenshots or small text that benefit from overview-plus-tile
  inspection;
- browser or Computer Use screenshots that can be saved to a local path without
  emitting pixels to the parent.

It is less suitable for latency-sensitive screenshot loops, exact pixel or
colorimetry measurements, hidden application or 3D-scene state, and images that
already entered the parent context. Concurrent nested runs were less reliable in
testing, so prefer one batched invocation (up to eight source images) or sequential
runs.

## Requirements

- macOS or Linux
- Python 3.10 or newer
- [Pillow](https://python-pillow.org/) for local image decoding and tiling
- An authenticated `codex` CLI available on `PATH`
- Permission to create a private temporary directory
- A parent environment that permits the nested Codex process to reach the service

The default worker model is `gpt-5.6-sol`. A caller may provide another single,
validated model identifier.

## Install

For a repository installation, ask Codex:

```text
Use $skill-installer to install the image-rollout-shim directory from this repository.
```

Install the Python dependency into the same `python3` environment Codex will use:

```bash
python3 -m pip install -r /absolute/path/to/checkout/image-rollout-shim/requirements.txt
```

For a manual user-level installation, link or copy the Skill into the current
Codex user Skill directory:

```bash
mkdir -p ~/.agents/skills
ln -s /absolute/path/to/checkout/image-rollout-shim ~/.agents/skills/image-rollout-shim
```

Codex normally detects Skill changes automatically. Restart it if the Skill does
not appear.

## Use

Explicit invocation:

```text
Use $image-rollout-shim to visually audit /absolute/path/to/screenshot.png.
Use thorough mode and focus on clipping, alignment, typography, and regressions.
```

Model override:

```text
Use $image-rollout-shim with model gpt-5.6-terra to compare these local renders.
```

Implicit invocation is enabled, so Codex may select the Skill whenever it would
otherwise inspect a local image with `view_image`. Because implicit Skill routing
is model behavior rather than a hard tool interceptor, explicitly invoke the Skill
when the isolation requirement is important.

For stronger repository-local guidance without installing a Hook, add this to the
repository's `AGENTS.md`:

```markdown
For every would-be `view_image` call on an absolute local image path, use
`$image-rollout-shim`. Do not retrieve or emit image bytes in the parent task. If
the shim cannot run, stop that visual inspection instead of falling back.
```

## Direct launcher smoke test

The Skill normally invokes the launcher itself. To test the launcher directly:

```bash
python3 image-rollout-shim/scripts/run_isolated_vision.py \
  --image /absolute/path/to/image.png <<'JSON'
{
  "objective": "Describe the visible layout and identify obvious defects.",
  "context": "Local smoke test.",
  "focus": ["layout", "legibility", "visual defects"],
  "questions": ["Are any elements clipped or overlapping?"],
  "mode": "thorough",
  "output_language": "English"
}
JSON
```

Successful stdout is one JSON object with `status: "ok"`, a structured `report`,
and non-image metadata. Errors are safe, stable JSON objects and never include the
raw child streams.

## Boundaries

This project does not:

- remove pixels that already entered the parent through a user attachment,
  `view_image`, Computer Use, a browser screenshot, or another image-bearing tool;
- automatically intercept every image-producing tool call;
- change OpenAI service-side processing or retention behavior;
- isolate the worker under a separate OS identity;
- guarantee that visual conclusions are correct or lossless.

See the full [isolation contract](image-rollout-shim/references/contract.md).

## Development

```bash
python3 -m pip install -r image-rollout-shim/requirements.txt
python3 -m unittest discover -s tests -p 'test_*.py' -v
python3 -m py_compile image-rollout-shim/scripts/run_isolated_vision.py
```

The unit suite uses a fake Codex executable; it does not upload fixtures or require
authentication. Live visual smoke tests are intentionally not run in GitHub
Actions.

## License

[MIT](LICENSE)

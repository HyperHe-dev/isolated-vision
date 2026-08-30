# Image Rollout Shim

English | [简体中文](README.zh-CN.md)

An experimental Codex Skill that sends local-image inspection to an ephemeral
`codex exec` worker and returns only a validated text report to the parent task.
Its purpose is to keep image bytes, Data URLs, base64, and raw worker output out
of the parent's rollout.

> [!IMPORTANT]
> This is a temporary, model-routed workaround—not an OS sandbox, a data-handling
> guarantee, or an OpenAI product. See [SECURITY.md](SECURITY.md) before using it
> with sensitive material.

## Why

This project mitigates a family of upstream Codex history/context issues in which
inline image data can be retained and handled again during later turns,
compaction, or transport:
[openai/codex#28316](https://github.com/openai/codex/issues/28316),
[openai/codex#24550](https://github.com/openai/codex/issues/24550),
[openai/codex#24388](https://github.com/openai/codex/issues/24388), and
[openai/codex#33024](https://github.com/openai/codex/issues/33024).

It only protects local images routed through the Skill *before* their pixels
reach the parent. It cannot clean an already bloated task or fix the upstream
behavior.

Local tests observed about 14 seconds for a simple worker call, about 31 seconds
for an implicit parent-to-worker flow, and 69–84 seconds for thorough three-image
reviews. A 90-image historical replay preserved the main visual findings while
correcting several overconfident claims. These are indicative results, not
portable benchmarks.

## How it works

1. The parent derives a visual brief from the current task.
2. The launcher validates the brief and local paths, preparing overview images
   and native-resolution tiles when needed.
3. An authenticated, ephemeral `codex exec --image` worker performs the review.
4. The launcher discards raw worker streams and returns only a schema-validated,
   image-free report and safe diagnostics.

The parent decides what to inspect and how to use the evidence; the worker only
performs the visual analysis.

## Install

Requirements: macOS or Linux, Python 3.10+, Pillow, and an authenticated `codex`
CLI on `PATH`. The nested process must be allowed to reach the Codex service.

Ask Codex to install the Skill directory from this repository:

```text
Use $skill-installer to install the image-rollout-shim directory from this repository.
```

Then install its Python dependency into the same `python3` environment Codex uses:

```bash
python3 -m pip install -r /absolute/path/to/checkout/image-rollout-shim/requirements.txt
```

Manual user-level installation also works:

```bash
mkdir -p ~/.agents/skills
ln -s /absolute/path/to/checkout/image-rollout-shim ~/.agents/skills/image-rollout-shim
```

## Use

```text
Use $image-rollout-shim to visually audit /absolute/path/to/screenshot.png.
Use thorough mode and focus on clipping, alignment, typography, and regressions.
```

The default worker model is `gpt-5.6-sol`; a caller may request another model:

```text
Use $image-rollout-shim with model gpt-5.6-terra to compare these local renders.
```

Implicit invocation is enabled, but Skill routing is model behavior rather than
a hard tool interceptor. When isolation matters, invoke it explicitly or add this
repository-local rule to `AGENTS.md`:

```markdown
For every would-be `view_image` call on an absolute local image path, use
`$image-rollout-shim`. Do not retrieve or emit image bytes in the parent task. If
the shim cannot run, stop that visual inspection instead of falling back.
```

## Good fits and limits

Good fits include UI defects and regressions, before/after comparisons, rendered
documents or dashboards, and high-resolution screenshots with small text.

It is less suitable for latency-sensitive screenshot loops, exact pixel or color
measurement, hidden application or 3D state, or images already present in the
parent context. Eight source images is a protocol ceiling, not a recommended batch
size: use the smallest comparison group that is semantically complete and process
independent groups sequentially.

The Skill does not intercept every image-producing tool, change service-side data
handling, isolate the worker under another OS identity, or guarantee correct or
lossless conclusions. See the full
[isolation contract](image-rollout-shim/references/contract.md).

## Development

```bash
python3 -m pip install -r image-rollout-shim/requirements.txt
python3 -m unittest discover -s tests -p 'test_*.py' -v
python3 -m py_compile image-rollout-shim/scripts/run_isolated_vision.py
```

Unit tests use a fake Codex executable and do not upload fixtures. Live visual
tests are intentionally excluded from GitHub Actions.

## License

[MIT](LICENSE)

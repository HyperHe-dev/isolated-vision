# Isolated Vision

English | [简体中文](README.zh-CN.md)

An experimental Codex Skill that routes local-image viewing through an
ephemeral `codex exec` worker and returns a validated text report. The parent
task continues from paths, task context, and visual observations. Image-bearing
worker output stays inside the isolated path.

> [!IMPORTANT]
> This is a temporary, model-routed workaround. It is not an OS sandbox, a
> data-handling guarantee, or an OpenAI product. Read [SECURITY.md](SECURITY.md)
> before using sensitive material.

## Why

This project is motivated by related Codex image-history and large-context
failure modes reported in
[openai/codex#28316](https://github.com/openai/codex/issues/28316),
[#24550](https://github.com/openai/codex/issues/24550),
[#24388](https://github.com/openai/codex/issues/24388), and
[#33024](https://github.com/openai/codex/issues/33024). Local testing with Codex
CLI `0.150.1` still reproduces the WebSocket connection issue. Images entering
the parent context are a significant trigger. Before the CLI update, compaction
cleared image content from the context.

The Skill only protects local images routed through it before their pixels reach
the parent; it cannot repair an already bloated task or fix the upstream
behavior.

Local tests took about 14 seconds for a simple worker call, 31 seconds for an
implicit parent-to-worker flow, and 69–84 seconds for a three-image run with
automatic detail preparation. A 90-image replay preserved the main findings
while correcting several overconfident claims. Treat these as indicative
results, not benchmarks.

## How it works

The parent supplies absolute local paths and a concise viewing purpose. The
launcher validates each source, creates a whole-image overview, adds
native-resolution detail tiles for large images, and starts an authenticated
ephemeral `codex exec --image` worker. Raw worker streams are discarded; only a
schema-validated text report and fixed diagnostics are returned. An optional job
ID supports coarse progress checks and terminal result recovery without rerunning
the visual task.

## Install

Requirements: macOS or Linux, Python 3.10+, Pillow, and an authenticated `codex`
CLI on `PATH`. The nested process must be able to reach the Codex service.

Ask Codex to install the Skill directory from this repository:

```text
Use $skill-installer to install the isolated-vision directory from this repository.
```

Then install Pillow into the same `python3` environment Codex uses:

```bash
python3 -m pip install -r /absolute/path/to/checkout/isolated-vision/requirements.txt
```

## Use

```text
Use $isolated-vision to view /absolute/path/to/screenshot.png and return the visual information relevant to the current task.
```

Image preparation is automatic. Use `--original-only` when each directly
supported original should be attached once without preparation. The default
worker model is `gpt-5.6-sol`; select another with `--model` when needed.

Skill routing is model behavior, not a hard tool interceptor. For automatic
project-level routing, add this rule to `AGENTS.md`:

```markdown
Whenever the task needs visual information from an absolute local image path,
route that path through `$isolated-vision` and continue from the returned text
observations. Keep parent-side image routing path-based.
```

When useful, the parent may show a stable original source during processing with
a Markdown image link. The Codex UI renders the preview while worker-private
temporary files remain inside the isolated path.

## Scope

- Good fits: UI feedback, before/after comparisons, rendered documents or
  dashboards, 3D renders, and high-resolution screenshots with small details.
- Poor fits: latency-sensitive loops, exact pixel/color measurement, hidden app
  or 3D state, and images already present in the parent context.
- Automatic overview and native-resolution tiling preserve useful visual detail,
  but model perception is not an exact pixel or color measurement. A request may
  contain up to eight source images and 48 private attachments.

See the [isolation contract](isolated-vision/references/contract.md) for the
full protocol and [SECURITY.md](SECURITY.md) for trust boundaries.

## Development

```bash
python3 -m pip install -r isolated-vision/requirements.txt
python3 -m unittest discover -s tests -p 'test_*.py' -v
python3 -m py_compile isolated-vision/scripts/vision.py
```

Unit tests use a fake Codex executable and do not upload fixtures. GitHub Actions
does not run live visual workers.

## License

[MIT](LICENSE)

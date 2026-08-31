# Image Rollout Shim

English | [简体中文](README.zh-CN.md)

An experimental Codex Skill that sends local-image review to an ephemeral
`codex exec` worker and returns a validated text report. The parent task receives
paths, instructions, and conclusions—not image bytes, Data URLs, base64, or raw
worker output.

> [!IMPORTANT]
> This is a temporary, model-routed workaround. It is not an OS sandbox, a
> data-handling guarantee, or an OpenAI product. Read [SECURITY.md](SECURITY.md)
> before using sensitive material.

## Why

This project mitigates Codex history/context problems reported in
[openai/codex#28316](https://github.com/openai/codex/issues/28316),
[#24550](https://github.com/openai/codex/issues/24550),
[#24388](https://github.com/openai/codex/issues/24388), and
[#33024](https://github.com/openai/codex/issues/33024). It only protects local
images routed through the Skill before their pixels reach the parent; it cannot
repair an already bloated task or fix the upstream behavior.

Local tests took about 14 seconds for a simple worker call, 31 seconds for an
implicit parent-to-worker flow, and 69–84 seconds for a thorough three-image
review. A 90-image replay preserved the main findings while correcting several
overconfident claims. Treat these as indicative results, not benchmarks.

## How it works

The parent writes a task-specific visual brief. The launcher validates local
paths, prepares overview images and native-resolution tiles when needed, then
starts an authenticated ephemeral `codex exec --image` worker. Raw worker streams
are discarded; only a schema-validated, image-free report and fixed diagnostics
are returned. An optional job ID supports coarse progress checks and terminal
result recovery without rerunning the review.

## Install

Requirements: macOS or Linux, Python 3.10+, Pillow, and an authenticated `codex`
CLI on `PATH`. The nested process must be able to reach the Codex service.

Ask Codex to install the Skill directory from this repository:

```text
Use $skill-installer to install the image-rollout-shim directory from this repository.
```

Then install Pillow into the same `python3` environment Codex uses:

```bash
python3 -m pip install -r /absolute/path/to/checkout/image-rollout-shim/requirements.txt
```

## Use

```text
Use $image-rollout-shim to visually audit /absolute/path/to/screenshot.png.
Use thorough mode and focus on clipping, alignment, typography, and regressions.
```

The default worker model is `gpt-5.6-sol`; name another model in the request when
needed.

Skill routing is model behavior, not a hard tool interceptor. For automatic
project-level routing, add this rule to `AGENTS.md`:

```markdown
For every would-be `view_image` call on an absolute local image path, use
`$image-rollout-shim`. Do not retrieve or emit image bytes in the parent task. If
the shim cannot run, stop that visual inspection instead of falling back.
```

When useful, the parent may give the user a normal file link to a stable original
source. It must not embed image syntax or expose worker-private temporary files.

## Scope

- Good fits: UI regressions, before/after comparisons, rendered documents or
  dashboards, and high-resolution screenshots with small details.
- Poor fits: latency-sensitive loops, exact pixel/color measurement, hidden app
  or 3D state, and images already present in the parent context.
- The Skill does not intercept every image-producing tool or guarantee correct,
  lossless conclusions. Eight source images is a ceiling, not a recommended batch.

See the [isolation contract](image-rollout-shim/references/contract.md) for the
full protocol and [SECURITY.md](SECURITY.md) for trust boundaries.

## Development

```bash
python3 -m pip install -r image-rollout-shim/requirements.txt
python3 -m unittest discover -s tests -p 'test_*.py' -v
python3 -m py_compile image-rollout-shim/scripts/run_isolated_vision.py
```

Unit tests use a fake Codex executable and do not upload fixtures. GitHub Actions
does not run live visual workers.

## License

[MIT](LICENSE)

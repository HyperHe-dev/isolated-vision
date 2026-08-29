# Security model

Image Rollout Shim is designed to reduce one specific kind of parent-rollout
exposure. It is not a general security boundary.

## Intended protection

When the parent routes an absolute local image path through the Skill before any
image-bearing tool call:

- the child receives the image through `codex exec --image`;
- the child session is launched with `--ephemeral`;
- child stdout and stderr are discarded;
- only a schema-validated JSON report is returned;
- Data URLs, base64-like payloads, image signatures, image-bearing keys, Markdown
  images, and HTML image tags are rejected;
- incomplete attachment coverage and malformed reports fail closed.

## Outside the boundary

- Skill selection is behavioral. There is no Hook that forcibly intercepts
  `view_image`.
- Images already attached to the parent or returned inline by another tool cannot
  be removed retroactively.
- The child uses the same operating-system account, Codex authentication, process
  environment, and locally readable filesystem permitted by its sandbox.
- The image is still sent through the normal Codex model path. `--ephemeral`
  concerns local session persistence; it does not change service-side data policy.
- The worker is instructed not to use tools or obey visible image text, but model
  instructions are not an OS-level control.
- Pillow decodes source images locally. Keep Pillow current and use an additional
  hardened sandbox for hostile or untrusted files.
- A text report can omit details, misread pixels, or make incorrect inferences.

Do not use this project as the sole control for secrets, regulated data, hostile
files, or environments where the child must not be able to read local data.

## Reporting a vulnerability

Prefer GitHub's private vulnerability-reporting feature when it is enabled for the
repository. Otherwise, open an issue containing only a minimal, non-sensitive
description and ask the maintainer for a private reporting channel. Never attach
sensitive images, transcripts, credentials, or raw rollout data to a public issue.

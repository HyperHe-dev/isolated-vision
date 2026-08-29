from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / "image-rollout-shim" / "scripts" / "run_isolated_vision.py"
DEFAULT_MODEL = "gpt-5.6-sol"


FAKE_CODEX = r'''#!/usr/bin/env python3
import json
import os
import sys
from pathlib import Path

args = sys.argv[1:]
required = ["exec", "--ephemeral", "--skip-git-repo-check", "--output-schema", "--output-last-message"]
if any(item not in args for item in required):
    raise SystemExit(91)
if args[args.index("--sandbox") + 1] != "read-only":
    raise SystemExit(92)
if args.count("--model") != 1:
    raise SystemExit(94)
model = args[args.index("--model") + 1]
expected_model = os.environ.get("FAKE_CODEX_EXPECT_MODEL")
if expected_model is not None and model != expected_model:
    raise SystemExit(95)
capture_path = os.environ.get("FAKE_CODEX_ARGS_CAPTURE")
if capture_path:
    Path(capture_path).write_text(json.dumps(args), encoding="utf-8")

prompt = sys.stdin.read()
if "[image-rollout-shim-worker:v1]" not in prompt:
    raise SystemExit(93)

request_line = next(line for line in prompt.splitlines() if line.startswith("REQUEST_JSON="))
manifest_line = next(line for line in prompt.splitlines() if line.startswith("ATTACHMENT_MANIFEST_JSON="))
request = json.loads(request_line.split("=", 1)[1])
manifest = json.loads(manifest_line.split("=", 1)[1])
source_count = len({item["source_image"] for item in manifest})

unsafe = os.environ.get("FAKE_CODEX_UNSAFE") == "1"
if os.environ.get("FAKE_CODEX_FAIL") == "1":
    print("data:image/png;base64,FAILURE-STDOUT-MUST-NOT-ESCAPE")
    print("iVBORw0KGgoFAILURE-STDERR-MUST-NOT-ESCAPE", file=sys.stderr)
    raise SystemExit(37)
summary = "data:image/png;base64,LEAK-MUST-NOT-ESCAPE" if unsafe else "Inspection completed."
report = {
    "schema_version": "1.0",
    "summary": summary,
    "findings": [],
    "answers": [],
    "uncertainties": [],
    "coverage": {
        "mode": request["mode"],
        "source_images": source_count,
        "attachments": len(manifest),
        "reviewed_regions": (
            [item["id"] for item in manifest[:-1]]
            if os.environ.get("FAKE_CODEX_INCOMPLETE") == "1"
            else [item["id"] for item in manifest]
        ),
        "limitations": []
    }
}
output_path = Path(args[args.index("--output-last-message") + 1])
output_path.write_text(json.dumps(report), encoding="utf-8")
print("data:image/png;base64,RAW-STDOUT-MUST-NOT-ESCAPE")
print("iVBORw0KGgoRAW-STDERR-MUST-NOT-ESCAPE", file=sys.stderr)
'''


class ShimTests(unittest.TestCase):
    def make_image(self, directory: Path, size: tuple[int, int] = (96, 64)) -> Path:
        path = directory / "fixture.png"
        Image.new("RGB", size, (24, 80, 140)).save(path)
        return path

    def make_fake_codex(self, directory: Path) -> Path:
        path = directory / "fake-codex"
        path.write_text(textwrap.dedent(FAKE_CODEX), encoding="utf-8")
        path.chmod(0o755)
        return path

    def run_shim(
        self,
        image: Path,
        fake_codex: Path,
        request: dict[str, object],
        *,
        unsafe: bool = False,
        fail: bool = False,
        incomplete: bool = False,
        model: str | None = None,
        expected_model: str | None = DEFAULT_MODEL,
        args_capture: Path | None = None,
    ) -> subprocess.CompletedProcess[str]:
        environment = os.environ.copy()
        environment["IMAGE_ROLLOUT_SHIM_CODEX"] = str(fake_codex)
        if unsafe:
            environment["FAKE_CODEX_UNSAFE"] = "1"
        if fail:
            environment["FAKE_CODEX_FAIL"] = "1"
        if incomplete:
            environment["FAKE_CODEX_INCOMPLETE"] = "1"
        if expected_model is not None:
            environment["FAKE_CODEX_EXPECT_MODEL"] = expected_model
        if args_capture is not None:
            environment["FAKE_CODEX_ARGS_CAPTURE"] = str(args_capture)
        command = [
            sys.executable,
            str(RUNNER),
            "--image",
            str(image),
            "--timeout",
            "30",
        ]
        if model is not None:
            command.extend(["--model", model])
        return subprocess.run(
            command,
            input=json.dumps(request),
            text=True,
            capture_output=True,
            env=environment,
            timeout=60,
            check=False,
        )

    def base_request(self, mode: str = "thorough") -> dict[str, object]:
        return {
            "objective": "Inspect the synthetic image.",
            "context": "Unit-test fixture.",
            "focus": ["coverage"],
            "questions": [],
            "mode": mode,
            "output_language": "English",
        }

    def test_raw_worker_streams_are_private(self) -> None:
        with tempfile.TemporaryDirectory() as name:
            directory = Path(name)
            result = self.run_shim(
                self.make_image(directory),
                self.make_fake_codex(directory),
                self.base_request(),
            )
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertEqual(result.stderr, "")
        self.assertNotIn("RAW-STDOUT", result.stdout)
        self.assertNotIn("RAW-STDERR", result.stdout)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["status"], "ok")
        self.assertFalse(payload["meta"]["raw_worker_output_forwarded"])
        self.assertEqual(payload["meta"]["effective_model"], DEFAULT_MODEL)

    def test_default_model_is_passed_to_worker(self) -> None:
        with tempfile.TemporaryDirectory() as name:
            directory = Path(name)
            result = self.run_shim(
                self.make_image(directory),
                self.make_fake_codex(directory),
                self.base_request(),
            )
        self.assertEqual(result.returncode, 0, result.stdout)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["meta"]["effective_model"], DEFAULT_MODEL)

    def test_explicit_model_is_passed_and_reported(self) -> None:
        with tempfile.TemporaryDirectory() as name:
            directory = Path(name)
            model = "provider/future-model:v2"
            result = self.run_shim(
                self.make_image(directory),
                self.make_fake_codex(directory),
                self.base_request(),
                model=model,
                expected_model=model,
            )
        self.assertEqual(result.returncode, 0, result.stdout)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["meta"]["effective_model"], model)

    def test_empty_model_falls_back_to_default(self) -> None:
        for model in ("", "   "):
            with self.subTest(model=repr(model)), tempfile.TemporaryDirectory() as name:
                directory = Path(name)
                result = self.run_shim(
                    self.make_image(directory),
                    self.make_fake_codex(directory),
                    self.base_request(),
                    model=model,
                )
                self.assertEqual(result.returncode, 0, result.stdout)
                payload = json.loads(result.stdout)
                self.assertEqual(payload["meta"]["effective_model"], DEFAULT_MODEL)

    def test_invalid_model_identifiers_are_rejected(self) -> None:
        invalid_models = (
            "--config",
            "gpt-5.6-sol --config model=x",
            "gpt-5.6-sol\n--model=other",
            "gpt-5.6-sol;touch-x",
            "model=value",
        )
        for model in invalid_models:
            with self.subTest(model=model), tempfile.TemporaryDirectory() as name:
                directory = Path(name)
                result = self.run_shim(
                    self.make_image(directory),
                    self.make_fake_codex(directory),
                    self.base_request(),
                    model=model,
                    expected_model=None,
                )
                self.assertEqual(result.returncode, 2)
                payload = json.loads(result.stdout)
                self.assertEqual(payload["error"]["code"], "invalid_model")

    def test_model_is_one_distinct_codex_argument(self) -> None:
        with tempfile.TemporaryDirectory() as name:
            directory = Path(name)
            capture = directory / "args.json"
            model = "vendor/model@2026-08-30"
            result = self.run_shim(
                self.make_image(directory),
                self.make_fake_codex(directory),
                self.base_request(),
                model=model,
                expected_model=model,
                args_capture=capture,
            )
            args = json.loads(capture.read_text(encoding="utf-8"))
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertEqual(args.count("--model"), 1)
        self.assertEqual(args[args.index("--model") + 1], model)

    def test_image_like_final_output_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as name:
            directory = Path(name)
            result = self.run_shim(
                self.make_image(directory),
                self.make_fake_codex(directory),
                self.base_request(),
                unsafe=True,
            )
        self.assertEqual(result.returncode, 2)
        self.assertNotIn("LEAK-MUST-NOT-ESCAPE", result.stdout)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["status"], "error")
        self.assertEqual(payload["error"]["code"], "unsafe_worker_output")

    def test_thorough_mode_privately_tiles_large_images(self) -> None:
        with tempfile.TemporaryDirectory() as name:
            directory = Path(name)
            result = self.run_shim(
                self.make_image(directory, (3500, 2200)),
                self.make_fake_codex(directory),
                self.base_request(),
            )
        self.assertEqual(result.returncode, 0, result.stdout)
        payload = json.loads(result.stdout)
        self.assertGreater(payload["meta"]["private_attachments"], 1)
        self.assertEqual(
            payload["meta"]["private_attachments"],
            len(payload["report"]["coverage"]["reviewed_regions"]),
        )

    def test_failed_worker_streams_do_not_escape(self) -> None:
        with tempfile.TemporaryDirectory() as name:
            directory = Path(name)
            result = self.run_shim(
                self.make_image(directory),
                self.make_fake_codex(directory),
                self.base_request(),
                fail=True,
            )
        self.assertEqual(result.returncode, 2)
        self.assertNotIn("FAILURE-STDOUT", result.stdout)
        self.assertNotIn("FAILURE-STDERR", result.stdout)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["error"]["code"], "worker_failed")

    def test_incomplete_region_coverage_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as name:
            directory = Path(name)
            result = self.run_shim(
                self.make_image(directory, (3500, 2200)),
                self.make_fake_codex(directory),
                self.base_request(),
                incomplete=True,
            )
        self.assertEqual(result.returncode, 2)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["error"]["code"], "incomplete_worker_coverage")

    def test_data_url_in_request_is_rejected_before_worker(self) -> None:
        with tempfile.TemporaryDirectory() as name:
            directory = Path(name)
            request = self.base_request()
            request["context"] = "data:image/png;base64,AAAA"
            result = self.run_shim(
                self.make_image(directory),
                self.make_fake_codex(directory),
                request,
            )
        self.assertEqual(result.returncode, 2)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["error"]["code"], "invalid_request")

    def test_missing_pillow_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as name:
            directory = Path(name)
            image = self.make_image(directory)
            result = subprocess.run(
                [
                    sys.executable,
                    "-S",
                    str(RUNNER),
                    "--image",
                    str(image),
                    "--timeout",
                    "30",
                ],
                input=json.dumps(self.base_request()),
                text=True,
                capture_output=True,
                timeout=60,
                check=False,
            )
        self.assertEqual(result.returncode, 2)
        self.assertEqual(result.stderr, "")
        payload = json.loads(result.stdout)
        self.assertEqual(payload["status"], "error")
        self.assertEqual(payload["error"]["code"], "missing_dependency")


if __name__ == "__main__":
    unittest.main()

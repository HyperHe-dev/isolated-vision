from __future__ import annotations

import importlib.util
import io
import json
import os
import subprocess
import sys
import tempfile
import textwrap
import time
import unittest
from unittest import mock
from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / "image-rollout-shim" / "scripts" / "run_isolated_vision.py"
LAUNCHER_SCHEMA = RUNNER.with_name("launcher-output.schema.json")
DEFAULT_MODEL = "gpt-5.6-sol"


FAKE_CODEX = r'''#!/usr/bin/env python3
import json
import os
import sys
import time
from pathlib import Path

args = sys.argv[1:]
required = ["exec", "--json", "--ephemeral", "--skip-git-repo-check", "--output-schema", "--output-last-message"]
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
schema_capture_path = os.environ.get("FAKE_CODEX_SCHEMA_CAPTURE")
if schema_capture_path:
    schema_path = Path(args[args.index("--output-schema") + 1])
    Path(schema_capture_path).write_text(schema_path.read_text(encoding="utf-8"), encoding="utf-8")

prompt = sys.stdin.read()
if "[image-rollout-shim-worker:v1]" not in prompt:
    raise SystemExit(93)

print(json.dumps({"type": "thread.started", "thread_id": "private-worker"}), flush=True)
print(json.dumps({"type": "turn.started"}), flush=True)

ready_path = os.environ.get("FAKE_CODEX_READY")
if ready_path:
    Path(ready_path).write_text(str(os.getpid()), encoding="utf-8")
sleep_seconds = float(os.environ.get("FAKE_CODEX_SLEEP_SECONDS", "0"))
if sleep_seconds:
    time.sleep(sleep_seconds)

request_line = next(line for line in prompt.splitlines() if line.startswith("REQUEST_JSON="))
manifest_line = next(line for line in prompt.splitlines() if line.startswith("ATTACHMENT_MANIFEST_JSON="))
request = json.loads(request_line.split("=", 1)[1])
manifest = json.loads(manifest_line.split("=", 1)[1])
source_count = len({item["source_image"] for item in manifest})

unsafe = os.environ.get("FAKE_CODEX_UNSAFE") == "1"
if os.environ.get("FAKE_CODEX_FAIL") == "1":
    print(json.dumps({"type": "error", "message": "private failure detail"}), flush=True)
    print("data:image/png;base64,FAILURE-STDOUT-MUST-NOT-ESCAPE")
    print("iVBORw0KGgoFAILURE-STDERR-MUST-NOT-ESCAPE", file=sys.stderr)
    raise SystemExit(37)
summary = "data:image/png;base64,LEAK-MUST-NOT-ESCAPE" if unsafe else "Inspection completed."
report = {
    "schema_version": "1.1",
    "summary": summary,
    "findings": [],
    "answers": [
        {
            "question_index": (
                len(request["questions"]) + 1
                if os.environ.get("FAKE_CODEX_BAD_QUESTION") == "1"
                else question_index
            ),
            "answer": "Synthetic answer.",
            "confidence": 0.9,
        }
        for question_index, _question in enumerate(request["questions"], start=1)
    ],
    "uncertainties": [],
    "coverage": {
        "mode": request["mode"],
        "source_images": source_count,
        "attachments": len(manifest) + (
            1 if os.environ.get("FAKE_CODEX_BAD_ATTACHMENT_COUNT") == "1" else 0
        ),
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
print(json.dumps({"type": "item.completed", "item": {"text": "data:image/png;base64,PRIVATE-EVENT"}}), flush=True)
print(json.dumps({"type": "turn.completed", "usage": {"input_tokens": 1}}), flush=True)
print("data:image/png;base64,RAW-STDOUT-MUST-NOT-ESCAPE")
print("iVBORw0KGgoRAW-STDERR-MUST-NOT-ESCAPE", file=sys.stderr)
'''


class ShimTests(unittest.TestCase):
    def load_runner(self) -> object:
        spec = importlib.util.spec_from_file_location(
            "image_rollout_shim_runner", RUNNER
        )
        self.assertIsNotNone(spec)
        self.assertIsNotNone(spec.loader)
        runner = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = runner
        spec.loader.exec_module(runner)
        return runner

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
        schema_capture: Path | None = None,
        bad_attachment_count: bool = False,
        bad_question: bool = False,
        job_id: str | None = None,
        job_root: Path | None = None,
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
        if schema_capture is not None:
            environment["FAKE_CODEX_SCHEMA_CAPTURE"] = str(schema_capture)
        if bad_attachment_count:
            environment["FAKE_CODEX_BAD_ATTACHMENT_COUNT"] = "1"
        if bad_question:
            environment["FAKE_CODEX_BAD_QUESTION"] = "1"
        if job_root is not None:
            environment["IMAGE_ROLLOUT_SHIM_JOB_ROOT"] = str(job_root)
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
        if job_id is not None:
            command.extend(["--job-id", job_id])
        return subprocess.run(
            command,
            input=json.dumps(request),
            text=True,
            capture_output=True,
            env=environment,
            timeout=60,
            check=False,
        )

    def run_job_command(
        self,
        command: str,
        job_id: str,
        job_root: Path,
    ) -> subprocess.CompletedProcess[str]:
        environment = os.environ.copy()
        environment["IMAGE_ROLLOUT_SHIM_JOB_ROOT"] = str(job_root)
        return subprocess.run(
            [
                sys.executable,
                str(RUNNER),
                command,
                "--job-id",
                job_id,
            ],
            text=True,
            capture_output=True,
            env=environment,
            timeout=15,
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
        self.assertEqual(set(payload), {"status", "report", "diagnostics"})
        diagnostics = payload["diagnostics"]
        self.assertEqual(diagnostics["effective_model"], DEFAULT_MODEL)
        launcher_schema = json.loads(LAUNCHER_SCHEMA.read_text(encoding="utf-8"))
        required_diagnostics = launcher_schema["$defs"]["diagnostics"]["required"]
        self.assertEqual(set(diagnostics), set(required_diagnostics))
        self.assertEqual(diagnostics["phase"], "completed")
        self.assertEqual(diagnostics["last_worker_event"], "turn_completed")
        self.assertGreaterEqual(diagnostics["worker_events_seen"], 4)
        self.assertNotIn("PRIVATE-EVENT", result.stdout)

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
        self.assertEqual(payload["diagnostics"]["effective_model"], DEFAULT_MODEL)

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
        self.assertEqual(payload["diagnostics"]["effective_model"], model)

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
                self.assertEqual(
                    payload["diagnostics"]["effective_model"], DEFAULT_MODEL
                )

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
                expected = "invalid_request" if model == "--config" else "invalid_model"
                self.assertEqual(payload["error"]["code"], expected)

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
        self.assertGreater(payload["diagnostics"]["private_attachments"], 1)
        self.assertEqual(
            payload["diagnostics"]["private_attachments"],
            len(payload["report"]["coverage"]["reviewed_regions"]),
        )

    def test_runtime_schema_binds_run_specific_counts_and_indices(self) -> None:
        with tempfile.TemporaryDirectory() as name:
            directory = Path(name)
            schema_capture = directory / "runtime-schema.json"
            request = self.base_request()
            request["questions"] = ["Is the fixture visually complete?"]
            result = self.run_shim(
                self.make_image(directory, (3500, 2200)),
                self.make_fake_codex(directory),
                request,
                schema_capture=schema_capture,
            )
            schema = json.loads(schema_capture.read_text(encoding="utf-8"))

        self.assertEqual(result.returncode, 0, result.stdout)
        payload = json.loads(result.stdout)
        attachment_count = payload["diagnostics"]["private_attachments"]
        properties = schema["properties"]
        image_index = properties["findings"]["items"]["properties"]["location"][
            "properties"
        ]["image_index"]
        coverage = properties["coverage"]["properties"]
        reviewed = coverage["reviewed_regions"]
        answers = properties["answers"]
        self.assertEqual(image_index["maximum"], 1)
        self.assertEqual(coverage["mode"]["enum"], ["thorough"])
        self.assertEqual(coverage["source_images"]["enum"], [1])
        self.assertEqual(coverage["attachments"]["enum"], [attachment_count])
        self.assertEqual(reviewed["minItems"], attachment_count)
        self.assertEqual(reviewed["maxItems"], attachment_count)
        self.assertEqual(len(reviewed["items"]["enum"]), attachment_count)
        self.assertEqual(answers["minItems"], 1)
        self.assertEqual(answers["maxItems"], 1)
        self.assertEqual(
            answers["items"]["properties"]["question_index"]["enum"],
            [1],
        )

    def test_invalid_report_identifies_safe_validation_rule(self) -> None:
        with tempfile.TemporaryDirectory() as name:
            directory = Path(name)
            result = self.run_shim(
                self.make_image(directory),
                self.make_fake_codex(directory),
                self.base_request(),
                bad_attachment_count=True,
            )

        self.assertEqual(result.returncode, 2)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["error"]["code"], "invalid_worker_output")
        self.assertEqual(
            payload["diagnostics"]["validation_rule"],
            "coverage_attachment_count",
        )
        self.assertNotIn("Inspection completed", result.stdout)

    def test_every_requested_question_must_be_answered_exactly_once(self) -> None:
        with tempfile.TemporaryDirectory() as name:
            directory = Path(name)
            request = self.base_request()
            request["questions"] = ["Is the fixture visually complete?"]
            result = self.run_shim(
                self.make_image(directory),
                self.make_fake_codex(directory),
                request,
                bad_question=True,
            )

        self.assertEqual(result.returncode, 2)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["error"]["code"], "invalid_worker_output")
        self.assertEqual(payload["diagnostics"]["validation_rule"], "answers")

    def test_sigterm_stops_worker_and_removes_private_workspace(self) -> None:
        with tempfile.TemporaryDirectory() as name:
            directory = Path(name)
            private_root = directory / "private-root"
            private_root.mkdir()
            ready_path = directory / "worker.pid"
            environment = os.environ.copy()
            environment["IMAGE_ROLLOUT_SHIM_CODEX"] = str(
                self.make_fake_codex(directory)
            )
            environment["FAKE_CODEX_EXPECT_MODEL"] = DEFAULT_MODEL
            environment["FAKE_CODEX_READY"] = str(ready_path)
            environment["FAKE_CODEX_SLEEP_SECONDS"] = "30"
            environment["TMPDIR"] = str(private_root)
            process = subprocess.Popen(
                [
                    sys.executable,
                    str(RUNNER),
                    "--image",
                    str(self.make_image(directory, (3500, 2200))),
                    "--timeout",
                    "30",
                ],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                env=environment,
            )
            self.assertIsNotNone(process.stdin)
            process.stdin.write(json.dumps(self.base_request()))
            process.stdin.close()
            process.stdin = None

            deadline = time.monotonic() + 10
            while not ready_path.is_file() and time.monotonic() < deadline:
                time.sleep(0.05)
            self.assertTrue(ready_path.is_file(), "worker did not start")
            worker_pid = int(ready_path.read_text(encoding="utf-8"))

            process.terminate()
            stdout, stderr = process.communicate(timeout=15)
            payload = json.loads(stdout)
            self.assertEqual(process.returncode, 2)
            self.assertEqual(stderr, "")
            self.assertEqual(payload["error"]["code"], "interrupted")
            self.assertEqual(list(private_root.glob("image-rollout-shim-*")), [])

            deadline = time.monotonic() + 5
            worker_alive = True
            while worker_alive and time.monotonic() < deadline:
                try:
                    os.kill(worker_pid, 0)
                except ProcessLookupError:
                    worker_alive = False
                else:
                    time.sleep(0.05)
            self.assertFalse(worker_alive, "worker survived launcher termination")

    def test_job_result_can_be_collected_after_the_run_session_is_gone(self) -> None:
        with tempfile.TemporaryDirectory() as name:
            directory = Path(name)
            job_root = directory / "jobs"
            job_id = "recoverable-run-01"
            result = self.run_shim(
                self.make_image(directory),
                self.make_fake_codex(directory),
                self.base_request(),
                job_id=job_id,
                job_root=job_root,
            )
            status_result = self.run_job_command("status", job_id, job_root)
            collect_result = self.run_job_command("collect", job_id, job_root)

            job_directory = job_root / job_id
            self.assertEqual(oct(job_directory.stat().st_mode & 0o777), "0o700")
            self.assertEqual(
                oct((job_directory / "status.json").stat().st_mode & 0o777),
                "0o600",
            )
            self.assertEqual(
                oct((job_directory / "result.json").stat().st_mode & 0o777),
                "0o600",
            )

            cleanup_result = self.run_job_command("cleanup", job_id, job_root)
            self.assertFalse(job_directory.exists())

        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertEqual(status_result.returncode, 0, status_result.stdout)
        status = json.loads(status_result.stdout)
        self.assertEqual(status["status"], "ok")
        self.assertEqual(status["state"], "succeeded")
        self.assertEqual(status["phase"], "completed")
        self.assertGreaterEqual(status["elapsed_ms"], 0)
        self.assertNotIn("result_ready", status)
        self.assertNotIn("idle_ms", status)
        self.assertNotIn("fixture.png", status_result.stdout)
        self.assertNotIn("PRIVATE-EVENT", status_result.stdout)
        self.assertEqual(collect_result.returncode, 0, collect_result.stdout)
        self.assertEqual(json.loads(collect_result.stdout), json.loads(result.stdout))
        self.assertEqual(cleanup_result.returncode, 0, cleanup_result.stdout)

    def test_live_job_status_and_pending_collect_are_content_free(self) -> None:
        with tempfile.TemporaryDirectory() as name:
            directory = Path(name)
            private_root = directory / "private-root"
            private_root.mkdir()
            job_root = directory / "jobs"
            job_id = "live-run-01"
            ready_path = directory / "worker.pid"
            environment = os.environ.copy()
            environment["IMAGE_ROLLOUT_SHIM_CODEX"] = str(
                self.make_fake_codex(directory)
            )
            environment["FAKE_CODEX_EXPECT_MODEL"] = DEFAULT_MODEL
            environment["FAKE_CODEX_READY"] = str(ready_path)
            environment["FAKE_CODEX_SLEEP_SECONDS"] = "30"
            environment["IMAGE_ROLLOUT_SHIM_JOB_ROOT"] = str(job_root)
            environment["TMPDIR"] = str(private_root)
            process = subprocess.Popen(
                [
                    sys.executable,
                    str(RUNNER),
                    "--image",
                    str(self.make_image(directory)),
                    "--timeout",
                    "30",
                    "--job-id",
                    job_id,
                ],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                env=environment,
            )
            self.assertIsNotNone(process.stdin)
            process.stdin.write(json.dumps(self.base_request()))
            process.stdin.close()
            process.stdin = None

            deadline = time.monotonic() + 10
            while not ready_path.is_file() and time.monotonic() < deadline:
                time.sleep(0.05)
            self.assertTrue(ready_path.is_file(), "worker did not start")

            status_result = self.run_job_command("status", job_id, job_root)
            pending_result = self.run_job_command("collect", job_id, job_root)
            premature_cleanup = self.run_job_command("cleanup", job_id, job_root)
            status = json.loads(status_result.stdout)
            pending = json.loads(pending_result.stdout)

            self.assertEqual(status_result.returncode, 0, status_result.stdout)
            self.assertEqual(status["state"], "running")
            self.assertEqual(status["phase"], "worker")
            self.assertGreaterEqual(status["worker_events_seen"], 2)
            self.assertEqual(status["last_worker_event"], "turn_started")
            self.assertEqual(pending_result.returncode, 3, pending_result.stdout)
            self.assertEqual(pending["status"], "pending")
            self.assertEqual(premature_cleanup.returncode, 2)
            self.assertEqual(
                json.loads(premature_cleanup.stdout)["error"]["code"],
                "job_still_running",
            )
            for output in (status_result.stdout, pending_result.stdout):
                self.assertNotIn("fixture.png", output)
                self.assertNotIn("PRIVATE-EVENT", output)
                self.assertNotIn("data:image", output)

            process.terminate()
            stdout, stderr = process.communicate(timeout=15)
            self.assertEqual(stderr, "")
            self.assertEqual(json.loads(stdout)["error"]["code"], "interrupted")

            terminal_status = json.loads(
                self.run_job_command("status", job_id, job_root).stdout
            )
            collected = self.run_job_command("collect", job_id, job_root)
            self.assertEqual(terminal_status["state"], "interrupted")
            self.assertEqual(json.loads(collected.stdout)["error"]["code"], "interrupted")
            self.run_job_command("cleanup", job_id, job_root)

    def test_job_identifier_cannot_escape_the_job_root(self) -> None:
        with tempfile.TemporaryDirectory() as name:
            directory = Path(name)
            job_root = directory / "jobs"
            result = self.run_shim(
                self.make_image(directory),
                self.make_fake_codex(directory),
                self.base_request(),
                job_id="../escape",
                job_root=job_root,
            )
        self.assertEqual(result.returncode, 2)
        self.assertEqual(json.loads(result.stdout)["error"]["code"], "invalid_job")

    def test_terminal_job_state_cannot_regress_to_running(self) -> None:
        runner = self.load_runner()
        with tempfile.TemporaryDirectory() as name:
            job_root = Path(name) / "jobs"
            with mock.patch.dict(
                os.environ,
                {"IMAGE_ROLLOUT_SHIM_JOB_ROOT": str(job_root)},
            ):
                diagnostics = runner.RunDiagnostics(phase="worker")
                controller = runner.JobController.create("terminal-run-01")
                controller.update(diagnostics)
                diagnostics.phase = "completed"
                controller.finish(
                    {"status": "ok"},
                    diagnostics,
                    state="succeeded",
                )

                diagnostics.phase = "worker"
                diagnostics.worker_events_seen += 1
                diagnostics.last_worker_event = "item_activity"
                controller.update(diagnostics)
                status = runner.read_job_status("terminal-run-01")

        self.assertEqual(status["state"], "succeeded")
        self.assertEqual(status["phase"], "completed")
        self.assertEqual(status["worker_events_seen"], 0)

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
        self.assertEqual(payload["diagnostics"]["phase"], "worker")
        self.assertEqual(payload["diagnostics"]["last_worker_event"], "error")

    def test_complete_report_is_recovered_after_worker_timeout(self) -> None:
        runner = self.load_runner()

        with tempfile.TemporaryDirectory() as name:
            directory = Path(name)
            image = self.make_image(directory)
            source = runner.SourceImage(image, 96, 64, "PNG", "Fixture", image.stat().st_size)
            attachment = runner.Attachment(
                image,
                {
                    "id": "image-1-overview",
                    "attachment_index": 1,
                    "source_image": 1,
                    "label": "Fixture",
                    "kind": "overview",
                    "original_size": [96, 64],
                    "region_pixels": [0, 0, 96, 64],
                },
            )
            request = self.base_request()
            report = {
                "schema_version": "1.1",
                "summary": "Recovered complete report.",
                "findings": [],
                "answers": [],
                "uncertainties": [],
                "coverage": {
                    "mode": "thorough",
                    "source_images": 1,
                    "attachments": 1,
                    "reviewed_regions": ["image-1-overview"],
                    "limitations": [],
                },
            }

            class TimedOutProcess:
                def __init__(self, command: list[str], **_: object) -> None:
                    self.pid = 424242
                    self.returncode = None
                    self.stdin = io.BytesIO()
                    self.stdout = io.BytesIO(
                        b'{"type":"thread.started"}\n{"type":"turn.started"}\n'
                    )
                    output_path = Path(
                        command[command.index("--output-last-message") + 1]
                    )
                    output_path.write_text(json.dumps(report), encoding="utf-8")

                def wait(self, timeout: int | None = None) -> int:
                    if timeout is not None:
                        raise subprocess.TimeoutExpired("fake-codex", timeout)
                    self.returncode = -9
                    return self.returncode

            diagnostics = runner.RunDiagnostics(
                timeout_seconds=30,
                effective_model=DEFAULT_MODEL,
                reasoning_effort="high",
            )
            with (
                mock.patch.object(runner.shutil, "which", return_value="/fake/codex"),
                mock.patch.object(runner.subprocess, "Popen", TimedOutProcess),
                mock.patch.object(runner.os, "killpg"),
            ):
                result = runner.run_worker(
                    "worker prompt",
                    [attachment],
                    DEFAULT_MODEL,
                    "high",
                    30,
                    directory,
                    RUNNER.with_name("report.schema.json"),
                    diagnostics,
                )

            validated = runner.validate_report(
                result.report, request, [source], [attachment]
            )
            diagnostics.report_recovered_after_timeout = result.recovered_after_timeout

        self.assertEqual(validated["summary"], "Recovered complete report.")
        self.assertTrue(result.recovered_after_timeout)
        self.assertTrue(diagnostics.final_report_present)
        self.assertTrue(diagnostics.report_recovered_after_timeout)
        self.assertEqual(diagnostics.worker_exit_code, -9)
        self.assertEqual(diagnostics.last_worker_event, "turn_started")

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

    def test_markup_like_request_text_is_allowed_without_being_echoed(self) -> None:
        with tempfile.TemporaryDirectory() as name:
            directory = Path(name)
            request = self.base_request()
            request["context"] = "Review an <img> element and ![preview](render.png)."
            request["questions"] = ["Is the ![preview](render.png) visible?"]
            result = self.run_shim(
                self.make_image(directory),
                self.make_fake_codex(directory),
                request,
            )

        self.assertEqual(result.returncode, 0, result.stdout)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["report"]["answers"][0]["question_index"], 1)
        self.assertNotIn("![preview]", result.stdout)
        self.assertNotIn("<img>", result.stdout)

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

"""Exercise the root test runner without installing dependencies or using Docker.

Run with: python3 -m unittest discover -s tests -p test_run_tests.py
"""

import os
from pathlib import Path
import subprocess
import tempfile
import unittest


RUNNER = Path(__file__).resolve().parents[1] / "run-tests.sh"


class TestRunTests(unittest.TestCase):
    def run_script(self, docker, fail_match="", missing_directory=None):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            binaries = root / "bin"
            binaries.mkdir()
            for name in ("api", "ui"):
                if name != missing_directory:
                    (root / name).mkdir()
            names = ["docker-compose"] if docker else ["pip", "pytest", "npm"]
            for name in names:
                command = binaries / name
                command.write_text(
                    "#!/bin/sh\n"
                    f"printf '%s\\n' '{name}' >> \"$COMMAND_LOG\"\n"
                    'if [ -n "$FAIL_MATCH" ]; then\n'
                    '  case "$0 $*" in *"$FAIL_MATCH"*) exit 7 ;; esac\n'
                    "fi\n"
                    "exit 0\n"
                )
                command.chmod(0o755)
            log = root / "commands.log"
            result = subprocess.run(
                ["/bin/bash", str(RUNNER)],
                cwd=root,
                env={
                    **os.environ,
                    "PATH": str(binaries),
                    "FAIL_MATCH": fail_match,
                    "COMMAND_LOG": str(log),
                },
                capture_output=True,
                text=True,
                timeout=10,
            )
            calls = log.read_text().splitlines() if log.exists() else []
            return result, calls

    def test_failures_stop_runner_and_propagate_exit_status(self):
        cases = {
            True: ["api pip install", "api pytest", "ui npm install", "ui npm run test"],
            False: ["pip install", "pytest tests/test_working.py", "npm install", "npm run test"],
        }
        for docker, failures in cases.items():
            for stage, failure in enumerate(failures, start=1):
                with self.subTest(docker=docker, failure=failure):
                    result, calls = self.run_script(docker, failure)
                    self.assertEqual(result.returncode, 7, result.stdout + result.stderr)
                    self.assertEqual(len(calls), stage)
                    self.assertNotIn("All tests completed!", result.stdout)

    def test_success_runs_both_suites(self):
        for docker in (False, True):
            with self.subTest(docker=docker):
                result, calls = self.run_script(docker)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(len(calls), 4)
                self.assertIn("All tests completed!", result.stdout)

    def test_missing_test_directory_fails(self):
        for name in ("api", "ui"):
            with self.subTest(directory=name):
                result, _ = self.run_script(False, missing_directory=name)
                self.assertNotEqual(result.returncode, 0)
                self.assertNotIn("All tests completed!", result.stdout)


if __name__ == "__main__":
    unittest.main()

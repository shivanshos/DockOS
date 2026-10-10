import importlib.util
from pathlib import Path
import subprocess
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location("validator", Path(__file__).parents[1] / "scripts/validate_trial.py")
validator = importlib.util.module_from_spec(spec)
spec.loader.exec_module(validator)


class DiagnosticsTests(unittest.TestCase):
    def test_mode_requires_explicit_field(self):
        self.assertEqual(validator.sync_mode("Sync mode: pull-only\n"), "pull-only")
        self.assertEqual(validator.sync_mode("  Sync mode: bidirectional\n"), "bidirectional")
        self.assertIsNone(validator.sync_mode("recommended: pull-only"))
        self.assertIsNone(validator.sync_mode("Sync mode: unknown"))
        self.assertEqual(validator.sync_mode("\x1b[32mSync mode: pull-only\x1b[0m\n"), "pull-only")

    def test_timeout_becomes_non_success(self):
        with patch.object(validator.subprocess, "run", side_effect=subprocess.TimeoutExpired("test", 1)):
            self.assertEqual(validator.command(["test"], timeout=1), (124, ""))

    def test_child_errors_are_not_printed(self):
        result = subprocess.CompletedProcess(["test"], 1, stdout="private account data", stderr="secret")
        with patch.object(validator.subprocess, "run", return_value=result), patch("builtins.print") as printer:
            rc, _ = validator.command(["test"])
        self.assertEqual(rc, 1)
        printer.assert_not_called()


if __name__ == "__main__":
    unittest.main()

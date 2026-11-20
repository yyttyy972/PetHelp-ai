import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


CONFIG_PATH = Path(__file__).resolve().parents[1] / "app" / "config.py"


class JWTSecretConfigTests(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.backend_root = Path(self.temporary_directory.name) / "backend"
        app_directory = self.backend_root / "app"
        app_directory.mkdir(parents=True)
        shutil.copy2(CONFIG_PATH, app_directory / "config.py")

        self.environment = os.environ.copy()
        self.environment.pop("JWT_SECRET", None)
        self.environment.pop("APP_ENV", None)
        self.environment["PYTHONPATH"] = str(self.backend_root)

    def tearDown(self):
        self.temporary_directory.cleanup()

    @property
    def secret_path(self):
        return self.backend_root / ".runtime" / "jwt_secret"

    def run_config(self, code, *, environment=None):
        return subprocess.run(
            [sys.executable, "-c", code],
            cwd=self.backend_root,
            env=environment or self.environment,
            capture_output=True,
            text=True,
            timeout=10,
        )

    def secret_digest(self):
        result = self.run_config(
            "import hashlib; import app.config as c; "
            "print(hashlib.sha256(c.JWT_SECRET.encode()).hexdigest())"
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        return result.stdout.strip()

    def test_first_start_generates_valid_secret(self):
        result = self.run_config(
            "import app.config as c; print(len(c.JWT_SECRET) >= 32)"
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), "True")
        self.assertGreaterEqual(len(self.secret_path.read_text(encoding="utf-8")), 32)

    def test_second_process_reads_same_secret(self):
        first_digest = self.secret_digest()
        second_digest = self.secret_digest()

        self.assertEqual(first_digest, second_digest)

    def test_existing_valid_secret_is_unchanged(self):
        existing = "existing-local-secret-" + "x" * 32
        self.secret_path.parent.mkdir(parents=True)
        self.secret_path.write_text(existing, encoding="utf-8")

        result = self.run_config(
            "import app.config as c; print(c.JWT_SECRET.startswith('existing-local'))"
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), "True")
        self.assertEqual(self.secret_path.read_text(encoding="utf-8"), existing)

    def test_empty_legacy_secret_is_repaired(self):
        self.secret_path.parent.mkdir(parents=True)
        self.secret_path.write_text("", encoding="utf-8")

        result = self.run_config(
            "import app.config as c; print(len(c.JWT_SECRET) >= 32)"
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), "True")
        self.assertGreaterEqual(len(self.secret_path.read_text(encoding="utf-8")), 32)

    def test_concurrent_first_start_returns_same_secret(self):
        command = [
            sys.executable,
            "-c",
            "import hashlib; import app.config as c; "
            "print(hashlib.sha256(c.JWT_SECRET.encode()).hexdigest())",
        ]
        processes = [
            subprocess.Popen(
                command,
                cwd=self.backend_root,
                env=self.environment,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            for _ in range(2)
        ]
        results = [process.communicate(timeout=10) for process in processes]

        self.assertTrue(all(process.returncode == 0 for process in processes), results)
        self.assertEqual(results[0][0].strip(), results[1][0].strip())
        self.assertFalse(self.secret_path.with_name("jwt_secret.lock").exists())
        self.assertFalse(self.secret_path.with_name("jwt_secret.tmp").exists())

    def test_explicit_environment_secret_has_priority(self):
        environment = self.environment.copy()
        environment["JWT_SECRET"] = "E" * 32

        result = self.run_config(
            "import os; import app.config as c; "
            "print(c.JWT_SECRET == os.environ['JWT_SECRET'])",
            environment=environment,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), "True")
        self.assertFalse(self.secret_path.exists())

    def test_production_requires_explicit_secret(self):
        environment = self.environment.copy()
        environment["APP_ENV"] = "production"

        result = self.run_config("import app.config", environment=environment)

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("explicitly configured in production", result.stderr)
        self.assertFalse(self.secret_path.exists())


if __name__ == "__main__":
    unittest.main()

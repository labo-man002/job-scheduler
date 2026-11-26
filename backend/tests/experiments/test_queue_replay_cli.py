import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from app.experiments import __main__ as cli

ROOT = Path(__file__).resolve().parents[3]
ORACLE = ROOT / "examples" / "queue-replay" / "oracle.json"


def run_cli(scenario, *args, env=None):
    return subprocess.run(
        [sys.executable, "-m", "app.experiments", str(scenario), *args],
        cwd=ROOT / "backend",
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


def test_stdout_uses_immutable_input_bytes_and_does_not_load_database(tmp_path):
    invalid_database_env = {**os.environ, "DATABASE_PORT": "unusable-database-port"}
    reformatted = tmp_path / "reformatted.json"
    original_bytes = ORACLE.read_bytes()
    reformatted_bytes = json.dumps(json.loads(original_bytes)).encode()
    reformatted.write_bytes(reformatted_bytes)

    original = run_cli(ORACLE, env=invalid_database_env)
    updated = run_cli(reformatted, env=invalid_database_env)

    assert original.returncode == updated.returncode == 0, (original.stderr, updated.stderr)
    original_report, updated_report = (json.loads(result.stdout) for result in (original, updated))
    assert original_report["scenario_sha256"] == hashlib.sha256(original_bytes).hexdigest()
    assert updated_report["scenario_sha256"] == hashlib.sha256(reformatted_bytes).hexdigest()
    assert original_report.pop("scenario_sha256") != updated_report.pop("scenario_sha256")
    assert original_report == updated_report
    assert "27/28" in original.stderr


def test_rejects_output_that_aliases_scenario(tmp_path):
    scenario = tmp_path / "scenario.json"
    original = ORACLE.read_bytes()
    scenario.write_bytes(original)
    alias = tmp_path / "output.json"
    alias.hardlink_to(scenario)

    result = run_cli(scenario, "--output", str(alias))

    assert result.returncode == 2
    assert "report output must differ from the scenario path" in result.stderr
    assert scenario.read_bytes() == alias.read_bytes() == original


def test_failed_atomic_write_keeps_existing_report_and_cleans_temporary_file(tmp_path, monkeypatch):
    output = tmp_path / "report.json"
    output.write_text('{"existing": true}\n', encoding="utf-8")

    def failed_replace(self, target):
        assert self.parent == target.parent
        assert target.read_text(encoding="utf-8") == '{"existing": true}\n'
        assert self.read_text(encoding="utf-8") == '{"new": true}\n'
        raise OSError("replace failed")

    monkeypatch.setattr(Path, "replace", failed_replace)

    with pytest.raises(OSError, match="replace failed"):
        cli.write_report(output, '{"new": true}\n')

    assert output.read_text(encoding="utf-8") == '{"existing": true}\n'
    assert list(tmp_path.iterdir()) == [output]


@pytest.mark.skipif(shutil.which("git") is None, reason="requires Git")
def test_git_provenance_requires_committed_cli_in_its_own_checkout(tmp_path, monkeypatch):
    repo = tmp_path / "repo"
    nested_source = repo / "export" / "backend" / "app" / "experiments" / "__main__.py"
    nested_source.parent.mkdir(parents=True)
    nested_source.write_text("# exported source\n", encoding="utf-8")

    def git(*args):
        return subprocess.check_output(["git", *args], cwd=repo, text=True).strip()

    git("init", "-q")
    git("add", ".")
    git("-c", "user.name=Replay Test", "-c", "user.email=replay-test@example.com", "commit", "-qm", "Set baseline")
    monkeypatch.setattr(cli, "__file__", str(nested_source))
    assert cli.git_provenance() == {"git_sha": None, "worktree_dirty": None}

    source = repo / "backend" / "app" / "experiments" / "__main__.py"
    source.parent.mkdir(parents=True)
    source.write_text("# untracked source\n", encoding="utf-8")
    monkeypatch.setattr(cli, "__file__", str(source))
    assert cli.git_provenance() == {"git_sha": None, "worktree_dirty": None}
    git("add", ".")
    git("-c", "user.name=Replay Test", "-c", "user.email=replay-test@example.com", "commit", "-qm", "Track source")
    head = git("rev-parse", "HEAD")

    monkeypatch.setenv("GIT_DIR", str(tmp_path / "other.git"))
    assert cli.git_provenance() == {"git_sha": head, "worktree_dirty": False}
    source.write_text("# edited source\n", encoding="utf-8")
    assert cli.git_provenance() == {"git_sha": head, "worktree_dirty": True}

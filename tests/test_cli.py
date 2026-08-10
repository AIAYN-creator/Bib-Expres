import subprocess
import sys


def test_version():
    result = subprocess.run(
        [sys.executable, "-m", "bib_expres.cli", "--version"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "0.1.0" in result.stdout

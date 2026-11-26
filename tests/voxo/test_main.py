import sys

import pytest

from voxo.__main__ import main


class TestMain:
    def test_version(self, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch) -> None:
        """`--version` prints the name of the command and a version."""
        monkeypatch.setattr(sys, "argv", ["voxo", "--version"])
        with pytest.raises(SystemExit):
            main()
        assert capsys.readouterr().out.startswith("voxo ")

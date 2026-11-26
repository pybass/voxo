import pytest

from voxo.__main__ import main


class TestMain:
    def test_says_not_written(self, capsys: pytest.CaptureFixture[str]) -> None:
        """The command says the service is not written yet."""
        main()
        assert "not written yet" in capsys.readouterr().out

"""tests that it runs"""

from click.testing import CliRunner

from splunk_downloader import cli


def test_cli_runs() -> None:
    """tests that it works"""

    runner = CliRunner()
    result = runner.invoke(cli, ["--latest", "-o", "linux", "forwarder"])
    assert result
    print(result.output)

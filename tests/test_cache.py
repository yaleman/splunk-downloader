from pathlib import Path
from unittest.mock import Mock

import pytest

from splunk_downloader import SplunkDownloader
from splunk_downloader.constants import URLS


@pytest.mark.parametrize("application", ["enterprise", "forwarder"])
def test_cached_release_pages_remain_distinct(tmp_path: Path, application: str) -> None:
    downloader = SplunkDownloader(cache=True)
    downloader.session.get = Mock(
        side_effect=[
            Mock(content=b'<a class="splunk-btn" data-link="older"></a>'),
            Mock(content=b'<a class="splunk-btn" data-link="current"></a>'),
        ]
    )
    cache_path = tmp_path / "cache"
    previous_url = URLS[application]
    current_url = URLS[f"{application}_current"]

    for _ in range(2):
        assert downloader.get_and_parse(previous_url, cache_path) == ["older"]
        assert downloader.get_and_parse(current_url, cache_path) == ["current"]

    assert downloader.session.get.call_count == 2
    assert len(list(cache_path.iterdir())) == 2
    assert list(tmp_path.iterdir()) == [cache_path]


def test_uncached_request_does_not_access_cache(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    downloader = SplunkDownloader(cache=False)
    downloader.session.get = Mock(
        return_value=Mock(content=b'<a class="splunk-btn" data-link="live"></a>')
    )
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("builtins.open", Mock(side_effect=PermissionError))
    monkeypatch.setattr(Path, "mkdir", Mock(side_effect=PermissionError))

    assert downloader.get_and_parse(URLS["enterprise"]) == ["live"]
    assert list(tmp_path.iterdir()) == []


def test_livehybrid_creates_cache_after_uncached_request(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    downloader = SplunkDownloader(cache=False)
    data = (
        b"enterprise\t10.0.0\thash\t"
        b"linux/splunk-10.0.0-hash-linux-x86_64.tgz\n"
    )
    downloader.session.get = Mock(
        side_effect=[Mock(content=b"<html></html>"), Mock(content=data)]
    )
    monkeypatch.chdir(tmp_path)

    assert downloader.get_and_parse(URLS["enterprise"]) == []
    assert not (tmp_path / "cache").exists()

    links = list(downloader.parse_livehybrid())
    assert len(links) == 1
    assert links[0].url == (
        "https://download.splunk.com/products/splunk/releases/10.0.0/"
        "linux/splunk-10.0.0-hash-linux-x86_64.tgz"
    )
    assert (tmp_path / "cache" / "livehybrid.tsv").read_bytes() == data
    assert list(downloader.parse_livehybrid()) == links
    assert downloader.session.get.call_count == 2

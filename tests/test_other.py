import logging
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import pytest
import requests.exceptions
from loguru import logger

from splunk_downloader import SplunkDownloader, get_data_from_url
from splunk_downloader.constants import URLS


@pytest.fixture
def downloader() -> SplunkDownloader:
    return SplunkDownloader(cache=False)


def test_download_page(downloader: SplunkDownloader) -> None:

    downloader.download_page("https://yaleman.org", None)

    with tempfile.NamedTemporaryFile(delete=False) as temp_file:
        downloader.download_page("https://yaleman.org", Path(temp_file.name))


def test_get_and_parse(downloader: SplunkDownloader) -> None:
    logging.basicConfig(level=logging.INFO)
    with pytest.raises(ValueError):
        downloader.get_and_parse("invalid_url", cached=True, cache_path=None)

    with tempfile.TemporaryDirectory() as temp_dir:
        cache_path = Path(temp_dir) / "asdfasfasldkfjhaslfkhjdsaflksdhjf"
        downloader.get_and_parse(
            "https://example.com",
            cached=True,
            cache_path=cache_path,
        )
        assert cache_path.exists()

    def _test_get_and_parse(url: str, cached: bool, with_temp_dir: bool) -> None:
        if with_temp_dir:
            with tempfile.TemporaryDirectory() as temp_dir:
                downloader.get_and_parse(url, cached=cached, cache_path=Path(temp_dir))
        else:
            downloader.get_and_parse(url, cached=cached, cache_path=None)

    tasks = []
    try:
        for url in list(URLS.values()):
            for cached in [True, False]:
                # Test with a temporary directory
                tasks.append((_test_get_and_parse, url, cached, True))
                tasks.append((_test_get_and_parse, url, cached, False))
    except requests.exceptions.ReadTimeout:
        print("ReadTimeout occurred, can't do much about that...", file=sys.stderr)
    except requests.exceptions.HTTPError as http_error:
        if http_error.errno == 500:
            print("HTTPError 500 occurred", file=sys.stderr)
        else:
            print("HTTPError occurred, can't do much about that...", file=sys.stderr)
    # Run all tasks in parallel
    with ThreadPoolExecutor(thread_name_prefix="splunk_downloader") as executor:
        futures = [executor.submit(func, *args) for func, *args in tasks]  # ty: ignore[invalid-argument-type]
        for future in as_completed(futures):
            # This will raise any exceptions that occurred in the threads
            try:
                future.result()
            except requests.exceptions.ReadTimeout as timeout_error:
                logger.error("ReadTimeout occurred: {}", timeout_error)
                continue
            except requests.exceptions.HTTPError as http_error:
                if http_error.response.status_code == 500:
                    logger.error(
                        "HTTPError 500 occurred for {}, ignoring",
                        http_error.request.url,
                    )
                else:
                    raise requests.exceptions.HTTPError from http_error


def test_cache_path_is_file(downloader: SplunkDownloader) -> None:
    with pytest.raises(ValueError, match="is not a directory"):
        downloader.get_and_parse(
            "https://example.com",
            cache_path=Path(__file__),
            cached=True,
        )


def test_get_data_from_url() -> None:
    with pytest.raises(ValueError, match="Couldn't get version from url"):
        get_data_from_url("invalid_url")

    test_with_no_package = "/releases/version/os/"
    assert get_data_from_url(test_with_no_package) is None


def test_livehybrid(downloader: SplunkDownloader) -> None:

    results = list(downloader.parse_livehybrid())
    assert all(hasattr(link, "url") for link in results)
    assert all(hasattr(link, "version") for link in results)
    assert all(hasattr(link, "os") for link in results)
    assert all(hasattr(link, "arch") for link in results)
    assert all(hasattr(link, "package_type") for link in results)

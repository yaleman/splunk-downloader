import logging
from pathlib import Path
import tempfile

import pytest

from splunk_downloader import download_page, get_and_parse
from splunk_downloader.constants import URLS
from concurrent.futures import ThreadPoolExecutor, as_completed


def test_download_page() -> None:
    download_page("https://yaleman.org", None)

    with tempfile.NamedTemporaryFile(delete=False) as temp_file:
        download_page("https://yaleman.org", Path(temp_file.name))


def test_get_and_parse() -> None:
    logging.basicConfig(level=logging.INFO)
    with pytest.raises(ValueError):
        get_and_parse("invalid_url", True, cache_path=False)  # type: ignore[arg-type]
    with pytest.raises(FileNotFoundError):
        get_and_parse("invalid_url", True, cache_path=Path("/asdfasfasldkfjhaslfkhjdsaflksdhjf"))

    def _test_get_and_parse(url: str, cached: bool, with_temp_dir: bool) -> None:
        if with_temp_dir:
            with tempfile.TemporaryDirectory() as temp_dir:
                get_and_parse(url, cached, Path(temp_dir))
        else:
            get_and_parse(url, cached, None)

    tasks = []
    for _download_type, url in URLS.items():
        for cached in [True, False]:
            # Test with a temporary directory
            tasks.append((_test_get_and_parse, url, cached, True))
            tasks.append((_test_get_and_parse, url, cached, False))

    # Run all tasks in parallel
    with ThreadPoolExecutor() as executor:
        futures = [executor.submit(func, *args) for func, *args in tasks]  # type: ignore[arg-type]
        for future in as_completed(futures):
            # This will raise any exceptions that occurred in the threads
            future.result()

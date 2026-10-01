"""Splunk downloader"""

import csv
import os
import re
import sys
import time
import urllib.parse
from collections.abc import Generator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import click
import requests
from bs4 import BeautifulSoup, Tag
from bs4.element import ResultSet
from loguru import logger
from packaging.version import Version
from pydantic import BaseModel, ConfigDict

from .constants import PACKAGES, TARGET_LINK_ATTR, TARGET_LINK_ATTR_FALLBACK, URLS

PACKAGE_MATCHER = re.compile(r"(" + "|".join(PACKAGES) + ")$")
VERSION_FINDER = re.compile(r"releases\/(?P<version>[^\/]+)\/(?P<os>[^\/]+)")

PACKAGE_VERSION = "0.2.3"


def download_page(url: str, cache_file: Path | None) -> bytes:
    """download the page and store it if cache_file is set"""
    logger.debug("Pulling URL {}", url)
    response = requests.get(
        url, timeout=30, headers={"User-Agent": f"splunk-downloader/{PACKAGE_VERSION}"}
    )
    response.raise_for_status()
    if cache_file is not None:
        logger.info("Writing {}", cache_file)
        with open(cache_file, "wb") as file_handle:
            file_handle.write(response.content)
    return response.content


def get_and_parse(url: str, cached: bool, cache_path: Path | None = None) -> list[str]:
    """grabs the url and soups it, returning a list of links"""

    try:
        parsed_url = urllib.parse.urlparse(
            url
        )  # validate the url is right, we don't actually use the result
        if not parsed_url.scheme or not parsed_url.netloc:
            raise ValueError(f"URL '{url}' is missing a scheme or netloc")
    except Exception as e:  # noqa: BLE001
        raise ValueError(f"Invalid URL '{url}': {e}")

    if cached:
        # this should only really be used for debugging and
        # you need to download the URLs with
        # wget or something first
        logger.debug("Using cached file")
        if cache_path is None:
            cache_path = Path("./cache/")
        if not cache_path.exists():
            cache_path.mkdir(parents=True, exist_ok=True)
            logger.info("Created cache directory at {}", cache_path)
        if not cache_path.is_dir():
            raise ValueError(f"Cache path '{cache_path}' is not a directory!")
        if "forwarder" in url:
            cachefile = cache_path.with_name("universalforwarder.html")
        else:
            cachefile = cache_path.with_name("previous-releases.html")

        if not os.path.exists(cachefile):
            logger.info("Cached file not found, downloading {} to {}", url, cachefile)
            try:
                download_page(url, cache_file=cachefile)
            except Exception as e:  # noqa: BLE001
                logger.error("Failed to download page {}: {}", url, e)
                return []
        else:
            update_time = os.stat(cachefile).st_mtime
            file_age = round(datetime.now(UTC).timestamp() - update_time, 0)
            logger.info("Cache file {} is {} seconds old.", cachefile, file_age)
        with open(cachefile, "r", encoding="utf8") as file_handle:
            soup = BeautifulSoup(file_handle.read(), "html.parser")
    else:
        soup = BeautifulSoup(download_page(url, None), "html.parser")
    links: ResultSet[Tag] = soup.find_all("a", class_="splunk-btn")
    retlinks = []
    for link in links:
        if not hasattr(link, "attrs"):
            logger.debug("No attrs on link, skipping: {}", link)
            continue
        datalink = link.attrs.get(TARGET_LINK_ATTR, None)
        if datalink is not None:
            datalink = str(datalink)
            if datalink.endswith(".ogg"):
                logger.debug("Skipping .ogg link, weirdos: {}", link)
                continue
            if datalink not in links:
                retlinks.append(datalink)
                logger.debug("Adding link to links: {}", datalink)
            continue
        datalink_fallback = link.attrs.get(TARGET_LINK_ATTR_FALLBACK, None)
        if datalink_fallback is not None:
            logger.debug("Falling back to wget link")
            datalink = str(datalink_fallback).split(" ")[-1].replace('"', "")
            if datalink.endswith(".ogg"):
                logger.debug("Skipping .ogg wget link, weirdos: {}", link)
                continue
            if datalink not in links:
                retlinks.append(datalink)
                logger.debug("Adding wget link to links: {}", datalink)
        else:
            logger.debug(
                "Skipping link, doesn't have attr '{}': {}", TARGET_LINK_ATTR, link
            )
    return retlinks


def download_link(url: str) -> bool:
    """downloads a link"""
    response = input(f"Would you like to download {url}? ")
    if response.strip().lower() not in ("y", "yes"):
        logger.info("Cancelled at user request")
        return False
    logger.info("Downloading {}", url)
    # this is intentionally a long-running task
    try:
        download_response = requests.get(url, timeout=300)
        download_response.raise_for_status()
    except requests.exceptions.Timeout as timeout_error:
        logger.error("Timed out downloading from {}: {}", url, timeout_error)
        return False
    filename = url.split("/")[-1]
    with open(filename, "wb") as download_handle:
        logger.info("Writing {} bytes to {}", len(download_response.content), filename)
        download_handle.write(download_response.content)
    return True


class SeenData(BaseModel):
    """Data for when you want to see you've seen an os/package/arch combination."""

    os: str
    arch: str
    package_type: str

    model_config = ConfigDict(extra="ignore")


class LinkData(BaseModel):
    """Full data for a link."""

    os: str
    arch: str
    package_type: str
    url: str
    version: Version

    model_config = ConfigDict(arbitrary_types_allowed=True)

    def __hash__(self) -> int:
        return hash((self.os, self.arch, self.package_type, self.url, self.version))


def parse_livehybrid() -> Generator[LinkData, None, None]:
    cache_path = Path("./cache") / "livehybrid.tsv"
    url = "https://livehybrid.github.io/downloadSplunk/downloads.tsv"
    if cache_path.exists() and os.stat(cache_path).st_mtime > time.time() - 86400:
        logger.info("Using cached file at {}", cache_path)
        data_content = cache_path.read_text()
    else:
        data_content = download_page(url, cache_path).decode("utf-8")

    tsv_reader = csv.reader(data_content.splitlines(keepends=False), delimiter="\t")
    for row in tsv_reader:
        if row[0].strip().startswith("#"):
            continue
        try:
            (package_type, version, _filehash, paths) = row
        except ValueError as e:
            logger.error("Failed to parse row {}: {}", row, e)
            continue

        for package_path in paths.split():
            # eg https://download.splunk.com/products/splunk/releases/10.4.4/windows/splunk-10.4.4-f0f12fcdcaa1-windows-x64.msi
            this_link = LinkData(
                os=package_path.split("/")[0],
                arch=get_arch_from_package(package_path),
                package_type=package_type,
                url=f"https://download.splunk.com/products/splunk/releases/{version}/{package_path}",
                version=Version(version),
            )
            yield this_link


def filter_by_latest(endstate: list[LinkData]) -> list[LinkData]:
    """filters by the latest version"""
    seen_list = []
    results = []
    for result in endstate:
        seen = SeenData.model_validate(result.model_dump())
        logger.debug("Checking if we have seen {}", seen.model_dump())
        if seen.model_dump() not in seen_list:
            seen_list.append(seen.model_dump())
            results.append(result)
    return results


def get_data_from_url(url: str) -> LinkData | None:
    """returns the version from the url"""

    result = VERSION_FINDER.search(url)
    if not result:
        raise ValueError(f"Couldn't get version from url: {url}")
    versionmatch = result.groupdict()

    package_type = PACKAGE_MATCHER.search(url)
    if package_type is None:
        logger.warning(f"Failed to parse package version from link: {url}")
        return None

    arch = get_arch_from_package(url)

    version_object = Version(versionmatch["version"])

    parsed = LinkData(
        arch=arch,
        version=version_object,
        url=url,
        os=versionmatch["os"],
        package_type=package_type.group(),
    )
    return parsed


def get_arch_from_package(url: str) -> str:
    """gets the arch from the package"""
    # .tar.Z fix is for solaris

    if "windows" in url:
        url = url.replace("-release", "")
    if "solaris" in url:
        url = url.replace(".tar.Z", ".tar")
    link_arch = url.split(".")[-2].split("-")[-1]

    return link_arch


def setup_logging(
    logger_object: Any = logger,
    debug: bool = True,
    log_sink: Any | None = sys.stderr,
) -> None:
    """does logging configuration"""
    # use the one from the environment, where possible
    loguru_level = os.getenv("LOGURU_LEVEL", "INFO")

    if debug:
        loguru_level = "DEBUG"

    logger_object.remove()
    logger_object.add(
        sink=log_sink,
        level=loguru_level,
    )


@click.command(help="Application needs to be either forwarder or enterprise.")
@click.option(
    "--cached",
    is_flag=True,
    default=False,
    help="Use a locally cached version of the source data.",
)
@click.option(
    "--arch", "-a", help="CPU Architecture filter - based on filename which is messy"
)
@click.option("--debug", "-d", is_flag=True, default=False, help="Enable debug mode")
@click.option(
    "--download",
    "-D",
    is_flag=True,
    default=False,
    help="Prompt to download to the local directory",
)
@click.argument(
    "application", type=click.Choice(["enterprise", "forwarder"], case_sensitive=False)
)
@click.option(
    "--version",
    "-v",
    "version_filter",
    help="Version to match, is used as a <version>* wildcard, if not included will list them all.",
)
@click.option(
    "--os",
    "-o",
    "os_filter",
    type=click.Choice(
        ["windows", "linux", "solaris", "osx", "freebsd", "aix"], case_sensitive=False
    ),
    help="OS string to match, valid options for Enterprise: (linux|windows|osx), Forwarder: (windows|linux|solaris|osx|freebsd|aix)",
)
@click.option(
    "--type",
    "-t",
    "packagetype",
    type=click.Choice(
        [el.replace("\\", "") for el in PACKAGES],
        case_sensitive=False,
    ),
    help="Package type to match.",
)
@click.option(
    "--latest",
    "-l",
    is_flag=True,
    help="Show only the latest version for any given os/package/arch combination.",
)
@click.option(
    "--include-livehybrid",
    is_flag=True,
    default=False,
    help="Include links from https://livehybrid.github.io/downloadSplunk/ in the results.",
)
def cli(
    application: str | None = None,
    debug: bool = False,
    version_filter: str = "",
    os_filter: str | None = None,
    download: bool = False,
    cached: bool = False,
    packagetype: str | None = None,
    arch: str | None = None,
    latest: bool = False,
    include_livehybrid: bool = False,
) -> None:
    """does the CLI thing"""
    setup_logging(logger, debug)

    if application is None:
        return
    if application.lower() not in ("enterprise", "forwarder"):
        logger.error(
            "Sorry, you need to select enterprise or forwarder, you selected: {}",
            application,
        )

    if os_filter:
        if application == "enterprise":
            valid_types = ["linux", "windows", "osx"]
        else:
            valid_types = ["windows", "linux", "solaris", "osx", "freebsd", "aix"]
        if os_filter not in valid_types:
            logger.error(
                "Package type set to {}, which isn't in the valid types for {} {}",
                os_filter,
                application,
                valid_types,
            )
            sys.exit(1)

    if packagetype != "":
        logger.debug("looking for package type: {}", packagetype)

    results: set[LinkData] = set()
    links = get_and_parse(url=URLS[application], cached=cached)
    try:
        links = links + get_and_parse(url=URLS[f"{application}_current"], cached=cached)
    except KeyError:
        pass

    links: list[LinkData | None] = [
        get_data_from_url(link) for link in links if get_data_from_url(link) is not None
    ]
    links: list[LinkData] = [link for link in links if link is not None]

    if include_livehybrid:
        try:
            links.extend(parse_livehybrid())
        except Exception as e:  # noqa: BLE001
            logger.error("Failed to include livehybrid links: {}", e)

    for link in links:
        logger.debug("Checking link {}", link)

        if os_filter and link.os != os_filter:
            logger.debug("Skipping {} as os does not match {}", link, os_filter)
            continue

        if version_filter and not str(link.version).startswith(version_filter):
            logger.debug("Skipping {} as version does not match {}", link, link)
            continue
        if packagetype and packagetype != link.package_type:
            logger.debug(
                "Skipping {} as package type does not match", link, packagetype
            )
            continue
        if arch and link.arch.lower() != arch.lower():
            logger.debug("Skipping {} as architecture does not match {}", link, arch)
            continue
        if link.model_dump() not in [r.model_dump() for r in results]:
            results.add(link)
    if not results:
        logger.error("No results found")
        return

    endstate: list[LinkData] = sorted(results, key=lambda k: k.version, reverse=True)

    # filter by latest
    if latest:
        endstate = filter_by_latest(endstate)

    # output stage
    for result in endstate:
        print(result.url)
        if download:
            download_link(result.url)

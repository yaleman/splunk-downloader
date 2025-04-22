"""Splunk downloader"""

import os
from datetime import datetime
from pathlib import Path
import re
import sys
from typing import Any, List, Optional


from bs4 import BeautifulSoup
import click
from loguru import logger
import requests
from packaging.version import Version
from pydantic import BaseModel, ConfigDict

from .constants import PACKAGES, TARGET_LINK_ATTR, TARGET_LINK_ATTR_FALLBACK, URLS

PACKAGE_MATCHER = re.compile(r"(" + "|".join(PACKAGES) + ")$")


def download_page(url: str, cache_file: Optional[Path]) -> bytes:
    """download the page and store it if cache_file is set"""
    logger.debug("Pulling URL {}", url)
    response = requests.get(url, timeout=30)
    response.raise_for_status()
    if cache_file is not None:
        logger.warning("Writing {}", cache_file)
        with open(cache_file, "wb") as file_handle:
            file_handle.write(response.content)
    return response.content


def get_and_parse(url: str, cached: bool, cache_path: Optional[Path] = None) -> List[str]:
    """grabs the url and soups it, returning a list of links"""
    if cached:
        # this should only really be used for debugging and
        # you need to download the URLs with
        # wget or something first
        logger.debug("Using cached file")
        if cache_path is None:
            cache_path = Path("./cache/")
        if not isinstance(cache_path, Path):
            raise ValueError(f"Cache path '{cache_path}' must be a Path object")
        if not cache_path.exists():
            raise FileNotFoundError(f"Cache path '{cache_path}' does not exist!")
        if not cache_path.is_dir():
            raise ValueError(f"Cache path '{cache_path}' is not a directory!")
        if "forwarder" in url:
            cachefile = cache_path.with_name("universalforwarder.html")
        else:
            cachefile = cache_path.with_name("previous-releases.html")

        if not os.path.exists(cachefile):
            download_page(url, cache_file=cachefile)
        else:
            update_time = os.stat(cachefile).st_mtime
            file_age = round(datetime.now().timestamp() - update_time, 0)
            logger.info("Cache file {} is {} seconds old.", cachefile, file_age)
        with open(cachefile, "r", encoding="utf8") as file_handle:
            soup = BeautifulSoup(file_handle.read(), "html.parser")
    else:
        soup = BeautifulSoup(download_page(url, None), "html.parser")
    links = soup.find_all("a", class_="splunk-btn")
    retlinks = []
    for link in links:
        if not hasattr(link, "attrs"):
            logger.debug("No attrs on link, skipping: {}", link)
            continue
        if link.attrs.get(TARGET_LINK_ATTR, None) is not None:
            datalink = link.attrs.get(TARGET_LINK_ATTR)
            if datalink.endswith(".ogg"):
                logger.debug("Skipping .ogg link, weirdos: {}", link)
                continue
            if datalink not in links:
                retlinks.append(datalink)
                logger.debug("Adding link to links: {}", datalink)
        elif link.attrs.get(TARGET_LINK_ATTR_FALLBACK, None) is not None:
            logger.debug("Falling back to wget link")
            datalink = link.attrs.get(TARGET_LINK_ATTR_FALLBACK).split(" ")[-1].replace('"', "")
            if datalink.endswith(".ogg"):
                logger.debug("Skipping .ogg wget link, weirdos: {}", link)
                continue
            if datalink not in links:
                retlinks.append(datalink)
                logger.debug("Adding wget link to links: {}", datalink)
        else:
            logger.debug("Skipping link, doesn't have attr '{}': {}", TARGET_LINK_ATTR, link)
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
        # pylint: disable=missing-timeout
        download_response = requests.get(url)
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


def filter_by_latest(endstate: List[LinkData]) -> List[LinkData]:
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


def get_data_from_url(url: str) -> Optional[LinkData]:
    """returns the version from the url"""
    version_finder = re.compile(r"releases\/(?P<version>[^\/]+)\/(?P<os>[^\/]+)")

    result = version_finder.search(url)
    if not result:
        raise ValueError(f"Couldn't get version from url: {url}")
    versionmatch = result.groupdict()
    if "version" not in versionmatch:
        raise ValueError("Version not found in versionmatch")

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
    log_sink: Optional[Any] = sys.stderr,
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
@click.option("--arch", "-a", help="CPU Architecture filter - based on filename which is messy")
@click.option("--debug", "-d", is_flag=True, default=False, help="Enable debug mode")
@click.option(
    "--download",
    "-D",
    is_flag=True,
    default=False,
    help="Prompt to download to the local directory",
)
@click.argument("application", type=click.Choice(["enterprise", "forwarder"], case_sensitive=False))
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
    type=click.Choice(["windows", "linux", "solaris", "osx", "freebsd", "aix"], case_sensitive=False),
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
def cli(  # pylint: disable=too-many-arguments,too-many-branches,too-many-locals,too-many-statements
    application: Optional[str] = None,
    debug: bool = False,
    version_filter: str = "",
    os_filter: Optional[str] = None,
    download: bool = False,
    cached: bool = False,
    packagetype: Optional[str] = None,
    arch: Optional[str] = None,
    latest: bool = False,
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

    results: List[LinkData] = []
    links = get_and_parse(url=URLS[application], cached=cached)
    try:
        links = links + get_and_parse(url=URLS[f"{application}_current"], cached=cached)
    except KeyError:
        pass

    for link in links:
        logger.debug("Checking link {}", link)
        link_data = get_data_from_url(link)
        if link_data is None:
            logger.debug("Skipping {}, data is None", link)
            continue

        if os_filter:
            if link_data.os != os_filter:
                logger.debug("Skipping {} as os does not match {}", link, os_filter)
                continue

        if version_filter:
            if not str(link_data.version).startswith(version_filter):
                logger.debug("Skipping {} as version does not match {}", link, link_data)
                continue
        if packagetype:
            if not packagetype == link_data.package_type:
                logger.debug("Skipping {} as package type does not match", link, packagetype)
                continue
        if arch:
            if link_data.arch.lower() != arch.lower():
                continue

        if link_data not in results:
            results.append(link_data)
    if not results:
        logger.error("No results found")
        return

    endstate: List[LinkData] = sorted(results, key=lambda k: k.version, reverse=True)

    # filter by latest
    if latest:
        endstate = filter_by_latest(endstate)

    # output stage
    for result in endstate:
        print(result.url)
        if download:
            download_link(result.url)

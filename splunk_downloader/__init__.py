""" Splunk downloader """

import os
from datetime import datetime
import re
import sys
from typing import Any, List, Optional

from distutils.version import LooseVersion

from bs4 import BeautifulSoup #type: ignore
import click
from loguru import logger
import requests
import pydantic

PACKAGES =  [
    "deb",
    "dmg",
    "msi",
    "p5p",
    r'pkg\.Z',
    "rpm",
    "tgz",
    "txz",
    r'tar\.Z',
    "zip",
]

PACKAGE_MATCHER = re.compile(r'('+'|'.join(PACKAGES)+')$')


URLS = {
    "enterprise": "https://www.splunk.com/en_us/download/previous-releases.html",
    "enterprise_current": "https://www.splunk.com/en_us/download/get-started-with-your-free-trial.html",
    "forwarder": "https://www.splunk.com/en_us/download/previous-releases/universalforwarder.html",
    "forwarder_current": "https://www.splunk.com/en_us/download/universal-forwarder.html",
}

def download_page(url: str, cache_file: str = "") -> bytes:
    """ download the page and store it if cache_file is set """
    logger.debug("Pulling URL {}", url)
    response = requests.get(url)
    response.raise_for_status()
    if cache_file.strip() != "":
        logger.warning("Writing {}", cache_file)
        with open(cache_file, "wb") as file_handle:
            file_handle.write(response.content)
    return response.content


def get_and_parse(url: str, cached: bool) -> List[Any]:
    """ grabs the url and soups it, returning a list of links """
    if cached:
        # this should only really be used for debugging and
        # you need to download the URLs with
        # wget or something first
        logger.debug("Using cached file")
        if "forwarder" in url:
            cachefile = "universalforwarder.html"
        else:
            cachefile = "previous-releases.html"

        if not os.path.exists(cachefile):
            download_page(url, cache_file=cachefile)
        else:
            update_time = os.stat(cachefile).st_mtime
            file_age = round(datetime.now().timestamp() - update_time, 0)
            logger.info("Cache file {} is {} seconds old.", cachefile, file_age)
        with open(cachefile, "r", encoding="utf8") as file_handle:
            soup = BeautifulSoup(file_handle.read(), "html.parser")
    else:
        soup = BeautifulSoup(download_page(url), "html.parser")
    links = soup.find_all("a", class_="splunk-btn")
    retlinks = []
    for link in links:
        if link.attrs.get("data-link", False):
            datalink = link.attrs.get("data-link")
            if datalink not in links:
                retlinks.append(datalink)
                logger.debug("Adding link to links: {}", datalink)
        else:
            logger.debug("Skipping link, doesn't have attr 'datal-linl': {}", link)
    return retlinks


def download_link(url: str) -> bool:
    """ downloads a link """
    response = input(f"Would you like to download {url}? ")
    if response.strip().lower() not in ("y", "yes"):
        logger.info("Cancelled at user request")
        return False
    logger.info("Downloading {}", url)
    download_response = requests.get(url)
    download_response.raise_for_status()
    filename = url.split("/")[-1]
    with open(filename, "wb") as download_handle:
        download_handle.write(download_response.content)
    return True

class SeenData(pydantic.BaseModel):
    """ Data for when you want to see you've seen an os/package/arch combination. """
    os: str
    arch: str
    package_type: str

#pylint: disable=too-few-public-methods
class LinkData(SeenData):
    """ Full data for a link. """
    url: str
    version: LooseVersion

    class Config:
        """ configuration """
        arbitrary_types_allowed = True


def filter_by_latest(endstate: List[LinkData]
    ) -> List[LinkData]:
    """ filters by the latest version """
    seen_list = []
    results = []
    for result in endstate:
        seen = SeenData.parse_obj(result)
        if seen not in seen_list:
            seen_list.append(seen)
            results.append(result)

    return results

def get_data_from_url(url: str) -> LinkData:
    """ returns the version from the url """
    version_finder = re.compile(r'releases\/(?P<version>[^\/]+)\/(?P<os>[^\/]+)')

    result = version_finder.search(url)
    if not result:
        raise ValueError(f"Couldn't get version from url: {url}")
    versionmatch = result.groupdict()
    if "version" not in versionmatch:
        raise ValueError("Version not found in versionmatch")

    package_type = PACKAGE_MATCHER.search(url)
    if package_type is None:
        raise ValueError(f"Failed to parse package version from link: {url}")

    arch = get_arch_from_package(url)

    parsed = LinkData(
        arch = arch,
        version = LooseVersion(versionmatch["version"]),
        url=url,
        os = versionmatch["os"],
        package_type=package_type.group()
    )
    return parsed

def get_arch_from_package(url: str) -> str:
    """ gets the arch from the package """
    # .tar.Z fix is for solaris

    if "windows" in url:
        url = url.replace("-release", "")
    if "solaris" in url:
        url = url.replace(".tar.Z", ".tar")
    link_arch = url.split(".")[-2].split("-")[-1]

    return link_arch



def setup_logging(
    logger_object: Any=logger,
    debug: bool = True,
    log_sink: Optional[Any]=sys.stderr,
) -> None:
    """ does logging configuration """
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
@click.option("--cached", is_flag=True, default=False)
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
    help="OS string to match, valid options for Enterprise: (linux|windows|osx), Forwarder: {(windows|linux|solaris|osx|freebsd|aix)}",
)
@click.option(
    "--type",
    "-t",
    "packagetype",
    type=click.Choice(
        [ el.replace("\\", '') for el in PACKAGES],
        case_sensitive=False,
        ),
    help="Package type to match.",
)
@click.option(
    "--latest", "-l", is_flag=True, help="Show only the latest version for any given os/package/arch combination."
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
    """ does the CLI thing """
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

        if os_filter:
            if link_data.os != os_filter:
                logger.debug("Skipping {} as os does not match {}", link, os_filter)
                continue

        if version_filter:
            if not str(link_data.version).startswith(version_filter):
                logger.debug(
                    "Skipping {} as version does not match {}", link, link_data
                )
                continue
        if packagetype:
            if not packagetype == link_data.package_type:
                logger.debug(
                    "Skipping {} as package type does not match", link, packagetype
                )
                continue
        if arch:
            if link_data.arch.lower() != arch.lower():
                continue

        if link_data not in results:
            results.append(link_data)
    if not results:
        logger.error("No results found")
        return


    endstate: List[LinkData] = sorted(results, key=lambda k: k.version, reverse=True )



    # filter by latest
    if latest:
        endstate = filter_by_latest(endstate)

    # output stage
    for result in endstate:
        print(result.url)
        if download:
            download_link(result.url)

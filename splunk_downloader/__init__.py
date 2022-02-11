""" Splunk downloader """

import os
from datetime import datetime
import re

from distutils.version import LooseVersion

from bs4 import BeautifulSoup #type: ignore
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


def get_and_parse(url: str, cached: bool):
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


def download_link(url) -> bool:
    """ downloads a link """
    response = input(f"Would you like to download {url}? ")
    if response.strip().lower() not in ("y", "yes"):
        logger.info("Cancelled at user request")
        return False
    logger.debug("Downloading {}", url)
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

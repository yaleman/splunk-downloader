""" please only use this if you actually accept the T&C's of using splunk software

    requires the following python packages:

    - requests (for handling HTTP requests) https://pypi.org/project/requests/
    - beautifulsoup4 (for parsing the HTTP responses) https://pypi.org/project/beautifulsoup4/
    - click (for cli things) https://pypi.org/project/click/
    - loguru (for output things) https://pypi.org/project/loguru/

"""

import os
import sys
from typing import List

import click
from loguru import logger

from . import PACKAGES, get_and_parse, download_link, get_data_from_url, LinkData, SeenData

URLS = {
    "enterprise": "https://www.splunk.com/en_us/download/previous-releases.html",
    "enterprise_current": "https://www.splunk.com/en_us/download/get-started-with-your-free-trial.html",
    "forwarder": "https://www.splunk.com/en_us/download/previous-releases/universalforwarder.html",
    "forwarder_current": "https://www.splunk.com/en_us/download/universal-forwarder.html",
}


def setup_logging(
    logger_object=logger,
    debug: bool = True,
    log_sink=sys.stderr,
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
    application: str = None,
    debug: bool = False,
    version_filter: str = None,
    os_filter: str = None,
    download: bool = False,
    cached: bool = False,
    packagetype: str = None,
    arch: str = None,
    latest: bool = False,
):
    """ does the CLI thing """
    setup_logging(logger, debug)

    if application is None:
        return False
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
        return False


    endstate: List[LinkData] = sorted(results, key=lambda k: k.version, reverse=True )


    def filter_by_latest(results: List[LinkData]) -> List[LinkData]:
        """ filters by the latest version """
        seen_list = []
        results = []
        for result in endstate:
            seen = SeenData.parse_obj(result)
            if seen not in seen_list:
                seen_list.append(seen)
                results.append(result)

        return results

    # filter by latest
    if latest:
        endstate = filter_by_latest(endstate)

    # output stage
    for result in endstate:
        print(result.url)
        if download:
            download_link(result.url)

    return True


if __name__ == "__main__":
    cli()  # pylint: disable=no-value-for-parameter

#!/usr/bin/env python3
#pylint: disable=invalid-name
""" please only use this if you actually accept the T&C's of using splunk software

    requires the following python packages:

    - requests (for handling HTTP requests) https://pypi.org/project/requests/
    - beautifulsoup4 (for parsing the HTTP responses) https://pypi.org/project/beautifulsoup4/
    - click (for cli things) https://pypi.org/project/click/
    - loguru (for output things) https://pypi.org/project/loguru/

"""

import os
import sys

try:
    import click
    import requests
    from bs4 import BeautifulSoup
    from loguru import logger
except ImportError as error_message:
    print(f"Failed to import {error_message.name}: {error_message}, quitting.")
    sys.exit(1)

URLS = {
    'enterprise' : "https://www.splunk.com/en_us/download/previous-releases.html",
    'enterprise_current' : 'https://www.splunk.com/en_us/download/get-started-with-your-free-trial.html',
    'forwarder' : "https://www.splunk.com/en_us/download/previous-releases/universalforwarder.html",
    'forwarder_current' : "https://www.splunk.com/en_us/download/universal-forwarder.html",
}


def get_and_parse(url: str, cached:bool):
    """ grabs the url and soups it, returning a list of links """
    if cached:
        # this should only really be used for debugging and
        # you need to download the URLs with
        # wget or something first
        logger.debug("Using cached file")
        if 'forwarder' in url:
            cachefile = 'universalforwarder.html'
        else:
            cachefile = 'previous-releases.html'

        with open(cachefile, 'r') as file_handle:
            soup = BeautifulSoup(file_handle.read(), 'html.parser')
    else:
        logger.debug("Pulling URL {}", url)
        response = requests.get(url)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'html.parser')
    links = soup.find_all("a", class_="splunk-btn")
    retlinks = []
    for link in links:
        if link.attrs.get('data-link', False):
            datalink = link.attrs.get('data-link')
            if datalink not in links:
                retlinks.append(datalink)
                logger.debug("Adding link to links: {}", datalink)
        else:
            logger.debug("Skipping link, doesn't have attr 'datal-linl': {}", link)
    return retlinks

def download_link(url):
    """ downloads a link """
    response = input(f"Would you like to download {url}? ")
    if response.strip().lower() not in ("y", "yes"):
        logger.info("Cancelled at user request")
        return False
    logger.debug("Downloading {}", url)
    download_response = requests.get(url)
    download_response.raise_for_status()
    filename = url.split("/")[-1]
    with open(filename, 'wb') as download_handle:
        download_handle.write(download_response.content)

    sys.exit(-1)

def setup_logging(logger_object=logger, debug: bool=True,
                  log_sink=sys.stderr,
                 ) -> None:
    """ does logging configuration """
    # use the one from the environment, where possible
    loguru_level=os.getenv('LOGURU_LEVEL', 'INFO')

    if debug:
        loguru_level='DEBUG'

    logger_object.remove()
    logger_object.add(sink=log_sink,
                      level=loguru_level,
                      )

@click.command(help='Application needs to be either forwarder or enterprise.')
@click.option('--cached', is_flag=True, default=False)
@click.option('--debug', '-d', is_flag=True, default=False, help="Enable debug mode")
@click.option('--download', '-D', is_flag=True, default=False, help="Prompt to download to the local directory")
@click.argument('application',
                type=click.Choice(['enterprise', 'forwarder'], case_sensitive=False))
@click.option('--version', '-v', 'version_filter',
              help="Version to match, is used as a <version>* wildcard, if not included will list them all.")
@click.option('--os', '-o', 'os_filter',
              type=click.Choice(['windows', 'linux', 'solaris', 'osx', 'freebsd', 'aix'], case_sensitive=False),
              help="OS string to match, valid options for Enterprise: (linux|windows|osx), Forwarder: (windows|linux|solaris|osx|freebsd|aix)")
@click.option('--type', '-t', 'packagetype',
              type=click.Choice(['deb', 'msi', 'rpm', 'tgz'], case_sensitive=False),
              help="Package type to match.",
              )
def cli( #pylint: disable=too-many-arguments,too-many-branches
        application: str,
        debug: bool,
        version_filter: str,
        os_filter:str,
        download:bool,
        cached:bool,
        packagetype: str,
        ):
    """ does the CLI thing """
    setup_logging(logger, debug)

    if application.lower() not in ('enterprise', 'forwarder'):
        logger.error("Sorry, you need to select enterprise or forwarder, you selected: {}", application)

    if os_filter:
        if application == 'enterprise':
            valid_types = ['linux','windows','osx']
        else:
            valid_types = ['windows','linux','solaris','osx','freebsd','aix']
        if os_filter not in valid_types:
            logger.error("Package type set to {}, which isn't in the valid types for {} {}",
                         os_filter, application, valid_types)
            sys.exit(1)

    if packagetype != "":
        #if packagetype not in ('msi', 'rpm', 'tgz'):
        #    logger.error("Va")
        logger.debug("looking for package type: {}", packagetype)
    results = []
    links = get_and_parse(url=URLS.get(application), cached=cached) + get_and_parse(url=URLS.get(f"{application}_current"), cached=cached)

    for link in links:
        logger.debug("Checking link {}", link)
        splitlink = link.split("/")
        link_os = splitlink[7]
        link_version = splitlink[6]
        if os_filter:
            if link_os != os_filter:
                logger.debug("Skipping {} as os does not match {}", link, os_filter)
                continue

        if version_filter:
            if not link_version.startswith(version_filter):
                logger.debug("Skipping {} as version does not match {}", link, link_version)
                continue

        if packagetype:
            if not link.endswith(packagetype):
                logger.debug("Skipping {} as package type does not match", link, packagetype)
                continue
        if link not in results:
            results.append(link)
    if not results:
        logger.error("No results found")
        return False

    # output stage
    results.sort(reverse=True)
    for result in results:
        print(result)
        if download:
            download_link(result)

    return True

if __name__ == '__main__':
    cli() #pylint: disable=no-value-for-parameter

"""please only use this if you actually accept the T&C's of using splunk software

requires the following python packages:

- requests (for handling HTTP requests) https://pypi.org/project/requests/
- beautifulsoup4 (for parsing the HTTP responses) https://pypi.org/project/beautifulsoup4/
- click (for cli things) https://pypi.org/project/click/
- loguru (for output things) https://pypi.org/project/loguru/

"""

from splunk_downloader import cli

if __name__ == "__main__":
    cli()

"""tests semver things"""

from splunk_downloader import get_data_from_url, PACKAGE_MATCHER

TEST_DATA = {
    "7.2.9.1": [
        "https://download.splunk.com/products/universalforwarder/releases/7.2.9.1/linux/splunkforwarder-7.2.9.1-605df3f0dfdd-Linux-s390x.tgz",
        "https://download.splunk.com/products/universalforwarder/releases/7.2.9.1/linux/splunkforwarder-7.2.9.1-605df3f0dfdd-Linux-ppc64le.tgz",
        "https://download.splunk.com/products/universalforwarder/releases/7.2.9.1/linux/splunkforwarder-7.2.9.1-605df3f0dfdd-Linux-arm.tgz",
        "https://download.splunk.com/products/universalforwarder/releases/7.2.9.1/freebsd/splunkforwarder-7.2.9.1-605df3f0dfdd-freebsd-11.1-amd64.txz",
        "https://download.splunk.com/products/universalforwarder/releases/7.2.9.1/freebsd/splunkforwarder-7.2.9.1-605df3f0dfdd-freebsd-10.4-amd64.txz",
        "https://download.splunk.com/products/universalforwarder/releases/7.2.9.1/aix/splunkforwarder-7.2.9.1-605df3f0dfdd-AIX-powerpc.tgz",
    ],
    "7.2.8": [
        "https://download.splunk.com/products/universalforwarder/releases/7.2.8/windows/splunkforwarder-7.2.8-d613a50d43ac-x86-release.msi",
        "https://download.splunk.com/products/universalforwarder/releases/7.2.8/windows/splunkforwarder-7.2.8-d613a50d43ac-x64-release.msi",
        "https://download.splunk.com/products/universalforwarder/releases/7.2.8/solaris/splunkforwarder-7.2.8-d613a50d43ac-solaris-11-sparc.p5p",
        "https://download.splunk.com/products/universalforwarder/releases/7.2.8/solaris/splunkforwarder-7.2.8-d613a50d43ac-solaris-11-intel.p5p",
        "https://download.splunk.com/products/universalforwarder/releases/7.2.8/solaris/splunkforwarder-7.2.8-d613a50d43ac-solaris-10-sparc.pkg.Z",
        "https://download.splunk.com/products/universalforwarder/releases/7.2.8/solaris/splunkforwarder-7.2.8-d613a50d43ac-solaris-10-intel.pkg.Z",
        "https://download.splunk.com/products/universalforwarder/releases/7.2.8/solaris/splunkforwarder-7.2.8-d613a50d43ac-SunOS-x86_64.tar.Z",
        "https://download.splunk.com/products/universalforwarder/releases/7.2.8/solaris/splunkforwarder-7.2.8-d613a50d43ac-SunOS-sparc.tar.Z",
        "https://download.splunk.com/products/universalforwarder/releases/7.2.8/osx/splunkforwarder-7.2.8-d613a50d43ac-macosx-10.11-intel.dmg",
        "https://download.splunk.com/products/universalforwarder/releases/7.2.8/osx/splunkforwarder-7.2.8-d613a50d43ac-darwin-64.tgz",
        "https://download.splunk.com/products/universalforwarder/releases/7.2.8/linux/splunkforwarder-7.2.8-d613a50d43ac-linux-s390x.rpm",
        "https://download.splunk.com/products/universalforwarder/releases/7.2.8/linux/splunkforwarder-7.2.8-d613a50d43ac-linux-2.6-x86_64.rpm",
    ],
}


def test_more_things() -> None:
    """more tests based on live data"""

    for version in TEST_DATA:
        for url in TEST_DATA[version]:
            result = get_data_from_url(url)
            assert result
            assert str(result.version) == version


def test_pkg_parser() -> None:
    """testing the url parser"""
    result = PACKAGE_MATCHER.search(TEST_DATA["7.2.9.1"][0])
    assert result
    assert result.group()
    print(result)
    print(result.group())

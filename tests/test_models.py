from packaging.version import Version

from splunk_downloader.models import LinkData


def test_link_data_hash():

    link_data_1 = LinkData(
        os="linux",
        arch="x86_64",
        package_type="deb",
        url="https://example.com/package.deb",
        version=Version("1.0.0"),
    )
    link_data_2 = LinkData(
        os="linux",
        arch="x86_64",
        package_type="deb",
        url="https://example.com/package.deb",
        version=Version("1.0.0"),
    )

    assert hash(link_data_1) == hash(link_data_2)

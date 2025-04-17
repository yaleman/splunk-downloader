PACKAGES = [
    "deb",
    "dmg",
    "msi",
    "p5p",
    r"pkg\.Z",
    "rpm",
    "tgz",
    "txz",
    r"tar\.Z",
    "zip",
]

TARGET_LINK_ATTR = "data-link"
TARGET_LINK_ATTR_FALLBACK = "data-wget"

BASE_URL = "https://www.splunk.com/en_us/download"

URLS = {
    "enterprise": f"{BASE_URL}/previous-releases.html",
    "enterprise_current": f"{BASE_URL}/splunk-enterprise.html",
    "forwarder": f"{BASE_URL}/previous-releases-universal-forwarder.html",
    "forwarder_current": f"{BASE_URL}/universal-forwarder.html",
}

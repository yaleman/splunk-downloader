from packaging.version import Version
from pydantic import BaseModel, ConfigDict


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

# splunk-downloader

A little script to help download Splunk installers. You really should agree to the download terms if you're going to use this, just sayin'.

```text
Usage: splunk-downloader [OPTIONS] {enterprise|forwarder}

  Application needs to be either forwarder or enterprise.

Options:
  --cached                        Use a locally cached version of the source
                                  data.
  -a, --arch TEXT                 CPU Architecture filter - based on filename
                                  which is messy
  -d, --debug                     Enable debug mode
  -D, --download                  Prompt to download to the local directory
  -v, --version TEXT              Version to match, is used as a <version>*
                                  wildcard, if not included will list them
                                  all.
  -o, --os [windows|linux|solaris|osx|freebsd|aix]
                                  OS string to match, valid options for
                                  Enterprise: (linux|windows|osx), Forwarder:
                                  (windows|linux|solaris|osx|freebsd|aix)
  -t, --type [deb|dmg|msi|p5p|pkg.Z|rpm|tgz|txz|tar.Z|zip]
                                  Package type to match.
  -l, --latest                    Show only the latest version for any given
                                  os/package/arch combination.
  --help                          Show this message and exit.
```

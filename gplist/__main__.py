# -*- coding: utf-8 -*-
"""command line tools
"""

from datetime import datetime
from gplist.mobileprovision import MobileProvision
from gplist.plist import PlistInfo
import argparse
import binascii
import json
import os
import sys


class PlistEncoder(json.encoder.JSONEncoder):

    def default(self, o):
        if isinstance(o, datetime):
            return o.strftime("%Y-%m-%dT%H:%M:%SZ")
        elif isinstance(o, bytes):
            return binascii.hexlify(o).encode("ascii")
        elif isinstance(o, map):
            return list(o)
        return o


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("file", help="plist or mobile provision file path")
    parser.add_argument("--cert",
                        action="store_true",
                        help="output certificate information of mobile provision file")
    parser.add_argument("--has-udid",
                        dest="udid",
                        help="check whether provision contains the target udid")
    args = parser.parse_args(sys.argv[1:])
    file_path = os.path.abspath(args.file)
    if not os.path.isfile(file_path):
        print("file=%s is not a valid file" % file_path)
        sys.exit(1)
    try:
        p = PlistInfo.from_file(file_path)
    except ValueError:
        m = MobileProvision.from_file(file_path)
        if args.cert:
            cert_info = []
            for cert in m.certs:
                cert_info.append({
                    "serial": cert.serial,
                    "name": cert.common_name,
                    "sha1": cert.sha1})
            json.dump(cert_info, sys.stdout, indent=2, cls=PlistEncoder)
        elif args.udid:
            if m.has_udid(args.udid):
                print("yes")
            else:
                print("no")
                sys.exit(1)
        else:
            json.dump(m, sys.stdout, indent=2, cls=PlistEncoder)
    else:
        if any([args.cert, args.udid]):
            print("file=%s is not recognized as mobile provision file" % file_path)
            sys.exit(1)
        json.dump(p, sys.stdout, indent=2, cls=PlistEncoder)


if __name__ == "__main__":
    main()

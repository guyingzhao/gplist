# -*- coding: utf-8 -*-
"""main test
"""

from gplist.__main__ import PlistEncoder
from gplist.mobileprovision import MobileProvision
from gplist.plist import PlistInfo
import json
import os
import sys
import unittest


py_exe = "python%s.%s" % (sys.version_info[0], sys.version_info[1])
cur_dir = os.path.dirname(os.path.abspath(__file__))


class MainTest(unittest.TestCase):

    def test_plist(self):
        file_path = os.path.join(cur_dir, "Info.plist")
        cmdline = "%s -m gplist %s" % (py_exe, file_path)
        with os.popen(cmdline) as fd:
            content = fd.read()
            p = json.loads(content)
        p2 = PlistInfo.from_file(file_path)
        self.assertEqual(p, p2)

    def test_provision(self):
        file_path = os.path.join(cur_dir, "embedded.mobileprovision")
        if not os.path.exists(file_path):
            print("file=%s not found, skipped")
            return

        cmdline = "%s -m gplist %s" % (py_exe, file_path)
        with os.popen(cmdline) as fd:
            content = fd.read()
        m = MobileProvision.from_file(file_path)
        content2 = json.dumps(m, cls=PlistEncoder, indent=2)
        self.assertEqual(content, content2)

        cmdline = "%s -m gplist --cert %s" % (py_exe, file_path)
        with os.popen(cmdline) as fd:
            content = fd.read()
        certs = json.loads(content)
        self.assertTrue(len(certs) > 0)
        self.assertIn("serial", certs[0])
        self.assertIn("name", certs[0])
        self.assertIn("sha1", certs[0])

        if "ProvisionsAllDevices" in m:
            udid = "xxx"
        else:
            udid = m["ProvisionedDevices"][0]
        cmdline = "%s -m gplist --has-udid %s %s" % (py_exe, udid, file_path)
        with os.popen(cmdline) as fd:
            content = fd.read()
        self.assertEqual(content, "yes\n")

        if "ProvisionsAllDevices" not in m:
            cmdline = "%s -m gplist --has-udid %s %s" % (
                py_exe, "xxx", file_path)
            with os.popen(cmdline) as fd:
                content = fd.read()
            self.assertEqual(content, "no\n")


if __name__ == "__main__":
    unittest.main()

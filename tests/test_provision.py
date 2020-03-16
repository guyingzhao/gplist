# -*- coding: utf-8 -*-
"""provision test
"""

from gplist.mobileprovision import MobileProvision
import os
import unittest


BASE_DIR = os.path.dirname(os.path.abspath(__file__))


class MobileProvisionTest(unittest.TestCase):

    def test_provision(self):
        provision_file = os.path.join(BASE_DIR, "embedded.mobileprovision")
        if not os.path.isfile(provision_file):
            print("%s not found, MobileProvisionTest skipped")

        m = MobileProvision.from_file(provision_file)
        self.assertIn("Name", m)
        self.assertFalse(m.is_expired())

        udid = m["ProvisionedDevices"][0]
        self.assertTrue(m.has_udid(udid))

        self.assertTrue(type(str), m.certs[0].sha1)
        for cert in m.certs:
            self.assertFalse(cert.is_expired())

        xml_data = m.to_xml()
        new_m = MobileProvision(xml_data)
        self.assertEqual(dict(new_m), dict(m))


if __name__ == "__main__":
    unittest.main()

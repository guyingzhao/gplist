# -*- coding: utf-8 -*-
"""test plist info
"""

from gplist.plist import PlistInfo, DictPlistInfo
import os
import unittest

import biplist


cur_dir = os.path.dirname(os.path.abspath(__file__))


class PlistInfoTest(unittest.TestCase):

    def check_plist(self, p):
        self.assertEqual(p["CFBundleIdentifier"], "com.guying.app.foo")
        self.assertEqual(p["CFBundleName"], "FooApp")
        self.assertEqual(p["CFBundleExecutable"], "FooApp")

    def test_binary_file(self):
        plist_file = os.path.join(cur_dir, "Info.plist")
        p = PlistInfo.from_file(plist_file)
        self.assertEqual(p.ref_size, 1)
        self.check_plist(p)

        temp_file = "temp.plist"
        p.to_binary_file(temp_file)
        self.assertTrue(os.path.isfile(temp_file))
        self.addCleanup(os.remove, temp_file)
        new_p = PlistInfo.from_file(temp_file)
        self.assertEqual(new_p.ref_size, 1)
        self.assertEqual(new_p, p)

    def test_large_binary_plist(self):
        plist_file = os.path.join(cur_dir, "large.plist")
        p = PlistInfo.from_file(plist_file)
        self.assertEqual(p.ref_size, 2)
        buf = p.to_binary()
        p2 = PlistInfo(buf)
        self.assertEqual(p2.ref_size, 2)
        self.assertEqual(dict(p), dict(p2))

    def test_app(self):
        app_path = os.path.join(cur_dir, "FooApp.app")
        p = PlistInfo.from_app(app_path)
        self.check_plist(p)

    def test_ipa(self):
        app_path = os.path.join(cur_dir, "FooApp.ipa")
        p = PlistInfo.from_app(app_path)
        self.check_plist(p)

    def test_xml_plist(self):
        plist_file = os.path.join(cur_dir, "Info.xml")
        p = PlistInfo.from_file(plist_file)
        self.check_plist(p)

        xml_file = "temp.xml"
        p.to_xml_file(xml_file)
        self.assertTrue(os.path.isfile(xml_file))
        self.addCleanup(os.remove, xml_file)
        new_p = PlistInfo.from_file(xml_file)
        self.assertEqual(new_p, p)

    def test_manipulate_property(self):
        plist_file = os.path.join(cur_dir, "Info.xml")
        p = PlistInfo.from_file(plist_file)
        p.add_property({"a": 1}, "foo")
        self.assertRaises(ValueError, p.add_property, 1, "foo")
        self.assertEqual(p["foo"], {"a": 1})
        p.update_property(2, "foo", "a")
        self.assertEqual(p["foo"]["a"], 2)
        p.remove_property("foo", "a")
        self.assertEqual(p["foo"], {})

        self.assertRaises(ValueError, p.remove_property, "xx")
        self.assertRaises(ValueError, p.update_property, "xx")

        with self.assertRaises(ValueError) as ctx:
            p.add_property(1, "foo", "b", "c")
        e = ctx.exception
        self.assertIn("b/c", e.args[0])

    def test_dict_plist(self):
        data = {"foo": {"a": 1}}
        p = DictPlistInfo(data)
        xml_file = "dict_plist.xml"
        p.to_xml_file(xml_file)
        self.assertTrue(os.path.isfile(xml_file))
        self.addCleanup(os.remove, xml_file)

        new_p = PlistInfo.from_file(xml_file)
        self.assertEqual(new_p, data)

        bin_file = "dict.plist"
        p.to_binary_file(bin_file)
        self.addCleanup(os.remove, bin_file)
        p2 = PlistInfo.from_file(bin_file)
        self.assertEqual(p, p2)

    def test_with_biplist(self):
        plist_file = os.path.join(cur_dir, "large.plist")
        p = PlistInfo.from_file(plist_file)
        p2 = biplist.readPlist(plist_file)
        self.assertEqual(p, p2)

        p3 = biplist.readPlistFromString(p.to_binary())
        self.assertEqual(p, p3)


if __name__ == "__main__":
    unittest.main(defaultTest="PlistInfoTest.test_with_biplist")

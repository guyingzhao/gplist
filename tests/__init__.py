# -*- coding: utf-8 -*-
"""unit tests
"""
import os
import sys
import unittest


def main():
    cur_dir = os.path.dirname(os.path.abspath(__file__))
    root_dir = os.path.dirname(cur_dir)
    if root_dir not in sys.path:
        sys.path.insert(0, root_dir)
    loader = unittest.TestLoader()
    tests = loader.discover(cur_dir)
    runner = unittest.runner.TextTestRunner()
    result = runner.run(tests)
    if result.wasSuccessful():
        code = 0
    else:
        code = 1
    sys.exit(code)


if __name__ == "__main__":
    main()

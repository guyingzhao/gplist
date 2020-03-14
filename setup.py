# -*- coding: utf-8 -*-
"""setup recipe
"""

import os

from setuptools import setup, find_packages

ROOT_DIR = os.path.dirname(os.path.abspath(__file__))


def generate_version():
    version_file = os.path.join(ROOT_DIR, "version.txt")
    if os.path.exists(version_file):
        with open(version_file) as fd:
            version = fd.read()
    else:
        version = "0.0.1"
        with open(version, "w") as fd:
            fd.write(version)
    return version


def get_description():
    readme = os.path.join(ROOT_DIR, "README.md")
    with open(readme) as fd:
        return fd.read()


if __name__ == "__main__":
    setup(
        name="gplist",
        version=generate_version(),
        packages=find_packages(exclude=("tests", "tests.*")),
        description="pure python plist manipulator",
        long_description=get_description(),
        long_description_content_type="text/markdown",
        author="guyingzhao",
        author_email="572488191@qq.com",
        url="https://github.com/guyingzhao/gplist.git",
        license="MIT"
    )

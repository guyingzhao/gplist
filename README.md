# plist

## Introduction

Info.plist is a manifest-liked file to store properties of an application. It's file format can be xml or binary. This file is a simple implementation of binary format deserialization.

## Usage

The `PlistInfo` is an ordered dict liked class, so you can treat it as an odered dict.

```python
from plist import PlistInfo

with open("Foo.app/Info.plist", "rb") as fd:
    p = PlistInfo
    print(p["CFBundleIdentifier"])
```


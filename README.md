# plist

[![Build Status](https://travis-ci.org/guyingzhao/gplist.svg?branch=master)](https://travis-ci.org/guyingzhao/gplist)

## Introduction

Info.plist is a manifest-liked file to store properties of an application. It's file format can be xml or binary. This file is a simple implementation of binary format deserialization.

## Usage

The `PlistInfo` is an ordered dict-liked class, so you can treat it as an ordered dict.

When parsing from binary data or file, `PlistInfo` will automatically detect the format and get the correct result.

### Binary Format

```python
import json
import os
from gplist.plist import PlistInfo

# raw binary
with open("FooApp.app/Info.plist", "rb") as fd:
    p = PlistInfo(fd.read())
    print(json.dumps(p, indent=2))

# from raw file
p = PlistInfo.from_file("FooApp.app/Info.plist")

# from app or ipa
p = PlistInfo.from_app("FooApp.app")
p = PlistInfo.from_app("FooApp.ipa")

foo_file = "foo.plist"
p.to_binary_file(foo_file)
assert os.path.isfile(foo_file)

buf = p.to_binary()
assert isinstance(buf, bytes)
```

### XML Format

```python
import os
from gplist.plist import PlistInfo

p = PlistInfo.from_app("FooApp.ipa")

foo_file = "foo_xml.plist"
p.to_xml_file(foo_file)
assert os.path.isfile(foo_file)

p.to_xml_file(foo_file, encoding="UTF-8", pretty=False)
assert os.path.isfile(foo_file)

buf = p.to_xml(encoding="UTF-8", pretty=True)
assert isinstance(buf, bytes)
```

### Property Manipulation

```python
from gplist.plist import PlistInfo

p = PlistInfo.from_app("FooApp.ipa")

p.add_property({"a": 1}, "foo")
assert p["foo"] == {"a": 1}

p.add_property("b", "foo", "b")
assert p["foo"]["b"] == "b"

p.update_property("c", "foo", "b")
assert p["foo"]["b"] == "c"

p.remove_property("foo", "a")
assert p["foo"] == {"b": "c"}
```


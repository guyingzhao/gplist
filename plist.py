# -*- coding: utf-8 -*-
"""plist
"""
from collections import OrderedDict
import datetime
import os
import shutil
import struct
import sys
import zipfile


if sys.version_info[0] == 2:
    PY2 = True
else:
    PY2 = False

STRUCT_SIZE_MAP = {1: "B", 2: "H", 3: "I", 4: "Q"}


def unzip(file_path, dir_path, members=None):
    temp_file = zipfile.ZipFile(file_path)
    try:
        if members is None:
            temp_file.extractall(path=dir_path)
        else:
            for member in members:
                temp_file.extract(member, path=dir_path)
    finally:
        temp_file.close()


class UID(int):
    def __init__(self, val):
        if val >= 1 << 64 or val < 0:
            raise ValueError("UID=%s not in range 0~2^64" % val)
        super(UID, self).__init__()

    def __str__(self):
        return "<UID %d>" % int(self)

    __repr__ = __str__


class PlistInfo(OrderedDict):

    def __init__(self, binary_data):
        self._binary_data = binary_data
        self._objs = OrderedDict()
        self._parse()
        super(PlistInfo, self).__init__(self._objs[0])

    @classmethod
    def from_file(cls, plist_file):
        if not os.path.exists(plist_file):
            raise ValueError("plist_info=%s is not valid" % plist_file)
        with open(plist_file, "rb") as fd:
            return cls(fd.read())

    @classmethod
    def from_app(cls, app_path):
        """from a *.ipa or *.app file
        """
        if not os.path.exists(app_path):
            raise ValueError("app_path=%s invalid" % app_path)
        if app_path.endswith(".ipa"):
            dir_path = os.path.join(os.getcwd(), "temp")
            base_name = os.path.basename(app_path)
            app_name = os.path.splitext(base_name)[0]
            plist_item = "%s.app/Info.plist" % app_name
            unzip(app_path, dir_path, [plist_item])
            plist_file = os.path.join(dir_path, plist_item)
            if not os.path.isfile(plist_file):
                raise RuntimeError("plist_file=%s not found" % plist_file)
            p = cls.from_file(plist_file)
            shutil.rmtree(dir_path, ignore_errors=True)
            return p
        elif app_path.endswith(".app"):
            plist_file = os.path.join(app_path, "Info.plist")
            if not os.path.isfile(plist_file):
                raise RuntimeError("plist_file=%s not found" % plist_file)
            return cls.from_file(plist_file)

    def _get_fmt(self):
        header = self._binary_data[:32]
        if header.startswith(b"<?xml") or header.startswith(b"<plist"):
            return "xml"
        elif header.startswith(b"bplist00"):
            return "binary"
        else:
            raise ValueError("header=%s unrecognized" % header)

    def _read_ints(self, count, unit_size, offset):
        obj_offsets = []
        buf_end = offset + count * unit_size
        obj_buf = self._binary_data[offset:buf_end]
        struct_type = ">" + STRUCT_SIZE_MAP[unit_size]
        for i in range(count):
            start = unit_size * i
            end = start + unit_size
            obj_size = struct.unpack(struct_type,
                                     obj_buf[start:end])[0]
            obj_offsets.append(obj_size)
        return obj_offsets

    def _parse_binary(self):
        tailer = self._binary_data[-32:]
        unit_size, self.ref_size, obj_count, top, table_offset = struct.unpack(
            ">6xBBQQQ", tailer)
        self.obj_offsets = self._read_ints(obj_count, unit_size, table_offset)
        self._read_object(top)

    def _read_object(self, obj_index):
        if obj_index in self._objs:
            return self._objs[obj_index]
        obj_offset = self.obj_offsets[obj_index]
        if PY2:
            token = ord(self._binary_data[obj_offset])
        else:
            token = self._binary_data[obj_offset]
        token_h, token_l = token & 0xf0, token & 0x0f
        start = obj_offset + 1
        if token == 0x0:
            result = None
        elif token == 0x8:
            result = False
        elif token == 0x9:
            result = True
        elif token == 0x0f:
            result = b""
        elif token_h == 0x10:  # int
            length = 1 << token_l
            end = start + length
            struct_type = STRUCT_SIZE_MAP[length]
            obj_buf = self._binary_data[start:end]
            result = struct.unpack(">" + struct_type, obj_buf)[0]
        elif token == 0x22:  # float
            end = start + 4
            obj_buf = self._binary_data[start:end]
            result = struct.unpack(">f", obj_buf)[0]
        elif token == 0x23:  # double
            end = start + 8
            obj_buf = self._binary_data[start:end]
            result = struct.unpack(">d", obj_buf)[0]
        elif token == 0x33:  # date
            obj_buf = self._binary_data[start:end]
            end = start + 8
            delta = struct.unpack(">d", obj_buf)[0]
            date = datetime.datetime(2001, 1, 1) + \
                datetime.timedelta(seconds=delta)
            result = date
        elif token_h == 0x40:  # data
            obj_size, length_size = self._get_size(token_l, start)
            start += length_size
            end = start + obj_size
            result = self._binary_data[start:end]
        elif token_h == 0x50:  # ascii string
            obj_size, length_size = self._get_size(token_l, start)
            start += length_size
            end = start + obj_size
            result = self._binary_data[start:end].decode("ascii")
        elif token_h == 0x60:  # unicode
            obj_size, length_size = self._get_size(token_l, start)
            start += length_size
            end = start + obj_size * 2
            result = self._binary_data[start:end].decode('utf-16be')
        elif token_h == 0x80:  # UID
            length = token_l
            end = start + length
            struct_type = STRUCT_SIZE_MAP[length]
            obj_buf = self._binary_data[start:end]
            result = UID(struct.unpack(">" + struct_type, obj_buf)[0])
        elif token_h == 0xa0:  # array
            obj_count, length_size = self._get_size(token_l, start)
            start += length_size
            obj_offsets = self._read_ints(obj_count, self.ref_size, start)
            result = []
            for index in obj_offsets:
                result.append(self._read_object(index))
        elif token_h == 0xd0:  # dict
            obj_count, length_size = self._get_size(token_l, start)
            start += length_size
            key_offsets = self._read_ints(obj_count, self.ref_size, start)
            start += obj_count * self.ref_size
            value_offsets = self._read_ints(obj_count, self.ref_size, start)
            result = {}
            for key_index, value_index in zip(key_offsets, value_offsets):
                key = self._read_object(key_index)
                value = self._read_object(value_index)
                result[key] = value
        else:
            raise ValueError("invalid token=0x%x" % token)
        self._objs[obj_index] = result
        return result

    def _get_size(self, token_l, offset):
        if token_l == 0xf:
            if PY2:
                length_size = 1 << (ord(self._binary_data[offset]) & 0x3)
            else:
                length_size = 1 << (self._binary_data[offset] & 0x3)
            struct_type = STRUCT_SIZE_MAP[length_size]
            length_buf = self._binary_data[(
                offset + 1):(offset + 1 + length_size)]
            return struct.unpack(">" + struct_type, length_buf)[0], length_size + 1
        else:
            return token_l, 0

    def _parse(self):
        fmt = self._get_fmt()
        if fmt == "binary":
            self._parse_binary()
        else:
            raise ValueError("fmt=%s not supported yet" % fmt)

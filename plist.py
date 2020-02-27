# -*- coding: utf-8 -*-
"""plist
"""
from collections import OrderedDict
import datetime
import os
import struct


STRUCT_SIZE_MAP = {1: "B", 2: "H", 3: "I", 4: "Q"}


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
            end = start + 1 << token_l
            obj_buf = self._binary_data[start:end]
            result = int.from_bytes(obj_buf, "big", signed=token_l >= 3)
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
            end = start + token_l
            result = UID(int.from_bytes(self._binary_data[start:end], 'big'))
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

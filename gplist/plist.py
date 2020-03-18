# -*- coding: utf-8 -*-
"""plist
"""
from collections import OrderedDict
from xml.dom.expatbuilder import parseString
from xml.dom.minidom import Element, Document, DocumentType
import base64
import datetime
import os
import shutil
import struct
import sys
import zipfile


if sys.version_info[0] == 2:
    PY2 = True
    string_type = basestring
else:
    PY2 = False
    string_type = str


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


def get_ipa_app(ipa_file):
    with zipfile.ZipFile(ipa_file) as fd:
        for item in fd.namelist():
            if item[:-1].endswith(".app"):
                return item
        else:
            raise RuntimeError("no .app directory found in %s" % ipa_file)


class UID(int):
    def __init__(self, val):
        if val >= 1 << 64 or val < 0:
            raise ValueError("UID=%s not in range 0~2^64" % val)
        super(UID, self).__init__()

    def __str__(self):
        return "<UID %d>" % int(self)

    __repr__ = __str__


class Data(str):

    def __init__(self, val):
        super(Data, self).__init__()
        self._raw = None

    @property
    def raw(self):
        if self._raw is None:
            if PY2:
                self._raw = base64.decodestring(self)
            else:
                self._raw = base64.decodebytes(self.encode("ascii"))
        return self._raw


class PlistInfo(OrderedDict):

    def __init__(self, binary_data):
        self._binary_data = binary_data
        self._objs = OrderedDict()
        self._parse()
        super(PlistInfo, self).__init__(self._objs[0])

    def __eq__(self, other):
        return dict.__eq__(self, other)

    def __ne__(self, other):
        return dict.__ne__(self, other)

    @property
    def format(self):
        return self._get_fmt()

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
            raise ValueError("app_path=%s not found" % app_path)
        app_path = app_path.rstrip(os.path.sep)
        if app_path.endswith(".ipa"):
            dir_path = os.path.join(os.getcwd(), "temp")
            app_item = get_ipa_app(app_path)
            plist_item = app_item + "Info.plist"
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
        else:
            raise ValueError("app_path=%s is invalid" % app_path)

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
            obj_offset = struct.unpack(struct_type,
                                       obj_buf[start:end])[0]
            obj_offsets.append(obj_offset)
        return obj_offsets

    def _parse_binary(self):
        tailer = self._binary_data[-32:]
        unit_size, self.ref_size, obj_count, top, table_offset = struct.unpack(
            ">6xBBQQQ", tailer)
        self.obj_offsets = self._read_ints(
            obj_count, unit_size, table_offset)
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
            result = Data(self._binary_data[start:end])
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

    def _pack_int(self, value):
        for max_int, bit_offset in [(1 << 8, 0), (1 << 16, 1), (1 << 32, 2), (1 << 64, 3)]:
            if value < max_int:
                break
        else:
            raise ValueError("int=%s out of range %s" % (value, 1 << 64))
        struct_type = STRUCT_SIZE_MAP[1 << bit_offset]
        int_buf = struct.pack(">" + struct_type, value)
        return int_buf, bit_offset | 0x10, 1 << bit_offset

    def _write_object(self, value, index, offset):
        if not isinstance(value, (dict, list, bool)):
            if value in self._values:
                value_index = self._values[value]
                return value_index, b"", offset
            else:
                self._values[value] = index

        self.obj_count += 1
        self.obj_offsets[index] = offset
        value_buf = b""
        if value is None:
            token = 0x0
        elif value is False:
            token = 0x8
        elif value is True:
            token = 0x9
        elif value == "":
            token = 0xf
        elif isinstance(value, int):
            token_h = 0x10
            value_buf, token_l, _ = self._pack_int(value)
            token = token_h | token_l
        elif isinstance(value, float):  # we don't use double
            token = 0x22
            value_buf = struct.pack(">f", value)
        elif isinstance(value, datetime.datetime):
            token = 0x33
            date_delta = value - datetime.datetime(2001, 1, 1)
            value_buf = struct.pack(">d", date_delta.seconds)
        elif isinstance(value, Data):
            token_h = 0x40
            length = len(value)
            if length < 0xf:
                token_l = length
            else:
                token_l = 0xf
                int_buf, bit_offset, _ = self._pack_int(length)
                value_buf += int_buf
                value_buf += struct.pack("B", bit_offset)
            value_buf += value
            token = token_h | token_l
        elif isinstance(value, string_type):
            is_ascii = True
            target_value = value
            if PY2:
                if isinstance(value, str):
                    try:
                        value.decode("ascii")
                    except UnicodeError:
                        is_ascii = False
                        try:
                            target_value = value.decode("utf8")
                        except UnicodeError:
                            target_value = value.decode("gbk")
                else:
                    try:
                        target_value = value.encode("ascii")
                    except UnicodeError:
                        target_value = value
                        is_ascii = False
            else:
                try:
                    target_value = value.encode("ascii")
                except UnicodeError:
                    is_ascii = False

            if is_ascii:
                token_h = 0x50
            else:
                token_h = 0x60

            # string length instead of bytes length
            length = len(target_value)
            if length < 0xf:
                token_l = length
            else:
                token_l = 0xf
                int_buf, bit_offset, _ = self._pack_int(length)
                value_buf += struct.pack("B", bit_offset)
                value_buf += int_buf
            if is_ascii:
                value_buf += target_value
            else:
                value_buf += value.encode("utf-16be")
            token = token_h | token_l
        elif isinstance(value, UID):
            token_h = 0x80
            int_buf, bit_offset, _ = self._pack_int(value)
            value_buf += int_buf
            token_l = 1 << bit_offset
            token = token_h | token_l
        elif isinstance(value, list):
            token_h = 0xa0
            length = len(value)
            if length < 0xf:
                token_l = length
                length_bytes = 0
            else:
                token_l = 0xf
                int_buf, bit_offset, length_bytes = self._pack_int(length)
                value_buf += struct.pack("B", bit_offset)
                value_buf += int_buf
            item_count = len(value)
            offset += len(value_buf) + item_count + length_bytes + 1
            data_buf = b""
            for item_value in value:
                obj_offset, item_buf, offset = self._write_object(
                    item_value, self.obj_count, offset)
                value_buf += struct.pack("B", obj_offset)
                self.obj_offsets[self.obj_count] = offset
                data_buf += item_buf
            value_buf += data_buf
            token = token_h | token_l
        elif isinstance(value, dict):
            token_h = 0xd0
            length = len(value)
            if length < 0xf:
                token_l = length
                length_bytes = 0
            else:
                token_l = 0xf
                int_buf, bit_offset, length_bytes = self._pack_int(length)
                value_buf += struct.pack("B", bit_offset)
                value_buf += int_buf
            item_count = len(value)
            offset += len(value_buf) + 2 * item_count + length_bytes
            if index != 0:
                offset += 1
            data_buf = b""
            for k in value.keys():
                obj_offset, k_buf, offset = self._write_object(
                    k, self.obj_count, offset)
                data_buf += k_buf
                value_buf += struct.pack("B", obj_offset)
            for v in value.values():
                obj_offset, v_buf, offset = self._write_object(
                    v, self.obj_count, offset)
                data_buf += v_buf
                value_buf += struct.pack("B", obj_offset)
            value_buf += data_buf
            token = token_h | token_l
        else:
            raise ValueError("unexpected value=%s" % value)
        buf = struct.pack("B", token) + value_buf
        if not isinstance(value, (list, dict)):
            offset += len(buf)
        return index, buf, offset

    def to_binary(self):
        self.obj_count = 0
        self.obj_offsets = {}
        self._values = {}
        _, buf, offset = self._write_object(self, 0, 8)
        for obj_offset in self.obj_offsets.values():
            buf += struct.pack(">H", obj_offset)
        buf += struct.pack(">6xBBQQQ", 2, 1, self.obj_count,
                           0, offset)
        return b"bplist00" + buf

    def to_binary_file(self, file_path):
        with open(file_path, "wb") as fd:
            fd.write(self.to_binary())

    def _parse(self):
        fmt = self._get_fmt()
        if fmt == "binary":
            self._parse_binary()
        elif fmt == "xml":
            self._parse_xml()
        else:
            raise ValueError("unsupported format: %s" % fmt)

    def _get_next_element(self, root):
        index = 0
        while True:
            try:
                child = root.childNodes[index]
            except IndexError:
                break
            else:
                if isinstance(child, Element):
                    yield child
                index += 1

    def _get_plist_node(self):
        dom = parseString(self._binary_data)
        for child in self._get_next_element(dom):
            tree = child
            break
        for child in self._get_next_element(tree):
            if child is None:
                raise RuntimeError("dict node for plist not found")
            if child.nodeName == "dict":
                tree = child
                break
        return tree

    def _get_node_value(self, node):
        node_type = node.nodeName
        if node_type == "true":
            node_value = True
        elif node_type == "false":
            node_value = False
        elif node_type == "string":
            if len(node.childNodes) > 0:
                node_value = node.childNodes[0].nodeValue
            else:
                node_value = ""
        elif node_type == "integer":
            node_value = int(node.childNodes[0].nodeValue)
        elif node_type == "real":
            node_value = float(node.childNodes[0].nodeValue)
        elif node_type == "dict":
            node_value = OrderedDict()
        elif node_type == "array":
            node_value = []
        elif node_type == "data":
            content = node.childNodes[0].nodeValue
            if PY2:
                node_value = Data(content)
            else:
                node_value = Data(content)
        elif node_type == "date":
            content = node.childNodes[0].nodeValue
            node_value = datetime.datetime.strptime(
                content, "%Y-%m-%dT%H:%M:%SZ")
        else:
            raise ValueError("unexpected node_type=%s" % node_type)
        return node_value

    def _parse_xml(self):
        tree = self._get_plist_node()
        d = OrderedDict()
        nodes = [(tree, d)]
        while nodes:
            root, value = nodes.pop(0)
            if root.nodeName == "dict":
                elem_nodes = self._get_next_element(root)
                for child in elem_nodes:
                    key = child.childNodes[0].nodeValue
                    value_node = next(elem_nodes)
                    child_value = self._get_node_value(value_node)
                    if value_node.nodeName in ["dict", "array"]:
                        nodes.append([value_node, child_value])
                    value[key] = child_value
            elif root.nodeName == "array":
                elem_nodes = self._get_next_element(root)
                for child in elem_nodes:
                    child_value = self._get_node_value(child)
                    if child.nodeName in ["dict", "array"]:
                        nodes.append([child, child_value])
                    value.append(child_value)
            else:
                raise TypeError("unexpected node type: %s" % root.nodeName)
        self._objs[0] = d

    def _to_dom_node(self, data, dom):
        if isinstance(data, bool):
            if data is True:
                data_node = dom.createElement("true")
            else:
                data_node = dom.createElement("false")
        elif isinstance(data, string_type):
            data_node = dom.createElement("string")
            if data:
                text_node = dom.createTextNode(data)
                data_node.appendChild(text_node)
        elif isinstance(data, int):
            data_node = dom.createElement("integer")
            text_node = dom.createTextNode(str(data))
            data_node.appendChild(text_node)
        elif isinstance(data, float):
            data_node = dom.createElement("real")
            text_node = dom.createTextNode(str(data))
            data_node.appendChild(text_node)
        elif isinstance(data, Data):
            data_node = dom.createElement("data")
            text_node = dom.createTextNode(data)
            data_node.appendChild(text_node)
        elif isinstance(data, datetime.datetime):
            data_node = dom.createElement("date")
            data = data.strftime("%Y-%m-%dT%H:%M:%SZ")
            text_node = dom.createTextNode(data)
            data_node.appendChild(text_node)
        else:
            raise ValueError("value=%s is unsupported" % data)
        return data_node

    def to_xml(self, encoding="UTF-8", pretty=True):
        dom = Document()
        dom.version = "1.0"
        dom.encoding = "UTF-8"
        doc_type = DocumentType("plist")
        doc_type.publicId = "-//Apple Computer//DTD PLIST 1.0//EN"
        doc_type.systemId = "http://www.apple.com/DTDs/PropertyList-1.0.dtd"
        dom.appendChild(doc_type)

        plist_node = dom.createElement("plist")
        plist_node.setAttribute("version", "1.0")
        dom.appendChild(plist_node)

        plist_root = dom.createElement("dict")
        plist_node.appendChild(plist_root)
        temp_pairs = [(self, plist_root)]
        while temp_pairs:
            data, root = temp_pairs.pop(0)
            if isinstance(data, dict):
                for k, v in data.items():
                    k_node = dom.createElement("key")
                    text_node = dom.createTextNode(k)
                    k_node.appendChild(text_node)
                    root.appendChild(k_node)

                    if isinstance(v, dict):
                        v_node = dom.createElement("dict")
                        temp_pairs.append((v, v_node))
                    elif isinstance(v, list):
                        v_node = dom.createElement("array")
                        temp_pairs.append((v, v_node))
                    else:
                        v_node = self._to_dom_node(v, dom)
                    root.appendChild(v_node)
            elif isinstance(data, list):
                for v in data:
                    if isinstance(v, dict):
                        v_node = dom.createElement("dict")
                        temp_pairs.append((v, v_node))
                    elif isinstance(v, list):
                        v_node = dom.createElement("array")
                        temp_pairs.append((v, v_node))
                    else:
                        v_node = self._to_dom_node(v, dom)
                    root.appendChild(v_node)
            else:
                data_node = self._to_dom_node(data, dom)
                root.appendChild(data_node)

        if pretty:
            xml_content = dom.toprettyxml(encoding=encoding)
        else:
            xml_content = dom.toxml(encoding=encoding)
        return xml_content

    def to_xml_file(self, file_path, encoding="UTF-8", pretty=True):
        with open(file_path, "wb") as fd:
            fd.write(self.to_xml(encoding=encoding,
                                 pretty=pretty))

    def _get_prop_parent(self, prop_fields):
        if len(prop_fields) < 1:
            raise ValueError("at least one field needs to be specified")
        temp_value = self
        count = 0
        for field in prop_fields[:-1]:
            try:
                temp_value = temp_value[field]
                count += 1
            except (IndexError, KeyError):
                found_path = "/".join(prop_fields[:count])
                rest_path = "/".join(prop_fields[count:])
                raise ValueError("`%s` of `%s` not found" %
                                 (rest_path, found_path))

        return temp_value, prop_fields[-1]

    def add_property(self, value, *prop_fields):
        """add property to plist

        :param value: property value
        :type  value: any
        :param prop_fields: property path
        :type  prop_fields: tuple
        """
        parent, key = self._get_prop_parent(prop_fields)
        if key in parent:
            raise ValueError("%s already exists" % ".".join(prop_fields))
        parent[key] = value

    def update_property(self, value, *prop_fields):
        """update property to plist

        :param value: property value
        :type  value: any
        :param prop_fields: property path
        :type  prop_fields: tuple
        """
        parent, key = self._get_prop_parent(prop_fields)
        if key not in parent:
            raise ValueError("%s not found" % ".".join(prop_fields))
        parent[key] = value

    def remove_property(self, *prop_fields):
        """remove property from plist

        :param value: property value
        :type  value: any
        :param prop_fields: property path
        :type  prop_fields: tuple
        """
        parent, key = self._get_prop_parent(prop_fields)
        if key not in parent:
            raise ValueError("%s not found" % ".".join(prop_fields))
        del parent[key]


class DictPlistInfo(PlistInfo):
    """plist information from dict data
    """

    def __init__(self, data):
        self._objs = OrderedDict()
        super(PlistInfo, self).__init__(data)

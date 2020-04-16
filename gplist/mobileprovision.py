# -*- coding: utf-8 -*-
"""mobile provision file serializing
"""

from datetime import datetime
import binascii

from cryptography import x509
from cryptography.hazmat import backends
from cryptography.hazmat.primitives.hashes import SHA1
from gplist.plist import PlistInfo, PY2


class Cert(object):

    def __init__(self, cert_obj):
        self._cert = cert_obj
        self._sha1 = None

    @property
    def cert(self):
        return self._cert

    @property
    def sha1(self):
        if self._sha1 is None:
            data = self._cert.fingerprint(SHA1())
            data = binascii.hexlify(data)
            if not PY2:
                data = data.decode("ascii")
            self._sha1 = data.upper()
        return self._sha1

    @property
    def invalid_before(self):
        return self._cert.not_valid_before

    @property
    def invalid_after(self):
        return self._cert.not_valid_after

    def is_expired(self):
        now = datetime.utcnow()
        return now < self.invalid_before or now > self.invalid_after


class MobileProvision(PlistInfo):

    def __init__(self, binary):
        super(MobileProvision, self).__init__(binary)
        self._certs = None

    @classmethod
    def from_file(cls, provision_file):
        with open(provision_file, "rb") as fd:
            content = fd.read()
        start_pos = content.find(b"<?xml")
        end_pos = content.find(b"</plist>") + len(b"</plist>")
        plist_buf = content[start_pos:end_pos]
        return cls(plist_buf)

    @property
    def certs(self):
        if self._certs is None:
            backend = backends.default_backend()
            self._certs = []
            for cert_data in self["DeveloperCertificates"]:
                cert_obj = x509.load_der_x509_certificate(
                    cert_data.raw, backend)
                self._certs.append(Cert(cert_obj))
        return self._certs

    def is_expired(self):
        return datetime.utcnow() > self["ExpirationDate"]

    def has_udid(self, udid):
        if "ProvisionsAllDevices" in self:
            return self["ProvisionsAllDevices"]
        else:
            return udid in self["ProvisionedDevices"]

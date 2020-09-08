# This module is a placeholder that will be replaced by real JWS support.
# Real JWS support is easy, in theory--but it introduces some dependencies
# on actual key types and on underlying crypto suites that I'm not ready for.

import base64
import hashlib


def _hash(val):
    if isinstance(val, str):
        val = val.encode('utf-8')
    # We're going to make the digest much smaller than 256 bits, just to make our
    # pseudo values easier to read.
    digest = hashlib.sha256(val).digest()[:8]
    return val, digest


def _txt(bytes):
    return base64.urlsafe_b64encode(bytes).decode('ascii')


def sign(content, key):
    content, hash_of_content = _hash(content)
    key, hash_of_key = _hash(key)
    signer = hashlib.sha256()
    signer.update(content)
    signer.update(key)
    signature = signer.digest()[:8]
    x = _txt(signature)
    y = _txt(hash_of_content)
    z = _txt(hash_of_key)
    return x + '.' + y + '.' + z


def verify(content, key, pseudo_jws):
    return sign(content, key) == pseudo_jws

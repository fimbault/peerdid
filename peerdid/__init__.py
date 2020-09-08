import re

PEER_DID_PAT = re.compile(r'^did:peer:(1)(z)([1-9a-km-zA-HJ-NP-Z]{46})$')


def get_predefined_did_value(char):
    return 'did:peer:1z' + 46*char


def is_valid_peer_did(did: str):
    if did:
        return bool(PEER_DID_PAT.match(did))


def abbreviate(did: str):
    return did[:15] + '...' + did[-3:]


def is_reserved_peer_did(did: str):
    if did:
        m = PEER_DID_PAT.match(did)
        if m:
            c = did[11].lower()
            for i in range(12, 57):
                if did[i].lower() != c:
                    return False
            return True
    return False


def compare_peer_dids(did_a, did_b):
    # Right now, we only know how to compare DIDs that use base58 encoding.
    # That comparison is case-sensitive, so we really don't need a fancy
    # function. However, that may change in the future. It's simpler to expose
    # the function so code can call it; this function can then insulate the
    # caller from future evolutions of the spec...
    assert did_a[10] == 'z'
    assert did_b[10] == 'z'
    return -1 if did_a < did_b else 1 if did_a > did_b else 0

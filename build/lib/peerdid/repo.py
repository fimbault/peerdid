import os

from .diddoc import DIDDoc, get_predefined
from .delta import Delta
from .file import File, canonical_fname
from . import is_valid_peer_did, is_reserved_peer_did


class Repo:
    """
    Backing storage for a collection of peer DIDs.
    """
    def __init__(self, path):
        self.path = Repo.norm_path(path)
        assert not os.path.isfile(path)

    def get_state(self, *dids):
        state = []
        for did in dids:
            file = self.get_doc(did).file
            state.append({did: file.snapshot})
        return state

    def new_doc(self, genesis_doc, signatures=[]):
        if not os.path.isdir(self.path):
            # Create a single folder, but not multiple layers of folders.
            os.mkdir(self.path)
        if isinstance(genesis_doc, Delta):
            delta = genesis_doc
        else:
            delta = Delta(genesis_doc, signatures)
        path = os.path.join(self.path, canonical_fname(delta.encnumbasis))
        f = File(path)
        f.append(delta)
        return f.did

    def get_doc(self, did):
        if is_valid_peer_did(did):
            if is_reserved_peer_did(did):
                return get_predefined(did[13])
            path = os.path.join(self.path, canonical_fname(did))
            if os.path.isfile(path):
                return DIDDoc(path)

    def resolve(self, did, as_of_time=None):
        if is_valid_peer_did(did):
            if is_reserved_peer_did(did):
                return get_predefined(did[13])
            else:
                path = os.path.join(self.path, canonical_fname(did))
                if os.path.isfile(path):
                    doc = DIDDoc(path)
                    return doc.resolve(as_of_time)

    @classmethod
    def norm_path(cls, path):
        return os.path.normpath(os.path.abspath(os.path.expanduser(path)))
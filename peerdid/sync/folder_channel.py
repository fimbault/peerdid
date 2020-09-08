import os
import uuid


class Channel:
    """
    Provide a duplex channel that works by manipulating files in a folder. This
    is a simple substitute for full-blown DIDComm as a communications channel. It
    simplifies our reference implementation of peer DIDs, makes testing convenient,
    and proves that peer DIDs can be built without DIDComm. However, DIDComm is
    still the preferred mechanism, because it provides security, decentralization,
    and transport independence in ways that alternatives do not. This channel is
    not intended to be used in production.
    """

    def __init__(self, folder: str, is_destward: bool = True):
        """
        Claim a folder in the file system as the locus of message
        sending and receiving.

        :param folder: Container for message files. It must exist.
        :param is_destward: Tells whether to treat the folder as
          destward or srcward, relative to the owner of this channel
          object. This parameter exists so the same folder can be used
          in complimentary ways by a producer and consumer of messages. If
          you are using a Channel on the back side of a relay (emitting
          to the file system as you get closer to the destination), then
          is_destward is true. This means that when a send() method is called,
          *.in files are written, and when the receive() method is called,
          *.out files are read. If you are writing an agent that uses a
          Channel as its intake mechanism, then is_destward is false. In
          this case, when a send() method is called, *.out files are
          written, and when a receive() method is called, *.in files
          are read:
          
          Channel is destward of the relay (write *.in; read *.out)
                             |
          http -> relay -> FolderChannel -> agent
                                     |
               Channel is srcward of the agent (read from *.in; write to *.out)
        """
        self.is_destward = is_destward
        self.folder = os.path.normpath(os.path.abspath(os.path.expanduser(folder)))
        if not os.path.isdir(folder):
            raise Exception("Folder %s must exist." % folder)

    @property
    def read_ext(self):
        """Which file extension do I read from?"""
        return ".out" if self.is_destward else ".in"

    @property
    def write_ext(self):
        """Which file extension do I write to?"""
        return ".in" if self.is_destward else ".out"

    @property
    def direction(self):
        return 'destward' if self.is_destward else 'srcward'

    def send(self, payload, id=None, *args):
        if isinstance(payload, str):
            payload = payload.encode('utf-8')
        if id is None:
            id = str(uuid.uuid4())
        # Because writing is not an atomic operation, create the file with
        # a temp name, then rename it once the file has been written and
        # closed. This prevents code from peeking/reading the file before
        # we are done writing it.
        temp_fname = os.path.join(self.folder, '.' + id + '.tmp')
        perm_fname = os.path.join(self.folder, id + self.write_ext)
        with open(temp_fname, 'wb') as f:
            f.write(payload)
        os.rename(temp_fname, perm_fname)
        return id

    def peek(self, filter=None):
        for x in _next_item_name(self.folder, self.read_ext, filter):
            return True

    def receive(self, filter=None):
        return _item_content(self.folder, self.read_ext, filter)

    def __str__(self):
        return self.direction + '=' + self.folder


def _next_item_name(folder, ext, filter=None):
    for root, folders, files in os.walk(folder):
        folders.clear()
        for fname in files:
            # Ignore files that are not messages.
            if fname.endswith(ext):
                if (filter is None) or (fname.startswith(filter)):
                    yield fname


async def _pop_item(fpath):
    with open(fpath, 'rb') as f:
        data = f.read()
    os.remove(fpath)
    return data


async def _item_content(folder, ext, filter=None):
    """Return next as mwc.MessageWithContext, or None if nothing is found."""
    data = None
    for fname in _next_item_name(folder, ext, filter):
        data = await _pop_item(os.path.join(folder, fname))
        return data

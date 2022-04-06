#!/usr/bin/env python3

# tinyssb/repository.py  -- disk storage for logs and blobs (sidechains)

'''
directory structure of a repository:

  path_to_repo_data/
      +--> config.json
      +--> _logs
      |       +--> FID1_IN_HEX.log
      |       `--> FID2_IN_HEX.log
      `--> _blob
              +--> 05/REST_OF_HASHPTR1_IN_HEX
              +--> 05/REST_OF_HASHPTR2_IN_HEX
              `--> AA/REST_OF_HASHPTR3_IN_HEX

blobs: stored as files of length 120 (!)
logs: see end of this file for a description of the log file format,
      it's a multiple of 128B
'''

import hashlib
import os
import sys

from tinyssb import packet, util

if sys.implementation.name == 'micropython':
    def isfile(fn):
        try:    return os.stat(fn)[0] & 0x8000 != 0
        except: return False
    def isdir(dn):
        try:    return os.stat(fn)[0] & 0x4000 != 0
        except: return False
else:
    isfile = os.path.isfile
    isdir  = os.path.isdir

class REPO:

    def __init__(self, path, verify_signature_fct):
        self.path = path
        self.vfct = verify_signature_fct
        try: os.mkdir(self.path + '/_logs')
        except: pass
        try: os.mkdir(self.path + '/_blob')
        except: pass
        self.open_logs = {}

    def _log_fn(self, fid):
        return self.path + '/_logs/' + util.hex(fid) + '.log'

    def _blob_fn(self, hashval):
        h = util.hex(hashval)
        return self.path + '/_blob/' + h[:2] + '/' + h[2:]

    def listlog(self):
        lst = []
        for fn in os.listdir(self.path + '/_logs/'):
            lst.append(util.fromhex(fn.split('.')[0]))
        return lst

    def create_log(self, fid, trusted_seq, trusted_msgID,
                   buf120=None, parent_fid=bytes(32), parent_seq=0):
        # use this to create a file where entries can start at any index
        fn = self._log_fn(fid)
        if isfile(fn):
            print("log", fn, "already exists")
            return None
        hdr  = bytes(12) # should have version and other magic bytes
        hdr += fid
        hdr += parent_fid + parent_seq.to_bytes(4, 'big')
        buf  = trusted_seq.to_bytes(4, 'big') + trusted_msgID
        hdr += buf
        if buf120 == None:
            hdr += buf # copy trusted seq number as front information
            pass
        else:
            pkt = packet.from_bytes(buf120, fid, trusted_seq+1, trusted_msgID,
                                    self.vfct)
            if pkt == None: return None
            hdr += pkt.seq.to_bytes(4, 'big') + pkt.mid # as front
        assert len(hdr) == 128, "log file header must be 128B"
        with open(fn, 'wb') as f:
            f.write(hdr)
            if buf120 != None: f.write(bytes(8) + buf120)
        return self.get_log(fid)

    def genesis_log(self, fid, buf48, signFct,
                    parent_fid=bytes(32), parent_seq=0):
        # use this to create a file where entries start at seq=1
        prev = fid[:20]   # this is a convention, like a self-signed cert
        genesis_block = packet.PACKET(fid, 1, prev)
        genesis_block.mk_plain_entry(buf48, signFct)
        return self.create_log(fid, 0, prev, genesis_block.wire,
                               parent_fid, parent_seq)

                            
    def get_log(self, fid): # returns a LOG, or None
        if not fid in self.open_logs:
            fn = self._log_fn(fid)
            if not isfile(fn): return None
            l = LOG(fn, self.vfct)
            if l == None: return None
            self.open_logs[fid] = l
        return self.open_logs[fid]

    def add_blob(self, buf120):
        hptr = hashlib.sha256(buf120).digest()[:20]
        fn = self._blob_fn(hptr)
        dn = fn[:-39]
        if not isdir(dn):   os.mkdir(dn)
        if isfile(fn):      return
        with open(fn, "wb+") as f:  f.write(buf120)
        return hptr

    def get_blob(self, hashptr):
        try:
            with open(self._blob_fn(hashptr), "rb") as f: return f.read(120)
        except Exception as e:
            # print("get_blob", e)
            pass
        return None

    def persist_chain(self, pkt, blobs):
        # first persist the blobs as otherwise we could have stored the
        # log entry but not all blobs, in case of a node crash
        for b in blobs:
            self.add_blob(b)
        feed = self.get_log(pkt.fid)
        # should we check our own signature here, use feed.append(pkt.wire)?
        feed._append(pkt)
        return [pkt.wire] + blobs
        
    '''
    def get_peer(fid): # -> PEER
        pass

    def get_user(fid): # -> USER
        pass

    def __del__(self):
       delete all log objects in self.open_logs
    '''

# ----------------------------------------------------------------------

class LOG:

    def __init__(self, fn, verify_signature_fct):
        self.vfct = verify_signature_fct
        self.f = open(fn, 'rb+')
        self.f.seek(0)
        hdr = self.f.read(128)
        hdr = hdr[12:]                                # first 12B unused
        self.fid  = hdr[:32]
        self.parfid = hdr[32:64]
        self.parseq = int.from_bytes(hdr[64:68], 'big')
        self.anchrS = int.from_bytes(hdr[68:72], 'big') # trusted seqNr
        self.anchrM = hdr[72:92]                        # trusted msgID
        self.frontS = int.from_bytes(hdr[92:96], 'big') # seqNr of last rec
        self.frontM = hdr[96:116]                       # msgID of last rec
        self.f.seek(0, 2)
        assert self.f.tell() == 128 + 128 * (self.frontS - self.anchrS), \
               "log file length mismatch"

    def __getitem__(self, seq):
        if seq > self.frontS:
            raise IndexError
        pos = 128 * (seq - self.anchrS)
        self.f.seek(pos)
        buf = self.f.read(128)[8:]
        if not buf or len(buf) == 0: return None
        mid = self.anchrM if seq == self.anchrS + 1 else bytes(20)
        return packet.from_bytes(buf, self.fid, seq, mid, None)

    def __len__(self):
        return self.frontS

    def __del__(self):
        self.f.close()

    def _append(self, pkt):
        assert pkt.seq == self.frontS + 1, "new log entry not in sequence"
        # append to file:
        self.f.seek(0,2)
        self.f.write(bytes(8) + pkt.wire)
        # update file header:
        self.frontS += 1
        self.frontM = pkt.mid
        self.f.seek(12+92) # position of front fields
        self.f.write(self.frontS.to_bytes(4, 'big') + self.frontM)
        self.f.flush()
        # os.fsync(self.f.fileno())
        return pkt

    def append(self, buf120):
        pkt = packet.from_bytes(buf120, self.fid, self.frontS+1, self.frontM,
                                self.vfct)
        if pkt == None: return None
        return self._append(pkt)

    def write_48B(self, buf48, signfct):
        assert len(buf48) == 48
        e = packet.PACKET(self.fid, self.frontS+1, self.frontM)
        e.mk_plain_entry(buf48, signfct)
        return self.append(e.wire)

    def prepare_chain(self, buf, signfct): # returns list of packets, or None
        e = packet.PACKET(self.fid, self.frontS+1, self.frontM)
        blobs = e.mk_chain(buf, signfct)
        return e, blobs

    def getfront(self):
        return (self.frontS, self.frontM)

# ----------------------------------------------------------------------
    
'''
A) Internal structure of an append-only log file:

  How 'anchor' and 'front' metadata relate to an append-only log:

                  v-- first log entry in file (seq=N)
   -  -  -  -  +-----------+-----------+-----------+-----------+
   log         |R+D+T+P+SIG|R+D+T+P+SIG|R+D+T+P+SIG|R+D+T+P+SIG| --> future
   -  -  -  -  +-----------+-----------+-----------+-----------+
          ^                   last log entry in file --^   ^
          |                                                |
          | anchorSEQ (N-1)                       frontSEQ |
          | anchorMID                             frontMID |


  The log file is a sequence of 128 byte blocks, the first is a header block

    128B header block
    128B log entry N
    128B log entry N+1
         ..


  The header block persists critical metadata for the log:
  - reserved   (12B)
  - feed ID    (32B, ed25519 public key)
  - parent ID  (32B, if this log is a subfeed)
  - parent SEQ ( 4B, seqNr where the parent feed declared this subfeed)
  - anchor SEQ ( 4B, seqNr, assumed to be trusted, can be >0 for truncated feed
  - anchor MID (20B, msgID, assumed to be trusted, of above anchorSEQ entry
  - front SEQ  ( 4B, seq number of last record in the file)
  - front MID  (20B, msgID of last record in the file)

 
  Log entries, following the header block, occupy also 128 bytes:
  - reserved   (  8B, could be RND or other mgmt information)
  - packet     (120B, DMX+T+PAYLOAD+SIGNATURE)
  Once a log entry is in the file, it is declared trusted
  (because we verify each packet before appending it)


B) Blobs:

  - any         (128B)
  - stored in a separate directory


C) Sidenote, unrelated to this repository code:

   One can use a log entry with a sidechain to tunnel packets of
   other feeds i.e., wrapping a feed inside another feed, or to
   tunnel a mix (of log entries from several feeds) inside a single feed.

   Given a (inner) packet X of length 128B (data), create two (outer) packets:

   i) log entry   D+T+P+SIG, where T is chain20
                                   P is 28B (data from X) + 20B (hptr)

   ii) blob       100B (data from X) + 20B (null-ptr)


'''

# eof

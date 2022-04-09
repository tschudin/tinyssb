# tinyssb/packet.py  -- creating, signing and verifying packets

import hashlib
import pure25519

PKTTYPE_plain48    = 0x00     # ed25519 signature, single packet with 48B
PKTTYPE_chain20    = 0x01     # ed25519 signature, start of hash sidechain
PKTTYPE_ischild    = 0x02     # metafeed information, only in genesis block
PKTTYPE_iscontn    = 0x03     # metafeed information, only in genesis block
PKTTYPE_mkchild    = 0x04     # metafeed information
PKTTYPE_contdas    = 0x05     # metafeed information

# see end of this document for the payload content of types 0x02-0x05

VERSION = b'tinyssb-v0'

def _dmx(nm):
    return hashlib.sha256(VERSION + nm).digest()[:7]

class PACKET:

    def __init__(self, fid, seq, prev):
        self.fid, self.seq, self.prev = fid, seq, prev
        self.nam = self.fid + self.seq.to_bytes(4,'big') + self.prev
        self.dmx = _dmx(self.nam)
        self.typ = None
        self.payload = None
        self.signature = None
        self.wire = None
        self.mid = None
        self.chain_len = -1
        self.chain_content = b''
        self.chain_firstptr = None # hashptr of first blob
        self.chain_nextptr = None # hashptr of next (pending) blob

    def _mid(self):
        return hashlib.sha256(self.nam + self.wire).digest()[:20]

    def _sign(self, typ, payload, signFct):
        assert len(payload) == 48
        self.typ = bytes([typ])
        self.payload = payload
        msg = self.dmx + self.typ + self.payload
        self.signature = signFct(self.nam + msg)
        self.wire = msg + self.signature
        self.mid = self._mid()
        
    def predict_next_dmx(self):
        next_name = self.fid + (self.seq+1).to_bytes(4,'big') + self.mid
        return _dmx(next_name)

    def has_sidechain(self):
        return self.typ[0] == PKTTYPE_chain20

    def content_is_complete(self):
        if self.typ[0] == PKTTYPE_plain48: return True
        if self.typ[0] == PKTTYPE_chain20:
            if self.chain_len == len(self.chain_content): return True
        return False
    
    def get_content(self):
        if self.typ[0] == PKTTYPE_plain48:
            return self.payload
        if self.typ[0] == PKTTYPE_chain20:
            return self.chain_content

    def mk_plain_entry(self, payload, signFct):
        if len(payload) < 48:
            payload += b'\x00'*(48-len(payload))
        self._sign(PKTTYPE_plain48, payload[:48], signFct)

    def mk_typed_entry(self, typ, payload, signFct):
        if len(payload) < 48:
            payload += b'\x00'*(48-len(payload))
        self._sign(typ, payload[:48], signFct)

    def mk_chain(self, content, signFct):
        # fills in and signs this object, returns reversed list of blobs
        # FIXME: use hardisk instead of memory?
        sz = btc_var_int(len(content))
        buf = sz + content
        ptr = bytes(20)
        blobs = []
        if len(buf) <= 28:
            payload = buf + bytes(28-len(buf)) + ptr 
        else:
            head, tail = buf[:28], buf[28:]
            i = len(tail) % 100
            if i > 0:
                tail += bytes(100-i)
            cnt = len(tail)//100
            while len(tail) > 0:
                buf = tail[-100:] + ptr
                blobs.append(buf)
                ptr = blob2hashptr(buf)
                tail = tail[:-100]
            payload = head + ptr 
        self._sign(PKTTYPE_chain20, payload, signFct)
        blobs.reverse()
        return blobs

    def undo_chain(self, getBlobFct):
        if self.chain_len < 0:
            self.chain_len, sz = btc_var_int_decode(self.payload)
            self.chain_content = self.payload[sz:min(28,sz+self.chain_len)]
            if self.chain_len == len(self.chain_content):
                self.chain_firstptr = None
            else:
                self.chain_firstptr = self.payload[-20:]
            if self.chain_firstptr == bytes(20):
                self.chain_firstptr = None
            self.chain_nextptr = self.chain_firstptr
        # print("undo_chain", self.chain_len, len(self.chain_content), self.chain_nextptr.hex())
        while getBlobFct and self.chain_len > len(self.chain_content) \
                         and self.chain_nextptr:
            blob = getBlobFct(self.chain_nextptr)
            if blob == None:
                # print("no blob :-(")
                return False
            self.chain_nextptr = blob[100:]
            if self.chain_nextptr == bytes(20): self.chain_nextptr = None
            blob = blob[:min(100,self.chain_len - len(self.chain_content))]
            # print("blob!", len(blob), blob)
            self.chain_content += blob
            # print("lengths", self.chain_len, len(self.chain_content))
        return self.chain_len == len(self.chain_content) # all content found

# ----------------------------------------------------------------------

def blob2hashptr(blob):
    return hashlib.sha256(blob).digest()[:20]

def from_bytes(buf120, fid, seq, prev, verify_signature_fct):
    # converts bytes to a packet object, if it verifies or if flag is False
    pkt = PACKET(fid, seq, prev)
    if verify_signature_fct: # expected DMX value
        if pkt.dmx != buf120[:7]:
            print("DMX verify failed, not a valid log extension")
            return None
    else:
        pkt.dmx = buf120[:7]
    pkt.typ = buf120[7:8]
    pkt.payload = buf120[8:56]
    pkt.signature = buf120[56:]
    if verify_signature_fct: # signature
        if not verify_signature_fct(fid, pkt.signature, pkt.nam + buf120[:56]):
            print("signature verify failed")
            return None
    pkt.wire = buf120
    pkt.mid = pkt._mid() #  only valid if incoming `prev was correct
    return pkt

def btc_var_int(i):
    assert i >= 0
    if i <= 252:        return bytes((i,))
    if i <= 0xffff:     return b'\xfd' + i.to_bytes(2, 'little')
    if i <= 0xffffffff: return b'\xfe' + i.to_bytes(4, 'little')
    return                     b'\xff' + i.to_bytes(8, 'little')

def btc_var_int_decode(buf):
    assert len(buf) >= 1
    h = buf[0]
    if h <= 252: return (h,1)
    assert len(buf) >= 3
    if h == 0xfd: return (int.from_bytes(buf[1:3], 'little'),3)
    assert len(buf) >= 5
    if h == 0xfe: return (int.from_bytes(buf[1:5], 'little'),5)
    assert len(buf) >= 9
    return (int.from_bytes(buf[1:9], 'little'), 9)

# ----------------------------------------------------------------------

'''
tinySSB Data Format of 48B Log Entries for "Metafeed Information"
-----------------------------------------------------------------

1) A tree hierarchy for dependend feeds

We specify for tinySSB a way to express tree-shaped feed dependencies:
a feed can have one or more children feeds and can end with an
optional continuation feed. The parent-child relationship naturally
forms a tree, extending it vertically. Horizontally, a continuation
feed extends a node such that the tree shape is kept intact.  The
following figure shows these two extension possibilities (we attach
classification-style names to nodes just for readability purposes):

                 root-feed (.)
               /      |          \
 sub-feed (.1)   sub-feed (.2)     ....
       |            ...    \
 subsub-feed (.1.1)     subsub-feed (.2.5) -> subsub-feed (.2.5') -> ...
                               |                    /    \
                           .2.5.1          .2.5'.1      .2.5'.2

We requires that a child node, as well as a continuation node, specify
their predecessor node which is found either horizontally (if a
continuation), or vertically (if a child node). The root node has no
predecessor, i.e. the respective predecessor feed ID is set to 0.

As a result, it is always possible to find the root node of the tree
when starting from am arbitrary feed X like this:

find_root(x):
  while x.predecessor != 0:
    x = x.predecessor
  return x

This is useful, for example, if trust claims are linked to the root node
and these trust claims should also apply to all dependend nodes.

The predecessor relationship is cryptographically protected such that
no loops can form: each dependend feed must provide a
"birth-certificate" as a proof of its status, in its genesis
block. This certificate is simply a hash value of the log entry's wire
format that announces the new dependend feed. The steps to create a
dependend feed are one of:

mk_child_feed(n):
  s = alloc_keypair()
  logentry = n.append(PKTTYPE_mkchild, s.pk, signed_with=n.sk)
  s.create_feed(PKTTYPE_ischild, pred=(logentry.fid/.seq),
                proof=hash(logentry), signed_with=s.sk)
  return s

mk_continuation_feed(n):
  s = alloc_keypair()
  finallogentry = n.append(PKTTYPE_contdas, s.pk, signed_with=n.sk)
  s.create_feed(PKTTYPE_iscontn, pred=(finallogentry.fid/.seq),
                proof=hash(finallogentry), signed_with=s.sk)
  return s

To end a feed, a continuation entry is created for a dependend feed=0:

mk_end_of_feed(n):
  finallogentry = n.append(PKTTYPE_contdas, 0, signed_with=n.sk)


2) Encoding

The format of the 48B payload containing metafeed information,
depending on the value in the packet's type field, is specified as
follows:

PKTTYPE_ischild: (always has sequence number 1)
  32B predecessor fid   # vertical (parent)
   4B predecessor seq
  12B hash(fid[seq])

PKTTYPE_iscontn: (always has sequence number 1)
  32B predecessor fid   # horizontal
   4B prececessor seq
  12B hash(fid[seq])

PKTTYPE_mkchild: (at arbitray position in the parent log)
  32B child fid
  16B any (timestamp, etc)

PKTTYPE_contdas:  (at the last position of the predecessor log)
  32B continuation fid
  16B any (timestamp, etc)


3) Discussion

(see also and compare with SSB's metafeed spec at
https://github.com/ssb-ngi-pointer/ssb-meta-feeds-spec)

The four packet types above form a minimal layer for expressing
dependency in a way that enforces a tree shape. One can design a
second layer of dependency, but without such guarantee, at
application layer that uses ordinary plain48 or chain20 messages. In
such 2nd layer dependency messages, things could be expressed like:

- mount      (called "metafeed/add/existing" in the SSB metafeed spec)
- unmount    (called "metafeed/tombstone" in the SSB metafeed spec)
- mounted    (called "metafeed/announce" in the SSB metafeed spec)

The verb mount is inherited from the UNIX vocabulary as it relates to
extending tree-shaped file systems. One could also have used the UNIX
concept of symbolic links (symlink(), unlink(), S_ISLINK()) for this
discussion with the characteristics that such higher-level tree
constructions can't prevent loop formation (which we do not want for
our low-level tree of feeds). Note that the SSB spec does not discuss
the problematic case where one metafeed would "add/existing" another
metafeed.

SSB's "metafeed/add/derived" action is, tree-wise, already covered by
our low-level mkchild action where the parent feed includes the child
feed's ID. At the same time, the genesis block of the child feed links
back to the respective PKTTYPE_mkchild log entry and proves this
reference by including a hash of it. This replaces both the two-fold
signing (necessary for "add/existing" in SSB's metafeed spec) and the
deterministic seed generation of a child's (which can be seen as
another proof of belonging to some parent feed).

There remains the question whether the child's (or continuation's)
keypair MUST be derived from the predecessor feed, instead of being
created from a random seed.  We chose to use a random seed in order to
be able to drop a dependend feed's secret key for forward secrecy
reasons. With the same intent we also prefer to not specify a special
private message to oneself for storing the secret key of (any)
dependend or top-level feed inside a feed, while the SSB spec uses a
"metafeed/seed" log entry in the main feed. If applications choose to
nevertheless have this feature (e.g. to use a log as a backup for
private keys), they can still implement it by themselves.


'''

# eof

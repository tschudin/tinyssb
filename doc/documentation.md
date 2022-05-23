# Low-Level Secure Scuttlebutt Packet Spec

_draft 2022-05-02_
Missing:

- Packet types 6
- End of file

## Abstract

In classic Secure Scuttlebutt, a log entry is self-describing in the sense that
it contains all relevant fields in order to verify the entry's signature.
Together with some "trust anchor state", a consumer can assert the integrity,
authenticity and trustworthiness of a log entry, if the previous log entry was
already trusted. Based on the observation that trustworthiness of a new entry
anyway depends on the trustworthiness of past entries as well as other external
state, TinySSB only includes in the wire format the bits that _cannot_ be
procured from such context. Doing so greatly reduces the number of bits that
need to be sent.

Tinyssb aims to provide an SSB-like protocol adapted for very limited devices by
sending and storing the least amount of data possible. In addition to the
reduction of the required number of bits exchanged, we introduce support for
multiple feeds organised in a tree structure that allows for an easy management
of the data as well as an interface to mutually forget data that is not needed
anymore.

## Introduction

In contrast with classical SSB, tinyssb makes use of the data stored for
previous entries to minimise the data sent. For example, we do not send the feed
identification (ed25519 public key), the entry's sequence number and the hash
value of the previous log entry. Indeed, those can be deduced from the received
data: the feedID is implicit through the signature: a consumer can validate the
signature by trying out all trusted public keys (because a key that is not part
of the trust anchor cannot lead to trustworthiness by definition). Similarly,
the sequence number is very much predictable: either it is immediately following
the highest trusted number we know about, or the potential entry has to be
dropped anyway.

_Not_ sending a field does not mean that it has no relevance. When computing the
signature, for example, these fields must be part of the "virtual log entry"
that is signed together with the bits of the packet, but these fields are not
manifested on the wire. To achieve this, a peer keeps a list of all expected
entries (precisely a hash value of the relevant fields). Thus, a data producer
can prepare a packet, compute the relevant fields and send the minimum required
data on the wire.

As an example, we describe here the virtual field of a log entry, as well as the
fields that appear "on the wire".

```
                     context state (exists at producer  |    a) trust anchors
                             as well as consumer side)  |    b) per feed 'head':
                                                        |      - prefix (version)
                                                        |      - feedId
                                                        |      - latestSeqNo
                                                        |      - latestMsgID
                                                         `---------|-----------
                                                                   |
virtual part of log entry              +-----log entry-----+       |
(used to compute the signature         .    prefix         . <-----'
 and demux field)                      .    feedID         .
                                       .    seqNo          .
                                   <---.--- prevMsgID      .
. . . . . . . . . . . . . . . . . . . .+ . . . . . . . . . +
                                       |    demux          |
manifested part of log entry           |    algo + type    |
(bits 'on the wire' as well            |    payload        |
 as replicated on disk)                |    signature      |
                                       +-------------------+


               Figure 1: virtual vs manifested parts of a log entry
```

This process not only spare some bandwidth by sending fewer bytes, but also
allows us to spare storage as only the bytes sent need to be stored.

## Packet Layout

A packet must be 120 bytes long, excluding link- or connexion-specific addition
dependent on the protocol (e.g. cloaking, encryption). Packets are either
_blob_ or _log entries_

- blob entries have:
    - a 1 to 100B payload
    - a 99 to 0B padding
    - a 20B hash pointer of the next blob entry in the chain

- log entries have:
    - a 7B demultiplexing field (DMX), a hash value of the virtual fields
    - a 1B algorithm and type field
    - a 48B payload
    - a 64B signature

```

<------------------- 120B ------------------->

                    120B ("wire bytes")
      +-------------------..-----------------+
      | cloaked packet content               | frame
      +-------------------..-----------------+

      where uncloaked PACKET content is one of:
Blob:
      +--------------------------------------+
      | blob                                 |
      +--------------------------------------+
          100B                          20B
      +---------------. . .----------+-------+
      | payload          | padding   | HPTR  | (padding can be 0B)
      +---------------. . .----------+-------+

Log:    
         7B           113B
      +-----+--------..----------------------+
      | DMX | demux content                  |
      +-----+--------..----------------------+

             where demux content is one of:

              1B     48B            64B
            +---+----..---+--------..--------+
            | 0 | payload | crypto-signature | 48B payload
            +---+----..---+--------..--------+

            +---+----..---+--------..--------+
            | 1 | L|C|PTR | crypto-signature | start of blob chain
            +---+----..---+--------..--------+
                  L= overall content length
                  C= first part of content
                  PTR = 20B hash of first blob in the chain

             ...

            +---+----..----------------------+
            | x | frontier/repl mgmt cmd/etc | and other packet types ...
            +---+----..----------------------+
```

### Log Entry Packet Format

A log entry has a virtual format containing not only the data itself but also
all the fields needed to verify the authenticity and integrity of the packet.
Those fields are:

```
- PFX  = 10B   'tinyssb-v0', prefix for versioning packet formats
- FID  = 32B   ed25519 public key (feed ID)
- SEQ  =  4B   log sequence number in big endian format
- PREV = 20B   message ID (MID) of preceding log entry
- DMX  =  7B   demultiplexing, the hash value of the fields above (that are not
               sent "on the wire")
- TYP  =  1B   packet type 
- PAYL = 48B   payload
- SIG  = 64B   signature
- MID  = 20B   messageID (hash value), used in "PREV" for the next message
```

Note that the length of the field `PFX` is not restricted, as only its hash
value is used (see below).

For notation purpose, we introduce the following fields:

```
LOG_ENTRY_NAME     = PFX + FID + SEQ + PREV
   (to compute DMX)


EXPANDED_LOG_ENTRY = LOG_ENTRY_NAME         + DMX + TYP + PAYL
                   = PFX + FID + SEQ + PREV + DMX + TYP + PAYL
   (to compute SIG)


FULL_LOG_ENTRY     = EXPANDED_LOG_ENTRY                        + SIG
                   = LOG_ENTRY_NAME         + DMX + TYP + PAYL + SIG
                   = PFX + FID + SEQ + PREV + DMX + TYP + PAYL + SIG
   (to compute MID)
``` 

#### Computing the hashes and signatures

The demultiplexing field is a (truncated) hash computed from the fields that are
not sent on the wire:

```
DMX = sha256(PFX + FID + SEQ + PREV)[:7]
```

The signature is the certificate of the authenticity and integrity of the
message:

```
SIG = ed25519_signature(secretkey, EXPANDED_LOG_ENTRY)
```

The MessageID (MID) is used by the following message (in PREV) to build a linked
list

```
MID = sha256(EXPANDED_LOG_ENTRY + SIG)[:20]
```

#### Log Entry Wire Format

We can now define the packet as sent on the wire:

```
PACKET = DMX + TYP + PAYL + SIG
       =  7B +  1B +  48B + 64B = 120B
```

### Blob Entry Packet Format

The second packet format contains only three fields

```
- CONTENT  =   1B - 100B
- PADDING  =  99B -   0B
- HPTR     =  20B
```

The content can have any size between 1 and 100 bytes, unlike the `PAYLOAD`
field in the log format, that has to contain exactly 48 bytes.

`HPTR` is a hash pointing to the **next** blob message, which implies that blobs
need to be computed bottom up (the last packet sent is prepared first):

```
HPTR = sha256(BLOB)[:20]
```

We will describe its use in more detail in the section about log packets of type
1

## Log Packet Types

A log entry has a 48 Bytes payload, which content must comply to the
specification of its type (given by the field `TYP`). We will describe the 7
types that are described as of this version of TinySSB.

### Type 0: Plain Text

Packet type 0 (`0x00`) is a plaintext without specific field. It can contain up
to 48B of content.

### Type 1: Chain

If more than the fixed-size 48B payload should be added to the log
(type 0), a chain can be used. As each packet must contain 120B, we split the
content and spread it into a chain of packets that can be sent sequentially. The
first of those packets will be a log packet of type 1 (`0x01`), containing all
the metadata for the content, while the rest of the data is spread among blob
packets. The content is divided in batches of 100B each, the last 20B being a
pointer (the hash value) to the next blob. The last blob is padded if needed,
and its `HPTR` field (the last 20B) are all zeros, signaling the end of the
chain.

The payload field of the log packet is split in 3 fields:

```
- LEN      :      n Bytes   the total length of content
- content1 : (28-n) Bytes   the first part of the content 
- HPTR1    :     20 Bytes   hash pointer
```

When forming the chain, the last blob has to be created first, from which the
last pointer value can be derived which goes into the second-last blob etc. The
total content length (field `LEN`) is encoded in
[Bitcoin's varInt format](https://en.bitcoin.it/wiki/Protocol_documentation#Variable_length_integer)
and its length must be considered when filling the last packet.

```

  <--------------120B packet content---------->
  
          <----- 48B payload ---->
          <----  28B ----> <-20B->
  +----+-+----------------+-------+- . . . ---+
  | DMX|T| LEN | content1 | HPTR1 | signature |   log entry
  +----+-+----------------+-------+- . . . ---+
                              |
     -------------------------' start of side chain (hash of blob 1)
    /
   v     100B                            20B
  +----------. . . . . . . . . .------+-------+
  | content2                          | HPTR2 |   blob 1, identfied by HPTR1
  +----------. . . . . . . . . .------+-------+
                                         |
                        - - -------------' continuation of side chain
     -------------- - - -
    /
   v     100B                            20B
  +----------. . . . . . . . . .------+-------+
  | contentN         |  padding       | 0---0 |  last blob N-1
  +----------. . . . . . . . . .------+-------+


               Figure 2: Side chain to have log entries
                         with content of arbitrary length
```

Note that type-0 log entries have a fixed-length 48B payload while type-1 log
entries can have any length, even from 0 to 48 bytes. When the length is less
than 28, the ```HPTR1``` field consists of zeros as no blobs are necessary.

## Tree structure for the feeds

The five following packet types concern the creation and management of
sub-feeds. We describe their nuts and bolts before specifying their different
fields.

### Rationale of sub-feeds

We specify for tinySSB a way to express tree-shaped feed dependencies: a feed
can have one or more children feeds and can end with an optional continuation
feed. The parent-child relationship naturally forms a tree, extending it
vertically. Horizontally, a continuation feed extends a node such that the tree
shape is kept intact.

```
                root-feed (.)
              /              \
             /                \
 subsub-feed (.1.1)     subsub-feed (.2.5) -> subsub-feed (.2.5') -> ...
                               |                    /    \
                           .2.5.1          .2.5'.1      .2.5'.2
```

We require that a child node, as well as a continuation node, specify their
predecessor node which is found either horizontally (if a continuation), or
vertically (if a child node). The root node has no predecessor, i.e. the
respective predecessor feed ID is set to 0.

As a result, it is always possible to find the root node of the tree when
starting from an arbitrary feed X like this:

```python
def find_root(x):
    while x.predecessor != 0:
        x = x.predecessor
    return x
```

This is useful, for example, if trust claims are linked to the root node and
these trust claims should also apply to all dependent nodes.

The predecessor relationship is cryptographically protected such that no loops
can form: each dependent feed must provide a "birth-certificate" as a proof of
its status, in its genesis block. This certificate is simply a hash value of the
log entry's wire format that announces the new dependent feed.

### Create a sub-feed

One can declare a new feed by using an entry with type 4 for a child (vertical)
feed or type 5 for a continued (horizontal) feed. The same format is used (only
the field `TYP` is different):

```
- NFID   :  32 Bytes   ID of the new feed (child or continuation)
- ____   :  16 Bytes   Not defined (any: timestamp, etc)
```

This can happen at any time in a feed, but the entry must be the last one in
case of a continued feed.

The new feed can now be created, which first entry must be of type 2 (for a
child feed) or 3. Again, only the `TYP` field can distinguish them.

```
- PFID   :  32 Bytes   ID of the predecessor feed
- PSEQ   :   4 Bytes   sequence number of the last log of predecessor feed  
- HASH   :  12 Bytes   hash(PFID[PSEQ])
```

Note that the fields PFID and PSEQ refer to the feed entry of the
parent/predecessor feed, thus do not match the FID and SEQ fields.

TODO: type 6, explain hash better?

### Type 6: Acknowledgement

```
- OLDFID  :  32 Bytes   id of the feed whose action is acknowledged  
- PADD    :  16 Bytes   padding
```

## Filtering Received Packets via "Expectation Tables"

A node (local peer) has precise knowledge about what packets are acceptable,
given its current state. The DMX field was introduced for letting packets
declare their profile and letting nodes filter on these announcements
(before performing the computationally expensive verification of the signature).
A second, independent filter is based on a requested packet's hash value. A node
therefore maintains two "expectation tables", one for logs (DEMUX_TBL) and one
for blobs (CHAIN_TBL).

The DEMUX_TBL table is populated by ```(DMX, feedID)``` tuples for each feed
that a node subscribed for: the node can exactly predict which`PFX`,`FID`,
`SEQ` and `PREV` a packet must have in order to be a valid extension of the
local log replica. As soon as a valid entry was received, the old DMX value can
be removed from the DEMUX_TBL and is replaced by the next one, based on the
updated feed. Note that a publisher can stream log entries back-to-back while
the consumer simply rotates the corresponding `DMX` entry.

Similarly, if a log entry contains a sidechain and the subscription asked for
replication **with** its sidechains, the node can add an expected hash pointer
value to the CHAIN_TBL table (which is the first hash pointer of this chain,
found in the payload of the received log entry). When the first blob is
received, the node can replace this expectation with the next hash pointer found
in the received blob, etc

## Request a log or blob entry

```python
# TODO
```

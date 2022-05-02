# Thoughts and Questions

@author Etienne Mettaz

## Abstract

While preparing a final version of TinySSB, I write here the questions popping
into my mind to find answers later (or ask for them)
Warnings are implementation remarks to discuss, problems are tasks for myself
while the last section is on past or current misunderstandings from my side that
I want to keep track of.

## Questions

1. Should we describe a packet as having 120 or 128 bytes?
2. The "acknowledge" packet is not properly and consistently used I think, what
   might cause problems:
    1. in `session.py`, `SlidingWindow::_process()`, we create the ack packet,
       whose content is only the id of the feed whose action is acknowledged and
       some zero bytes (for padding). Couldn't that lead to misunderstanding by
       acknowledging the wrong packet (for example if the remote makes several
       children in a row and one make_child packet is lost)? Maybe that's our "
       concurrency problem"...
    2. Also, the condition for the if-loop is not exactly the same:

       ```if pkt.typ == bytes([packet.PKTTYPE_contdas]):```

       vs

       ```if pkt.typ[0] == packet.PKTTYPE_iscontn:```
    3. What happens if a `mk_child` is lost? There are currently no
       acknowledgment for that.
3. The request packets ('blobs' and 'want') are not part of the feed by itself.
   Should they nevertheless be described in the documentation?
4. The `log_burning_demo.py` does a lot of non-trivial work, and people using
   the library will need to do it as well. What interface do we want to give to
   the users?
5. I don't think `Keystore::dump()` and `Keystore::load()` are ever called. It
   makes the code non-reentrant, as we don't keep track of the sub-feeds key
   pairs
6. Repo::mk_child_log() specification says that last 12 bytes of
   'PKTTYPE_ischild'(and of 'PKTTYPE_iscontn') = hash(fid[seq]) (fid and seq
   from referenced packet from other feed), but here we use the last 12B of the
   (64B) signature.
7. There's nothing in the documentation on the format of the packets as stored
   in the disk (as specified in REPO::allocate_log() and LOG::). Should I add
   it?

## Former Problems (not relevant anymore):

1. [SOLVED] Prefix:
    1. In code, `nam` does not contain prefix (`VERSION`),
       unlike `LOG_ENTRY_NAME` in packet-spec.md
    2. It is added to compute dmx, but **not for signature**
    3. `VERSION = b'tinyssb-v0'` => prefix.size != 8 bytes
2. poc-04: amount of files in data/'user'/_logs always grows
3. [SOLVED] LOG.write_typed_48B() (in repository.py) has same sig as
   NODE.write_typed_48B()
   I find it a bit confusing PS: session also contains
   SlidingWindow.write_typed_48B()
1. [SOLVED] Can we end a feed by declaring it as continued (packet type 5) with
   continuation feedID set to 0?
   Yes: repo::write_eof()

1. [SOLVED] Packet fields in packet-spec.md do not always correspond to the
   names in code
2. [SOLVED] True or false: a continued feed is always closed
3. Sometime, the number of logs increases linearly. Problem with deleting? Or
   verifying DMX/SIG?

## Questions / remarks for myself

1. [SOLVED] About poc-03: The only diff between PKTTYPE_ischild and
   PKTTYPE_iscontn is
   that feedID refers to a parent or not (horizontal). How do we tell them
   apart? With Type field
   (same for mkchild and contdas)
2. [SOLVED] Why multiple feeds and subfeed? having a sliding window on just the
   main feed
   lets us do everything we want, no?
    1. multiple feeds let a user have different activities and other peers
       replicate just a subset of them
    2. Continuation feeds simplifies greatly the management of the sliding
       window
       (starts always at the start of the current feed and ends at the actual
       point, discarded are always entire feeds)
3. [SOLVED] `neigh` is not defined in IOLOOP.run(), but used later. I'm not sure
   what it
   is and I wonder if I didn't miss something.
4. [SOLVED] fix REPO.verify
5. [SOLVED] compare with poc-04 (and 3?)
6. [SOLVED] Diff between log, blob, plain (incl. type)
7. [SOLVED] Is a "log" a packet from format "DMX+TYP+PAYL+SIG" or a packet with
   TYP=1? Is
   the first packet of a blob chain considered to be a Log or Blob entry?

## Documentation

Things not to forget in final documentation

1. packet type (see end of packet.py)
2. list of packet fields (see beginning of packet.py)
3. Add packet fields description for blob packets
4. comments at the end of repository (poc-01)
5. Check PREV of 1. packet

General packet layout:

1. add other entry types
2. list of "algorithm and type fields"

___

1. Short description, rationale and link to SSB % packet length, with
   description of rationale and SSB-history
2. Packet types and tree structure
3. Relevant fields
4. Logs entries
5. Blob entries
6. special entries

# Thoughts and Questions

@author Etienne Mettaz

## Abstract

While preparing a final version of TinySSB, I write here the questions popping
into my mind to find answers later (or ask for them)
Warnings are implementation remarks to discuss, problems are tasks for myself
while the last section is on past or current misunderstandings from my side that
I want to keep track of.

## Warnings

1. Prefix:
    1. In code, `nam` does not contain prefix (`VERSION`),
       unlike `LOG_ENTRY_NAME` in packet-spec.md
    2. It is added to compute dmx, but **not for signature**
    3. `VERSION = b'tinyssb-v0'` => prefix.size != 8 bytes
2. poc-04: amount of files in data/'user'/_logs always grows
3. LOG.write_typed_48B() (in repository.py) has same sig as
   NODE.write_typed_48B()
   I find it a bit confusing PS: session also contains
   SlidingWindow.write_typed_48B()
4. It looks like dmx

## Problems :

1. Packet fields in packet-spec.md do not always correspond to the names in code
2. True or false: a continued feed is always closed
3. The request packets (blobs and want) don't contain all fields, and the DMX
   field is computed with missing fields. Is it ok?
4. Sometime, the number of logs increases linearly. Problem with deleting? Or
   verifying DMX/SIG?

## Questions / remarks for myself

1. About poc-03: The only diff between PKTTYPE_ischild and PKTTYPE_iscontn is
   that feedID refers to a parent or not (horizontal). How do we tell them
   apart?
   (same for mkchild and contdas)
2. Why multiple feeds and subfeed? having a sliding window on just the main feed
   lets us do everything we want, no?
    1. multiple feeds let a user have different activities and other peers
       replicate just a subset of them
    2. Continuation feeds simplifies greatly the management of the sliding
       window
       (starts always at the start of the current feed and ends at the actual
       point, discarded are always entire feeds)
3. `neigh` is not defined in IOLOOP.run(), but used later. I'm not sure what it
   is and I wonder if I didn't miss something.
4. fix REPO.verify
5. compare with poc-04 (and 3?)
6. Diff between log, blob, plain (incl. type)
7. Is a "log" a packet from format "DMX+TYP+PAYL+SIG" or a packet with TYP=1? Is
   the first packet of a blob chain considered to be a Log or Blob entry?
8. No subfeed can be deleted without creating a new one. In other words, #feeds
   = #mkchild action + 1

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

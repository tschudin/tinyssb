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
   1. In code, `nam` does not contain prefix (`VERSION`), unlike `LOG_ENTRY_NAME` in packet-spec.md
   2. It is added to compute dmx, but **not for signature**
   3. `VERSION = b'tinyssb-v0'` => prefix.size != 8 bytes
2. poc-04: amount of files in data/'user'/_logs always grows
3. LOG.write_typed_48B() (in repository.py) has same sig as NODE.write_typed_48B()
   I find it a bit confusing
   PS: session also contains SlidingWindow.write_typed_48B()

## Problems :

1. Packet fields in packet-spec.md do not always correspond to the names in code
3. True or false: a continued feed is always closed

## Questions / remarks for myself

1. About poc-03: The only diff between PKTTYPE_ischild and PKTTYPE_iscontn is
   that feedID refers to a parent or not (horizontal). How do we tell them apart?
   (same for mkchild and contdas)
2. Why multiple feeds and subfeed? having a sliding window on just the main feed
   lets us do everything we want, no?
   1. multiple feeds let a user have different activities and other peers replicate 
   just a subset of them
   2. Continuation feeds simplifies greatly the management of the sliding window
   (starts always at the start of the current feed and ends at the actual point,
   discarded are always entire feeds)
3. `neigh` is not defined in IOLOOP.run(), but used later. I'm not sure what it is
   and I wonder if I didn't miss something.
4. fix REPO.verify

## Documentation

Things not to forget in final documentation

1. packet type (see end of packet.py)
2. list of packet fields (see beginning of packet.py)

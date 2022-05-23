# Documentation for TinySSB's API

_draft 2022-05-23_
_Author: Etienne Mettaz_

## Abstract

We present here the main documentation for understanding and using TinySSB. For
a more technical documentation on the packets' content, see the
[low level documentation](low-level-doc.md).

## Introduction

TinySSB, like its source Secure Scuttlebutt (SSB), is based on append-only logs
that are cryptographically signed with pointers that enforce a linked-list
structure of the feed (each entry points to the previous one and contains a
sequence number). One drawback of this property is that one needs to synchronise
and check all log entries of a peer to exchange with him, even entries that do
not concern us. Therefore, TinySSB introduces the concept of child feeds: for
each use, one create a new sub-feed. A peer using several application
can thus have different feeds for each app. This creates a tree-like
datastructure formed of feeds.

To best manage your identity, TinySSB automatically creates several feeds. As in
classic Secure Scuttlebutt, a peer has a `root` feed, but this will scarcely be
used: most of its purpose is to keep track of other feeds. It has three
sub-feeds:

1. `alias`  : a 'contact list'
2. `app`    : a list of the apps used by the peer
3. `public` : a neutral feed (not linked to any app) to communicate with other
   peers.

Of the 4 feeds (including the `root`), only the `public` feed is meant to be
read by other peers; the other feeds contains private data for local use.

Each feed consists of a linked list of log entries that contains a payload and
metadata, including a `type` field. This field describes the purpose of the
entry, for example:

- `plain text` (freely usable payload)
- `blob` (start a blob chain to create data packet of more than the 48 bytes
  payload of `plain text`)
- `make child` (create a sub-feed)
- `continued as` (ends this feed that is continued by a new sub-feed)
- ...

For a complete list and a better description of the packet structure, see the
[specific documentation](low-level-doc.md).

### The `root` feed

The main (and to date only) purpose of the root feed is to keep a pointer to
other sub-feeds. Thus, it contains exclusively `make child` entries, whose
payload contains the public key of the sub-feed and a name for it: `alias`,
`public` or `app`. Note that if several entries points to child feeds with the
same name, only the last entry will be considered.

### The `alias` feed

The `alias` feed is a contact list stored as `public_key ~ name`. It contains
almost exclusively `plain text` entries following one of these patterns:

- `set`:
    - 32 bytes public key
    - 16 bytes (BIPF encoded) name (eventually padded)
- `delete`:
    - 16 bytes all zeros
    - 32 bytes public key

Note that the name is private (not known by the person it refers to or anybody
else), and bounded to 16 bytes (when encoded in BIPF format).

In a later implementation, we might add a field at the beginning to specify the
pattern (or create new packet types). We could also add a `change` type to
modify the name.
For optimisation purposes, we might add a mechanism to copy all valid (not
deleted) entries in a new feed when the number of `delete` entries reaches a
threshold (for example 25% of the number of log entries). This feed would be a
child feed of `root` and the old feed would be ignored.

### The `app` feed

The app feed is a feed that keeps track of all the applications that a peer
uses. Each application has a unique ID Apart from the first entry (`is_child`),
all entries are one of the
following:

- `make child` for which the 16 bytes `undefined` field contains a bipf encoded
  (local) name. The name has to be chosen uniquely by the user, because only the
  last entry of several using the same name will be considered [TODO: enforce in
  `create app` that app name is not already registered].
- `set`: the idea is the same as in the `alias` field, but the 32 bytes field is
  an appID instead of a feed public key:
    - 32 bytes appID
    - 16 bytes bipf encoded name

  Each `make child` MUST be followed by a `set`, but the reverse is not true:
  a `set` entry with an appID that was already assigned will rename that app
  (for the local user)
- `delete`: signal that an app is not used anymore
    - 32 bytes appID
    - 16 bytes unspecified

### The `public` feed

The purpose of the `public` feed is to start a connection with a peer to know
the required data to start using an app.

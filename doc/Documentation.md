# Documentation for TinySSB API

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

1. `aliases`  : a 'contact list'
2. `apps`    : a list of the apps used by the peer
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
payload contains the public key of the sub-feed and a name for it: `aliases`,
`public` or `apps`. Note that if several entries points to child feeds with the
same name, only the last entry will be considered.

### The `aliases` feed

The `aliases` feed is a contact list stored as `public_key ~ name`. It contains
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

### The `apps` feed

The app feed is a feed that keeps track of all the applications that a peer
uses. An application has 3 different fields that can be added, modified and
deleted by 3 different packets:
- `app_name`: a human readable, self-(locally) attributed name. It is used
  as the key in `identity.directory['apps]`, and is present in all packets
- `appID`   : a 32 bytes random id defined by the app developer. A user
  cannot have more than one app using the same appID unless the previous one
  have been deleted (see `delete` packet)
- `fid`     : a 32 bytes feed ID (public key) that points to the app data

Apart from the first entry (`is_child`), all entries are one of the following:

- `make child` : creates a new feed.
    - 32 bytes `fid`
    - 16 bytes `app_name` (bipf encoded)
- `set`: set the app_id for the previously defined `app_name`
    - 32 bytes `appID`
    - 16 bytes `app_name` (bipf encoded)
- `delete`: signal that an app is not used anymore
    - 32 bytes `appID`
    - 16 bytes `app_name` (bipf encoded)

When reading sequentially through the log gathering data for one app, the first
log entry must be a `make_child`, followed by a `set`. After that, the
following entries of a same type will change the `fid` (`make_child`) or the
`app_name` (`set`).
For security, `delete` takes both `app_name` and `appID`. The app will be
deleted only if both match. After that, all data about this app will be ignored.


### The `public` feed

The purpose of the `public` feed is to start a connection with a peer to know
the required data to start using an app.


### The app specific sub-feed

To create a new app, one write a `make_child` packet in the `apps` feed. This
feed (we will name it `chess` for the example) is filled with two types of
packets: `blob`, `set` and `delete`. When the payload is too long to fit in the
48 bytes of `set`'s payload, one use `blob` instead. This doesn't lead to a 
problem as there can be no confusion. For readability, we will use `set` in 
this documentation, but bear in mind that if the payload is more than 48 bytes,
the packet is a blob instead. 

To create a new game, we add a `set` packet that contains the following fields 
as a bipf encoded dictionary:
- `inst_id`            : integer instance identification number,
- `initiate_local_fid` : 32 bytes public key, the feed I'm writing to
- `initiate_remote_fid`: 32 bytes public key, the feed I'm reading from
- `with`               : 32 bytes public key, the friend's `public` key (as 
                         appear in `aliases`)
- `name`               : a string, can be freely chosen by the developer 
                         and/or the user

`name` is an application or user identifier for the game and is optional. 
`initiate` is used to make sure that we can keep trace of the whole game. 
Following updates will not override those values. As one might not know the 
`remote_fid` at initiation, it might be omitted in the first package and 
added later on.

To update a field, one can send a new `set` packet with the same fields as 
the original entry except:
- No `initiate_local_fid`. A new

`gameID` must match a previous (non deleted) entry and is the only 
compulsory field. As we want to keep track of the original `local_fid` and 
`remote_fid`, we cannot override it, therefore we introduce `current` fids. 
`with` and `name` would override the previous content.

Note that in the code, only the first letter (`g`, `l`, `cl`, `r`, `cr` and 
`w`) are used.

`delete` packets contains only the instance number

# Documentation for TinySSB API

_draft 2022-05-23_
_Author: Etienne Mettaz_

## Abstract

We present here the main documentation for understanding and using TinySSB. For
a more technical documentation on the packets' content and the tree 
structure for feeds, see the 
[packet specification documentation](low-level-concepts.md).

We start by a short introduction followed by an extensive description of the 
feeds created and used by the API, before listing and explaining the objects,
methods and functions made available by the API.

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

## Feeds description

To best manage your identity, TinySSB API automatically creates several feeds. 
As in classic Secure Scuttlebutt, a peer has a `root` feed, but this will 
scarcely be used: most of its purpose is to keep track of other feeds. It 
has three sub-feeds:

1. `aliases`  : a 'contact list'
2. `apps`     : a list of apps used by the peer
3. `public`   : a neutral feed (not linked to any app) to communicate with other
   peers.

Of the 4 feeds (including the `root`), only the `public` feed is meant to be
read by other peers; the other feeds contains private data for local use only.

Each feed consists of a linked list of log entries that contains a payload and
metadata, including a `type` field. This field describes the purpose of the
entry, for example:

- `plain text`   :  freely usable payload
- `blob`         :  start a blob chain to create data packet of more than
  the 48 bytes payload of `plain text`
- `make child`   :  create a sub-feed
- `continued as` :  ends this feed that is continued by a new sub-feed
- `set`          :  declare a new element for an abstract data type

For a complete list and a better description of the packet structure, see the
[specific documentation](low-level-concepts.md).

### The `root` feed

The main (and to date only) purpose of the root feed is to keep a pointer to
other sub-feeds. Thus, it contains exclusively `make child` entries, whose
payload contains the public key of the sub-feed and a name for it: `aliases`,
`public` or `apps`. Note that if several entries points to child feeds with the
same name, only the last entry will be considered.

### The `aliases` feed

The `aliases` feed is a contact list stored as `public_key ~ name`. It contains
almost exclusively entries following one of these patterns:

- `set`:
    - 32 bytes public key
    - 16 bytes (BIPF encoded) name (padded if necessary)
- `delete`:
    - 32 bytes public key
    - 16 bytes all zeros

Note that the name is private (not known by the person it refers to or anybody
else), and bounded to 16 bytes (after being encoded in BIPF format).

For optimisation purposes, we might add a mechanism to copy all valid (not
deleted) entries in a new feed when the number of `delete` entries reaches a
threshold (for example 25% of the number of log entries). This feed would be a
child feed of `root` and the old feed would be ignored.

### The `public` feed

The purpose of the `public` feed is to start a connection with a peer to know
the required data to start using an app. The content is not restrained by 
this specification. It also serves as the user's identity, i.e. this feed's 
public key is used as identifier (it is used as the SSB feed's public key is 
used as identity in classic SSB), not the root's public key.

### The `apps` feed

The app feed is a feed that keeps track of all the applications that a peer
uses. There is exactly one valid `apps` feed that points to one subfeed for 
each "installed app". Each application has 3 different fields that can be 
added, modified and deleted :

- `app_name`: a human readable, self- (locally-) attributed name. It is used
  as the key in `identity.directory['apps]`, and is present in all packets
  for this app.
- `appID`   : a 32 bytes random id defined by the app developer. A user
  cannot have more than one app using the same appID unless the previous one
  has been deleted (see `delete` packet).
- `fid`     : a 32 bytes feed ID (public key) that points to the app data

Apart from the first entry (`is_child`), all entries are one of the following:

- `make child` : creates a new sub-feed (new application).
    - 32 bytes `fid`
    - 16 bytes `app_name` (bipf encoded)
- `set`: set the app_id for the previously defined `app_name`
    - 32 bytes `appID`
    - 16 bytes `app_name` (bipf encoded)
- `delete`: signal that an app is not used anymore
    - 32 bytes `appID`
    - 16 bytes `app_name` (bipf encoded)

When reading sequentially through the log, gathering data for one app, the first
log entry must be a `make_child`, followed by a `set`. After that, the following
`set` entries with the same `appID` will change the `app_name`.
For checking purpose, `delete` takes both `app_name` and `appID`. The app will
be deleted only if both match. After that, all data about this app will be
ignored. This is all done by the method `Identity::define_app()`.

### The app specific sub-feed

This section describes the content of the feeds created by `make_child` packets
in the `apps feed`.

Each can have several `instances` (a game, a chat group, etc.). Each instance
consists of up to 5 fields (bipf encoded):

- `inst_id`            : integer, unique identifier of the instance,
- `initial_local_fid`  : 32B public key, the feed I'm writing to at the
  beginning
- `local_fid`          : 32B public key, the feed I'm currently writing to
  (different from `initial_local_fid` in case of a continuation feed)
- `peers`              : a list of remote peers containing:
    - `with`                  : the friend's `public` key (as appear in 
      `aliases`)
    - `initial_remote_fid`    : 32B public key, the feed used at the beginning
        of the instance
    - `remote_fid`            : 32B public key, the feed currently used
- `name`               : an optional string, application or user property for 
    the game. Can be freely chosen by the developer and/or the user

NB: the first version of TinySSB does not support a change of public id (see 
`public` feed). This means the `peers`[`with`] is used as identification. 
For following version, one might add support for it.

To create a new instance of an app, one writes a `make_child` packet in the
`apps` feed. The newly created feed starts with an `is_child` packet 
followed by `set` and `delete` packets. Note that when the payload is too 
long to fit in the 48 bytes of `set`'s payload, one uses `blob` instead. 
This doesn't lead to confusion as it is the only use of `blob` packets in this
feed. For readability, we will use `set` in this documentation.

To update a field, one writes a new `set` packet with the same `inst_id`. It
can update any field except for `initial_*_fid`. Indeed, these two fields 
are used to keep track of the whole game (having the initial feed, one can 
reconstruct the whole game by following the chain built by the continuation 
feeds). Following updates will not override those values: the field `local_fid`
(rsp. `remote_fid`) will be used to update those values in case of continuation
feeds (this is done automatically).

As one might not know the `initial_remote_fid` at initiation, it can be
omitted and added later on.

Note that in the code, only the first letters (`id`, `il`, `l`, `ir`, `r`, `w`
and `n`) are used.

`delete` packets contains only the instance number. We use bipf
encoding as the instance number's size is not fix.

Those tasks are done by the methods `Application::create_inst()` and 
`Application::add_remote()`

## Log manager

To follow the concept of separation of concerns, we added an object 
`log_manager`. It  acts as an interface between the high level `Identity` 
and `Application` and the low-level `Node`. All operation (for example 
creating or deleting a log, write a logentry) are sent from the API-level 
classes to the low-level classes through it. In addition, it manages a track 
of the logs available with there purpose (private, public, remote) and ensure
that all relevant data are stored to allow for a restart after a break that 
could occur at any time by updating a storage of the keys (encryption keys 
for the logs) and demultiplexer fields (a reference to the current and 
waiting operations) periodically with a loop.

For a more extensive description of the types of logs and the operations made
available by the Log Manager, please refere to the comment at the end of [the 
file](../src/poc-05/tinyssb/log_manager.py).

## API

All objects, methods and functions designed to be used through the API are 
in the `__init__.py`, `identity.py` and `application.py` files. We describe 
here the main functions and methods: please refer to the comments in those 
files for a complete description.

### Starting

When starting the program, one must obtain an `identity` object. To do so, 
one can either create a new one with `generate_id()` or launch an existing 
one with `load_identity()`. Both return an `identity` object.

### Identity

The `identity` object is the central piece of the implementation. It manages 
and give access to the application currently used as well as the contact list.

With `follow()` and `unfollow()`, one can add or delete contacts from the 
`aliases` feed.

The `identity` in itself is mainly managing objects and access to them, but 
the main exchange are done through the `application` object. To create a new 
one, use `define_app()`. Alternatively, one can load an existing app with 
`resume_app()`. `delete_app()` will not only terminate the app but also 
delete all data associated with it, including its sub-feeds.

The last method, `write_to_public()` let us write in the `public` feed to send
and receive the necessary information for starting an instance of an app. See in
the Notes for more details.

### Application

The object returned by `identity.define_app()` and `identity.resume_app()` is an
instance of `Application`, which lets us manage instances. 

`create_inst()` generates a new instance of the current application and returns
the instance id (note that this id is local. Remote peers on the same instance
do not necessarily use the same instance id). It does not take details about
remote peers that participate in this instance: this has to be added with
`add_remote()`. Several peers can be added to the same instance (allowing 
for multi-user application), but only one by call to the `add_remote()`.
One can also restart an existing instance with `resume_inst()`. 

There is no call to make before exiting an instance. One can either switch 
to a different instance or app or terminate the program. `terminate_inst()` puts
an end to the instance (it won't be possible to write to it anymore), but keeps
the files on the disk. It is still possible to connect to that instance to 
read remote feeds. On the other hand, `delete_inst` remove all data 
associated to the instance after a call to `terminate_inst()`.

`send()` transmit data to the remote(s). There is no defined content description 
as this is to be defined independently by the application (the software 
developer). If the content is a string, bipf encoding will be used. No 
padding is needed, and the data will be automatically sent either as plain text
or as blob, depending on the length.
`set_callback()` sets the function to be executed upon receipt of such a packet.

## Notes

This first version of TinySSB is mostly a proof of concept. Also, the management
of many feeds is not good: the deletion of old feeds is far from optimal, and
sometimes not even made available by an API call. The update of feeds that are
meant to be rewritten(for example `apps` and `aliases`) is not yet supported.
The use of the sliding window (to bound the number of log entries in a feed) is 
not supported optimally.

# Pseudocode for a chat app using TinySSB

_draft 2022-05-10_

## Abstract

To construct a good API, I write an elegant pseudocode for a chat app, and I'll
stick the actual API to it.

## Example : open existing

```python
import tinyssb as tiny

# List ids that I can load (only the names associated to it)
ids = tiny.list_identities()
i = input(f"Choose an identity to open (write its index): {ids} ")
identity = tiny.fetch_id(ids[i])
rd = identity.directory
ad = rd['apps']
chess_games = ad['chess']
ui = ...
identity.launch_app(chess_games, ui)  # enter the app

# print the different sessions (subfeeds) available
# Example: a chat, a chess game, ...
with_ = input(rd['alias'])

session = identity.open_session(with_)
session.register(upcall_function)
while True:
    msg = ui.input("> ")
    if msg == 'quit':
        identity.sync()
        break
    else:
        session.send(msg)
```

31.05:
```python
import tinyssb as tiny

# List ids that I can load (only the names associated to it)
ids = tiny.list_identities()
i = input(f"Choose an identity to open (write its index): {ids} ")
identity = tiny.fetch_id(ids[i])
dir = identity.directory
print(dir['apps'])  # Output: (['chess'], ['tetris'])
app = identity.launch_app('chess')
i = input(f"Choose a game instance: {app.instances}")  
# Output: { '0': { ... }, '1': { ... } ... }

app.start(i)
app.set_callback(lambda received: print(received))
while True:
    msg = ui.input("> ")
    if msg == 'quit':
        identity.sync()
        break
    else:
        session.send(msg)
```

## 'Directory'

The navigation data can be obtained by get_root_directory(), and we call it
`directory`. It is a python list of this form (`bin_key` is a byte array public
key):

```python
directory = {
    'apps': {
        'chess': { 'fid':'`bin_key`',
                   'appID': '`bin_key`'
        },
        'chat': { 'fid':'`bin_key`',
                  'appID': '`bin_key`'
        },
    },
    'alias': {
        'Chiara': '`bin_key`',
        'David_chat': '`bin_key`'
    }
}
```

From each element of `apps`, we can access the different running games or
sessions

## Discussion 11.05

3 sub-feeds: `alias`, `apps` and `public`:

- `public` :  my public identity (used for example when I want to start a chess
  game)
- `alias`  :  my 'contact list', a dictionary with `public` feed ids from other
  peers with a nickname (for me only)
- `apps`   :  a list of apps that I can run

Every time I add a new entry into `apps`, I create a feed that will hold a list
of the `'sessions'` (or 'games' for a chess app). It contains `create` and
`delete` packet (one `delete` for one `create`, that need to be enforced).
`create` packets contain:

- `instance`    : a game identifier
- `local_feed`  : a (newly created) feed id where I will write the data
- `remote_feed` : the remote feed id to replicate (later: will be a list to
  allow for multiplayer? )

For each app `n` there is a feed `n` that holds a list of activ 'games'. This
feed only accepts `create` and `delete` packets. This is implemented as a list
ADT with a short feed length, often making continuation sub-feeds that copies
the data we are still interested to (the exact form of this is not yet
specified).

```
               root 
             /   |   \
            /    |    \
     public    alias    app 
                      /  |  \
                     /   |   \
                chess  chat  app_name
```

### Alias sub-feed

The alias sub-feed keeps track of the public keys of other peers, as a contact
list (to be exact, it stores key-value pairs containing the public key of
the `public` sub-feed of other peers and a given name). Note that the name is
private (not known by the person it refers to or anybody else) and that its
length is bounded: its BIPF representation must not be longer than 16 bytes.
The idea is to store the entries in a single log entry. Except feed management
(`is_child`) entries, we have only `plain_48` entries that follow one of these
patterns:

- `Set`:
    - 32 bytes public key
    - 16 bytes (BIPF encoded) name (eventually padded)
- `Delete`:
    - 16 bytes all zeros
    - 32 bytes public key

Possible extensions:

- add a `Change` pattern to change the name (old name and new name). This would
  require to have unique names (which is not required for the sub-feed, but
  maybe it should be enforced anyway)
- add a special field of one byte to distinguish between the types (downside:
  name will have to be shorter)
    - eventually, add packet specification types
- I think we should not have feed continuation. When it contains too
  many `delete` (for example 25% of the packets are `delete` packets), create a
  new child feed from the root feed, copy all contacts that have not been
  deleted. The old feed will be ignored (see start.load_identity()) and can be
  deleted.

### Ideas and questions:

1. One of three options:
    - the local feed is a sub-feed of `root`
    - the local feed is a sub-feed of `apps`
    - the local feed is stand-alone (problem: we need to store the private key
      somewhere, we need to create a bunch of stuff, I think it's a bad idea)
      I suggest using the `apps` feed, and make use of the 16 bytes that are not
      defined for the app name (feed id and name should be all we need to
      identify it)
2. Create 2 new packet types: `create` and `delete`. `create` points to a blob
   with the needed data (see above) and `delete` is a normal log with the feed
   id and game identifier (that implies that it is no longer than 16 bytes)

## Remarks

1. I'm getting lost with the encodings: cbor, bipf, hex, bytes... Which one
   should I use?
2. Data to keep track of:
    1. outside of logs:
        1. name
        2. root public key
        3. root private key
    2. in root log:
        1.

## [outdated] Log tree

We decided to keep the root log as holder of metadata only. It keeps information
about 3 default sub-feeds (sub-feeds are child feeds):

- aliases : a contact list, with pk as keys and names (how I personally
  call them) as values
- config  : name and feed id of the root
- apps    : a dictionary of the used apps. The keys are the app names and
  the values are the corresponding feed ids.

In addition, each app has its own log (a child feed). A programmer is free to
use the feed for its own application, and a friendly peer will replicate only
this sub-feed. The other 3 peers are (for the moment) not replicated (and not
encrypted).

Proposition:
The content of the default feeds is bipf encoded, it is just a list. We
introduce 2 new packet types `0x07` and `0x08` that correspond respectively to
`set` and `delete` (a `delete` comes only after a `set`).

Should we separate (in the folder) my personal feeds from the other feeds
(which are read-only)? [No]

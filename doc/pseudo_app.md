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
rd = identity.get_root_directory()
ad = rd['apps']
chess_games = ad['chess']
ui = ...
identity.launch_app(chess_games, ui)  # enter the app

# print the different sessions (subfeeds) available
# A session is a subfeed that is shared with one peer
with_ = input(rd['alias'])

session = identity.open_session(with_)

while True:
    msg = ui.input("> ")
    if msg == 'quit':
        identity.sync()
        break
    else:
        identity.send(msg)

```

## 'Directory'

The navigation data can be obtained by get_root_directory(), and we call it
`directory`. It is a python list of this form (`bin_key` is a byte array key):

```python
directory = {
    'apps': {
        'chess': '`bin_key`',  # personal keys only
        'chat': '`bin_key`'
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

- `public` :  my public identity (ex: I want to start a chess game)
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

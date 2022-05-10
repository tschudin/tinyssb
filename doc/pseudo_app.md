# Pseudocode for a chat app using TinySSB

_draft 2022-05-10_

## Abstract

To construct a good API, I write an elegant pseudocode for a chat app, and I'll
stick the actual API to it.

## Example 1

```python
import tinyssb as tiny

# List ids that I can load
print(tiny.list_identities())
i = input("Choose an identity to open")
if x:
    identity = tiny.fetch_id(i)
else:
    identity = tiny.generate_id()

act = input(identity.activities())  # choose a log

if not identity.open(act):
    identity.start(act)  # Create a new feed
```

## Example 2

```python
import tinyssb as tiny

# List ids that I can load
print(tiny.list_identities())
i = input("Choose an identity to open")
if x:
    identity = tiny.fetch_id(i)
else:
    identity = tiny.generate_id()

chat = input(identity.chats())  # choose a conversation with a peer

chat.open()
while True:
    msg = input("> ")
    if msg == 'quit':
        chat.close()
    else:
        chat.send(msg)

```

## Example 3

```python
import tinyssb as tiny

# List ids that I can load (also print it) 
ids = tiny.list_identities()
i = input("Choose an identity to open (write its ")
if x:
    identity = tiny.fetch_id(i)
else:
    identity = tiny.generate_id()

# print the different sessions (subfeeds) available
# A session is a subfeed that is shared with one peer
print(identity.sessions())
remote_key = input("Enter the public key for a new session")
# session = identity.create_session()
session = identity.open_session()

session.open()
while True:
    msg = input("> ")
    if msg == 'quit':
        session.close()
    else:
        session.send(msg)

```

## Example 4 Open existing

```python
import tinyssb as tiny

# List ids that I can load (also print it) 
ids = tiny.list_identities()
i = input("Choose an identity to open (write its ")
identity = tiny.fetch_id(i)
rd = identity.get_root_directory()
ad = rd['apps']
chess_games = ad['chess']

chess_games[1].start()  # start a thread in the background

# print the different sessions (subfeeds) available
# A session is a subfeed that is shared with one peer
print(identity.application_list())

session = identity.open_session()

session.open()
while True:
    msg = input("> ")
    if msg == 'quit':
        session.close()
    else:
        session.send(msg)

bipf(['set', string, feedID])

bipf(['del', string])

```

## Idea list

1. Have a root feed that controls the identity, but used mostly for metadata
2. Have `sessions` that are sub-feeds (child logs) to communicate with one
   person

##

1. One session per application
2. Root feed as dict to pointer to aliases (private, about other peers), feed
   information, apps dictionary

## Log tree

We decided to keep the root log as holder of metadata only. It keeps information
about 3 default sub-feeds (sub-feeds are child feeds):

- aliases     : a contact list, with pk as keys and names (how I personally
  call them) as values
- information : (what exactly?)
- apps        : a dictionary of the used apps. The keys are the app names and
  the values are the corresponding feed ids.

In addition, each app has its own log (a child feed). A programmer is free to
use the feed for its own application, and a friendly peer will replicate only
this sub-feed. The other 3 peers are (for the moment) not replicated (and not
encrypted).

[Proposition]
The content of the default feeds is bipf encoded, it is just a list. We
introduce 2 new packet types `0x07` and `0x08` that correspond respectively to 
`set` and `delete` (a `delete` comes only after a `set`).


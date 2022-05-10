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
session = identity.add_session()

session.open()
while True:
    msg = input("> ")
    if msg == 'quit':
        session.close()
    else:
        session.send(msg)
    
```

## Idea list

1. Have a root feed that controls the identity, but used mostly for metadata
2. Have `sessions` that are subfeeds (child logs) to communicate with one person





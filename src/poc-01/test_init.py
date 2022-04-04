#!/usr/bin/env python3

# test_init.py

import binascii
import json
import os
import pure25519
import sys

def hex(b):
    return binascii.hexlify(b).decode()

os.system("rm -rf data")

nodes = {}
anchors = []
# create IDs:
for nm in ['nodeA', 'nodeB', 'nodeC']:
    sk, _ = pure25519.create_keypair()
    sk,pk = sk.sk_s[:32], sk.vk_s # just the bytes
    # create the first message:
    msgID0 = b'abc'
    anchors.append( (hex(pk), 0, hex(msgID0)) )
    nodes[pk] = {
        "name":   nm,
        "feedID": hex(pk),
        "secret": hex(sk),
        "msgID0": hex(msgID0)
    }

# add mutual trust anchors:
for n in nodes.values():
    n['trusted'] = [a for a in anchors if a[0] != n['feedID']]

# write it all out
for n in nodes.values():
    pfx = 'data/' + n['name']
    os.system(f"mkdir -p {pfx}/_blob")
    os.system(f"mkdir -p {pfx}/_logs")
    if sys.implementation.name == 'micropython':
        with open(f"{pfx}/config.json", "w") as f: json.dump(n, f)
        with open(f"{pfx}/state.json", "w") as f:  json.dump({}, f)
    else:
        with open(f"{pfx}/config.json", "w") as f: json.dump(n, f, indent=2)
        with open(f"{pfx}/state.json", "w") as f:  json.dump({}, f, indent=2)

os.system("find data|sort")

# eof

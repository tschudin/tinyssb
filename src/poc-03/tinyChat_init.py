#!/usr/bin/env python3

# test_init.py
# 2022-04-06 <christian.tschudin@unibas.ch>

import binascii
import json
import os
import pure25519
import sys

from tinyssb import packet, repository

def hex(b):
    return binascii.hexlify(b).decode()

os.system("rm -rf data")

nodes = {}
# create IDs:
for nm in ['Alice', 'Bob', 'Carla']:
    sk, _ = pure25519.create_keypair()
    sk,pk = sk.sk_s[:32], sk.vk_s # just the bytes
    # anchors.append(pk)
    nodes[pk] = {
        "name":   nm,
        "feedID": pk,
        "secret": sk
    }
alias = {hex(n['feedID']):n['name'] for n in nodes.values()}
for n in nodes.values():
    n['alias'] = alias

# list of public keys that all have to mutually trust
anchors = [n['feedID'] for n in nodes.values()]

def mksignfct(secret):
    sk = pure25519.SigningKey(secret)
    return lambda m: sk.sign(m)

def mkverifyfct(secret):
    def vfct(pk, s, msg):
        try:
            pure25519.VerifyingKey(pk).verify(s,msg)
            return True
        except Exception as e:
            print(e)
        return False
    return vfct

# create genesis entry and add mutual trust anchors
for n in nodes.values():
    pfx = './data/' + n['name']
    os.system(f"mkdir -p {pfx}/_blob")
    os.system(f"mkdir -p {pfx}/_logs")
    cfg = { k:hex(v) if type(v) == bytes else v for k,v in n.items() }
    with open(f"{pfx}/config.json", "w") as f: json.dump(cfg, f)
    repo = repository.REPO(pfx, mkverifyfct(n['secret']))
    feed = repo.mk_generic_log(n['feedID'], packet.PKTTYPE_plain48,
                               b'log entry 1', mksignfct(n['secret']))
    for other in anchors:
        if other != n['feedID']:
            repo.allocate_log(other, 0, other[:20]) # install trust anchor

os.system("find data|sort")

# eof

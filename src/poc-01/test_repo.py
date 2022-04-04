#!/usr/bin/env python3

# test_repo.py  -- disk storage of logs and sidechains

import binascii
import json
import os
import pure25519
import time

from tinyssb import packet, repository

def fromhex(h):
    return binascii.unhexlify(h)

# ----------------------------------------------------------------------

if __name__ == '__main__':
    
    pfx = './data/nodeA'
    with open(pfx + '/config.json', 'r') as f:
        cfg = json.load(f)
    print("--> run `test_init.py` before running this script, or from time to time")
    print("node:", cfg['name'])

    fid = fromhex(cfg['feedID'])
    sk = pure25519.SigningKey(fromhex(cfg['secret']))
    
    def signing_fct(msg):
        return sk.sign(msg)
    def verify_fct(pk,sig,msg):
        try:
                pure25519.VerifyingKey(pk).verify(sig,msg)
                return True
        except Exception as e:
            print(e)
            return False

    repo = repository.REPO(pfx, verify_fct)
    feed = repo.get_log(fid) # recover persisted trust anchor and feed state
    if feed == None:      # or create new log
        feed = repo.genesis_log(fid,
                                b'hello, first log entry',
                                signing_fct)

    seq, mid = feed.frontS, feed.frontM  # retrieve latest trust tuple
    # create and append 5 log entries
    for i in range(5):
        seq += 1
        entry = packet.PACKET(fid, seq, mid)
        entry.mk_plain_entry(bytes([48+seq]*48), lambda m: sk.sign(m))
        feed.append(entry.wire)
        mid = entry.mid

    # demonstrate random access to each log entry's content, include sidechain
    for i in range(feed.frontS):
        e = feed[i+1]       # any number could be given, in any order
        print("[" + str(e.seq) + "]", end=' ')
        if e.has_sidechain():
            e.undo_chain(lambda ptr: repo.get_blob(ptr))
            print(e.chain_content)
        else:
            print(e.payload)

    # create and append one log entry with a blob sidechain
    seq += 1
    chain_entry = packet.PACKET(entry.fid, seq, mid)
    blobs = chain_entry.mk_chain(str(time.localtime()).encode() + b' | ' + \
                                 b'more than 48 bytes is ' * 10,
                                 lambda m: sk.sign(m))
    feed.append(chain_entry.wire)
    for b in blobs:
        repo.add_blob(b)

    # retrieve the content of the new blob sidechain

    # in-memory example:
    #   blob_dict = { packet.blob2hashptr(b):b for b in blobs }
    #   chain_entry.undo_chain(lambda ptr: blob_dict[ptr])
    # from disk:
    chain_entry.undo_chain(lambda ptr: repo.get_blob(ptr))
    # print(chain_entry.seq, chain_entry.chain_content)

# eof

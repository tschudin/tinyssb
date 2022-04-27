#!/usr/bin/env python3

# log_burning_demo.py
# 2022-04-11 christian.tschudin@unibas.ch

# create a constant stream of update for Alice's symtab that she replicates
# to Bob, using approximately four logs of limited length which together
# implement a delay-tolerant session abstraction between Alice and Bob

from tinyssb import io, keystore, node, packet
from tinyssb import repository, session, symtab, util
from tinyssb.dbg import *

import json
import os
import sys
import time


# ----------------------------------------------------------------------

def start_node(path):
    with open(path + '/config.json') as f:
        cfg = json.load(f)
    me = util.fromhex(cfg['feedID'])
    alias = {util.fromhex(k):v for k,v in cfg['alias'].items()}
    peerlst = [pk for pk in alias if pk != me]
    alias = {v:k for k,v in alias.items()}
    with open(path + '/keystore.json') as f:
        ks = keystore.Keystore(json.load(f))

    faces = [io.UDP_MULTICAST(('224.1.1.1',5000))]
    repo = repository.REPO(path, lambda pk,sig,msg: ks.verify(pk,sig,msg))
    nd = node.NODE(faces, ks, repo, me, peerlst)
    nd.start()

    return nd, alias

# ----------------------------------------------------------------------

if __name__ == '__main__':

    # --------------------------------------------------
    if sys.argv[1] == 'init':
        os.system("rm -rf data")

        nodes = {}
        for nm in ['Alice', 'Bob']: # create IDs
            ks = keystore.Keystore()
            pk = ks.new(nm)
            nodes[pk] = {
                'name':     nm,
                'feedID':   pk,
                'keystore': ks
            }
        alias = {util.hex(pk):n['name'] for pk,n in nodes.items()}
        for n in nodes.values():
            n['alias'] = alias

        # create genesis entry and add mutual trust anchors
        for pk, n in nodes.items():
            pfx = './data/' + n['name']
            os.system(f"mkdir -p {pfx}/_blob")
            os.system(f"mkdir -p {pfx}/_logs")
            with open(f"{pfx}/config.json", "w") as f:
                f.write(util.json_pp({ 'name': n['name'],
                                       'feedID': util.hex(pk),
                                       'alias': n['alias']}))
            ks = n['keystore']
            with open(f"{pfx}/keystore.json", "w") as f:
                f.write(str(ks))
            repo = repository.REPO(pfx, lambda fid,msg,sig: ks.verify(fid,msg,sig))
            feed = repo.mk_generic_log(n['feedID'], packet.PKTTYPE_plain48,
                                       b'log entry 1', lambda msg: ks.sign(pk, msg))
            for other in nodes.keys(): # install mutual trust
                if other != n['feedID']:
                    repo.allocate_log(other, 0, other[:20]) # install trust anchor

        os.system("find data|sort")

    # --------------------------------------------------
    elif sys.argv[1] == 'Alice':
        nd, alias = start_node('data/Alice')
        bob = nd.repo.get_log(alias['Bob'])
        aliceFID = alias['Alice']
        print("Alice is", util.hex(aliceFID))

        localSessFID = nd.ks.new('Alice session')
        pkts = nd.repo.mk_child_log(aliceFID, nd.ks.get_signFct(aliceFID),
                             localSessFID, nd.ks.get_signFct(localSessFID),
                             b'session-20220416')
        nd.repo.get_log(localSessFID).subscription += 1
        pkts = [nd.repo.get_log(aliceFID)[1]] + pkts
        nd.push(pkts, True) # push new session details: Bob could wait for it

        print("\nWaiting for Bob to announce his subfeed ", end='')
        while True:
            if len(bob) > 1:
                pkt = bob[-1]
                if pkt.typ[0] == packet.PKTTYPE_mkchild:
                    remoteSessFID = pkt.payload[:32]
                    break
            print(".", end='')
            sys.stdout.flush()
            time.sleep(2)
        nd.push(pkts, True) # push (again) session details if Bob was not
                            # online when we pushed the first time
        print(f"handshake received: remote sess feed is {util.hex(remoteSessFID)[:20]}..")
        print()
        
        nd.sess = session.SlidingWindow(nd, localSessFID, remoteSessFID)
        st = symtab.Symtab(slidingWindowProvider=nd.sess, port=1)
        nd.sess.start() # this does upcalls for all content received to far

        # preload a few symbols
        for i in range(10):
            val = os.urandom(10)
            sc = st.alloc(val)
            dbg(GRA, f"created shortcut {sc} for symbol 0x{util.hex(val)}")

        while True:
            val = os.urandom(10)
            sc = st.alloc(val)
            dbg(GRA, f"created shortcut {sc} for symbol 0x{util.hex(val)}")
            while True: # try to randomly remove one symbol until success
                try:
                    sc = os.urandom(1)[0] % len(st.tbl)
                    st.free(sc)
                    dbg(GRA, f"removed shortcut {sc}")
                    break
                except IndexError:
                    pass

            time.sleep(2)
            dbg(GRA, f"* Alice len(keystore)={len(nd.ks.kv)},",
                     f"len(dmxt)={len(nd.dmxt)},",
                     f"len(openlogs)={len(nd.repo.open_logs)}")

    # --------------------------------------------------
    elif sys.argv[1] == 'Bob':
        nd, alias = start_node('data/Bob')
        alice = nd.repo.get_log(alias['Alice'])
        bobFID = alias['Bob']
        print("Bob is", util.hex(bobFID))

        localSessFID = nd.ks.new('Bob session')
        pkts = nd.repo.mk_child_log(bobFID, nd.ks.get_signFct(bobFID),
                                 localSessFID, nd.ks.get_signFct(localSessFID),
                                 b'session-20220416')
        pkts = [nd.repo.get_log(bobFID)[1]] + pkts
        nd.push(pkts, True) # push new session details: Alice could wait for it

        print("\nWaiting for Alice to announce her subfeed ", end='')
        while True:
            if len(alice) > 1:
                pkt = alice[-1]
                if pkt.typ[0] == packet.PKTTYPE_mkchild:
                    remoteSessFID = pkt.payload[:32]
                    break
            print(".", end='')
            sys.stdout.flush()
            time.sleep(2)
        print('\nhandshake received', util.hex(remoteSessFID))
        nd.push(pkts, True) # push (again) session details if Alice was not
                            # online when we pushed the first time
        
        nd.sess = session.SlidingWindow(nd, localSessFID, remoteSessFID)
        st = symtab.Symtab(slidingWindowProvider=nd.sess, port=1)
        st.set_upcall(lambda chg: dbg(BLU, 'symtab notification:',
                       [x if type(x) != bytes else util.hex(x) for x in chg]))
        nd.sess.start() # this does upcalls for all content received to far

        while True:
            time.sleep(5)
            dbg(GRA, f"* Bob len(keystore)={len(nd.ks.kv)},",
                     f"len(dmxt)={len(nd.dmxt)},",
                     f"len(openlogs)={len(nd.repo.open_logs)}")

    # --------------------------------------------------
    else:
        print('usage ...')

# eof

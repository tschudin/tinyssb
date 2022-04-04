#!/usr/bin/env python3

# test_prodcons.py  -- a consumer asking for new log entries

import hashlib
import json
import os
import sys
import _thread
import time

from tinyssb import io, node, packet, repository, util
from tinyssb.dbg import *

# ----------------------------------------------------------------------

'''
   a very simple (not scalable, not private) replication protocol:
     . new entries are proactively broadcast
     . consumers repeatedly ask for the subsequent entry for their log
     . timeout is set to slightly bigger than production interval

   general form for replication commands:
      DMX = hash(fid_A + CMD)[:7]
      PACKET = DMX + command_arguments

   replication request:
     CMD == b'want'
     DMX = hash(fid_of_peer_node + CMD)[:7]
     PAYLOAD = N * (fid_of_request_log (32B) + request_seq (4B, big endian))
     PACKET = DMX + PAYLOAD (total 7 + N*36)

'''

# ----------------------------------------------------------------------

def dmx(nm):
    return hashlib.sha256(nm).digest()[:7]

def want_handler(nd, demx, buf, neigh):
    dbg(GRA, f'RCV want@dmx={util.hex(demx)}')
    buf = buf[7:]
    while len(buf) >= 24:
        fid = buf[:32]
        seq = int.from_bytes(buf[32:36], 'big')
        # if fid != cfg['fid']: # only return this node's log
        #     dbg(RED, '    ignored (request for wrong fid)')
        #     break
        h = util.hex(fid)[:20]
        try:
            feed = nd.repo.get_log(fid)
            if feed:
                neigh.face.enqueue(feed[seq].wire)
                dbg(GRA, f'    have {h}.[{seq}], will send')
        except:
            dbg(GRA, f"    no entry for {h}.[{seq}]")
        buf = buf[36:]

def producer(nd, cfg):
    import time

    # serve want requests for all logs we have (don't do this in practice!)
    for fid in nd.repo.listlog():
        want_dmx = dmx(fid + b'want')
        dbg(GRA, f"+dmx want@{util.hex(want_dmx)} for {util.hex(fid)[:20]}...")
        nd.arm_dmx(want_dmx, lambda buf,n: want_handler(nd, want_dmx, buf, n))

    while True: # produce
        time.sleep(5)
        msg = str(time.localtime()).encode() # time.ctime(time.time()).encode()
        seq, mid = nd.feed.getfront()
        pkt = packet.PACKET(cfg['fid'], seq+1, mid)
        pkt.mk_plain_entry(msg, nd.sign)
        nd.feed.append(pkt.wire)
        for f in nd.faces:
            f.enqueue(pkt.wire)
        dbg(GRE, f"[{seq+1}] enqueued for first time")

def consumer(nd, fid):
    import time
    replica = nd.repo.get_log(fid)
    if replica == None:
        print("must start producer before (this) consumer")
        sys.exit(-1)
    next_timeout = [0]

    def arm_for_front():
        front = replica.getfront()
        nextseq = (front[0]+1).to_bytes(4, 'big')
        pktdmx = dmx(packet.PFX + fid + nextseq + front[1])
        dbg(GRA, f"+dmx pkt@{util.hex(pktdmx)} for {util.hex(fid)[:20]}.[{front[0]+1}]")
        nd.arm_dmx(pktdmx, lambda buf,n: append_latest(nd, pktdmx, buf, n))
        
    def request_latest():
        arm_for_front()
        seq = len(replica)+1
        want_dmx = dmx(fid + b'want')
        wire = want_dmx + fid + seq.to_bytes(4, 'big')
        # does not need padding to 128B, it's not a log entry or blob
        d = util.hex(want_dmx)
        h = util.hex(fid)[:20]
        for f in nd.faces:
            f.enqueue(wire)
            dbg(GRA, f"SND want request to dmx={d} for {h}.[{seq}]")
        
    def append_latest(nd, d, buf, n):
        dbg(GRA, f'RCV pkt@dmx={util.hex(d)}, try to append it')
        if not replica.append(buf):
            dbg(RED, "    verification failed")
        else:
            nd.arm_dmx(d) # remove current DMX handler, request was satisfied
            h = util.hex(replica.fid)[:20]
            dbg(GRE, f"    append {h}.[{len(replica)}]")
            request_latest()
            # set timeout to 1sec more than production interval
            next_timeout[0] = time.time() + 6

    # serve want requests for all logs we have (don't do this in practice!)
    for fid in nd.repo.listlog():
        want_dmx = dmx(fid + b'want')
        dbg(GRA, f"+dmx want@{util.hex(want_dmx)} for {util.hex(fid)[:20]}...")
        nd.arm_dmx(want_dmx, lambda buf,n: want_handler(nd, want_dmx, buf, n))

    while True: # periodic ARQ
        now = time.time()
        if next_timeout[0] < now:
            request_latest()
            next_timeout[0] = now + 9
            time.sleep(10)
        else:
            time.sleep(next_timeout[0] - now)

def mksignfct(secret):
    if sys.implementation.name == 'micropython':
        import hmac
        return lambda m: hmac.new(secret,m,'sha512').digest()
    else:
        import pure25519
        sk = pure25519.SigningKey(secret)
        return lambda m: sk.sign(m)

def mkverifyfct(secret):
    if sys.implementation.name == 'micropython':
        import hmac
        return lambda pk, s, m: hmac.new(secret,m,'sha512').digest() == s
    else:
        import pure25519
        def vfct(pk, s, m):
            try:
                pure25519.VerifyingKey(pk).verify(s,m)
                return True
            except Exception as e:
                print(e)
                return False
        return vfct

# ----------------------------------------------------------------------

if __name__ == '__main__':
    import argparse

    def ip2tuple(arg):
        a = arg.split('/')
        return a[0], int(a[1])

    e = '''
      *add means that an option can be given several times. Remember to
      reset the file system with ./test_init.py before running this demo.
    '''
    p = argparse.ArgumentParser(description='tinySSB Producer/Consumer Demo',
                                epilog=e)
    p.add_argument('-kiss', type=str, metavar='SERIALDEV', action='append',
          help='*add a face to serial device, e.g. /dev/tty.usbserial-0001')
    p.add_argument('-udp',  type=str, metavar='HOST/PORT', action='append',
          help='*add a face to remote UDP port, e.g. 192.168.4.1/5001')
    p.add_argument('-mc',   type=str, metavar='GROUP/PORT', action='append',
          help='*add a face to multicast group, e.g. 224.1.1.1/5000')
    p.add_argument('-cons', type=str, metavar='nodeB|nodeC',
          help='run as a consumer (default is producer nodeA)')
    args = p.parse_args()

    print("Producer/consumer demo for the tinySSB Python library")
    pfxA = './data/nodeA'
    pfxB = './data/nodeB'
    pfxC = './data/nodeC'
    with open(pfxA + '/config.json', 'r') as f:
        cfgA = json.load(f)
        cfgA['sign'] = mksignfct(util.fromhex(cfgA['secret']))
        cfgA['verify'] = mkverifyfct(util.fromhex(cfgA['secret']))
        cfgA['fid'] = util.fromhex(cfgA['feedID'])

    faces = []

    if args.kiss:
        for k in args.kiss:
            kiss = io.KISS(k)
            if kiss.ser != None:
                faces.append(kiss)
    if args.udp: #  192.168.4.1/5001
        for u in args.udp:
            udp = io.UDP_UNICAST( ip2tuple(u) )
            faces.append(udp)
    if args.mc:  #  224.1.1.1/5000
        for m in args.mc:
            mc = io.UDP_MULTICAST( ip2tuple(m) )
            faces.append(mc)

    if len(faces) == 0:
        faces = [io.UDP_MULTICAST( ('224.1.1.1',5000) )]

    if args.cons == None:
        print("Producer nodeA:")
        nodeA = node.NODE(faces)
        nodeA.sign = cfgA['sign']
        nodeA.repo = repository.REPO(pfxA, cfgA['verify'])
        nodeA.feed = nodeA.repo.get_log(cfgA['fid'])
        if nodeA.feed == None:
            nodeA.feed = nodeA.repo.genesis_log(cfgA['fid'], b'entry 0',
                                                nodeA.sign)
            # add this new feed as a trust anchor for node B, node C
            for p in [pfxB, pfxC]:
                r = repository.REPO(p, cfgA['verify'])
                feedA = r.create_log(cfgA['fid'], 0, cfgA['fid'][:20])
            del feedA  # release the open file
        nodeA.start()
        _thread.start_new_thread(producer, (nodeA, cfgA))
    else:
        pfx = pfxB if args.cons == 'nodeB' else pfxC
        print(f"Consumer {args.cons}:")
        nd = node.NODE(faces)
        nd.repo = repository.REPO(pfx, cfgA['verify'])
        nd.start()
        _thread.start_new_thread(consumer, (nd, cfgA['fid']))

    try:
        input('Enter return to terminate...\n\n')
    except:
        pass

# eof

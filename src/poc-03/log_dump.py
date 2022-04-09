#!/usr/bin/env python3

# log_dump.py
# 2022-04-09 <christian.tschudin@unibas.ch>

import hashlib

from tinyssb import packet, repository, util

# ----------------------------------------------------------------------

def wrap(s):
    if len(s) < 65:
        return s
    return [s[0+i:64+i] for i in range(0, len(s), 64)]
    
def toHex(buf):
    if buf == None:
        return None
    return wrap(util.hex(buf))

def get_blob(blobdirname, hashptr):
    if blobdirname == None: return ('?', None)
    h = util.hex(hashptr)
    fn = blobdirname + '/' + h[:2] + '/' + h[2:]
    try:
        with open(fn, "rb") as f:
            return fn, f.read(120)
    except Exception as e:
        return fn, None

# ----------------------------------------------------------------------

def dump_generator(log_file_path, blob_dir_path=None, chain_depth=0):
    # chain_depth == -1: dump the full chain
    from collections import OrderedDict

    feed = repository.LOG(log_file_path, None)
    if feed == None:
        print("no such feed")
        return
    yield OrderedDict([
        ('dumptype',     'tinySSB log file'),
        ('fid',          toHex(feed.fid)),
        ('path',         wrap(log_file_path)),
        ('anchor.seq',   feed.anchrS),
        ('anchor.msgID', toHex(feed.anchrM)),
        ('front.seq',    feed.frontS),
        ('front.msgID',  toHex(feed.frontM)),
        ('store_length', feed.frontS - feed.anchrS)
    ])
    seq,mid = feed.anchrS, feed.anchrM
    for p in feed:
        if p.seq > feed.anchrS:
            seq += 1
            nam = feed.fid + seq.to_bytes(4, 'big') + mid
            newmid = p._mid()
            t = '0x%02x = ' % p.typ[0]
            t += ['PKTTYPE_plain48',
                  'PKTTYPE_chain20',
                  'PKTTYPE_ischild',
                  'PKTTYPE_iscontn',
                  'PKTTYPE_mkchild',
                  'PKTTYPE_contdas'][p.typ[0]]
            blobchain = []
            pktdict = OrderedDict([
                ('dumptype',  'tinySSB log entry (packet)'),
                ('fid*',      toHex(feed.fid)),
                ('seq*',      seq),
                ('prev*',     toHex(mid)),
                ('name*',     toHex(nam)),
                ('dmx*',      toHex(packet._dmx(nam))),
                ('mid*',      toHex(newmid)),
                ('raw_len',   len(p.wire)),
                ('raw',       toHex(p.wire)),
                ('hptr',      toHex(hashlib.sha256(p.wire).digest()[:20])),
                ('dmx',       toHex(p.dmx)),
                ('type',      t),
                ('payload',   toHex(p.payload)),
            ])
            if p.typ[0] == packet.PKTTYPE_chain20:
                p.undo_chain(lambda hptr: get_blob(blob_dir_path, hptr)[1])
                chaindict = OrderedDict()
                chaindict['content_declared_len'] = p.chain_len
                chaindict['content_available_len'] = len(p.chain_content)
                chaindict['content'] = toHex(p.chain_content)
                if p.chain_firstptr != None:
                    chaindict['first_blob'] = toHex(p.chain_firstptr)
                pktdict['sidechain'] = chaindict
                if p.chain_firstptr != None and blob_dir_path != None:
                    ptr = p.chain_firstptr
                    while chain_depth <= -1 or chain_depth > 0:
                        fn, b = get_blob(blob_dir_path, ptr)
                        blobchain.append((fn,b))
                        if b == None: break
                        ptr = b[-20:]
                        if ptr == bytes(20): break
                        chain_depth -= 1
            if p.typ[0] == packet.PKTTYPE_ischild:
                pktdict['parent_fid'] = toHex(p.payload[:32])
                pktdict['parent_seq'] = int.from_bytes(p.payload[32:36], 'big')
                pktdict['proof'] = toHex(p.payload[36:])
            if p.typ[0] == packet.PKTTYPE_iscontn:
                pktdict['predecessor_fid'] = toHex(p.payload[:32])
                pktdict['predecessor_seq'] = int.from_bytes(p.payload[32:36], 'big')
                pktdict['proof'] = toHex(p.payload[36:])
            if p.typ[0] == packet.PKTTYPE_mkchild:
                pktdict['child'] = toHex(p.payload[:32])
            if p.typ[0] == packet.PKTTYPE_contdas:
                pktdict['contd'] = toHex(p.payload[:32])
            pktdict['signature'] = toHex(p.signature)
            yield pktdict

            mid = newmid
            for b in blobchain:
                blobDir = OrderedDict([
                    ('dumptype', 'tinySSB chained blob'),
                    ('path',     b[0]),
                ])
                if b[1] != None:
                    b = b[1]
                    blobDir['hptr'] = toHex(hashlib.sha256(b).digest()[:20])
                    blobDir['content'] = toHex(b[:100])
                    if b[-20:] != bytes(20):
                        blobDir['next'] = toHex(b[-20:])
                yield blobDir

# ----------------------------------------------------------------------

if __name__ == '__main__':
    import glob
    import sys

    if len(sys.argv) <= 1 or sys.argv[1].startswith('-h'):
        print(f"usage: {sys.argv[0]} LOG_FILE_GLOB")
    else:
        # FIXME: parse chain depth command line parameter
        blobdir = '/'.join(sys.argv[1].split('/')[:-2]) + '/_blob'
        print("[\n")
        for fn in glob.glob(sys.argv[1]):
            for d in dump_generator(fn, blobdir, -1):
                print(util.json_pp(d) + ',\n')
        print("null\n]") # in order to output correct JSON code

# eof

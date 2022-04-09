#!/usr/bin/env python3

# ftree_load.py
# 2022-04-09 <christian.tschudin@unibas.ch>

from tinyssb import packet, repository, util

def print_feed_tree(repo, lvl, fid):
    feed = repo.get_log(fid)
    e = '..'
    if feed[-1].typ[0] == packet.PKTTYPE_contdas:
        e = ']]' if feed[-1].payload[:32] == bytes(32) else '>>'
    if feed[1].typ[0] == packet.PKTTYPE_iscontn:
        a = '>'
    elif feed[1].typ[0] == packet.PKTTYPE_ischild:
        a = '+'
    elif lvl == 0:
        a = '/'
    else:
        a = '?'
    print(f"{'    '* lvl}  {a} {util.hex(fid)}{e}")
    for i in range(2, len(feed)+1):
        pkt = feed[i]
        if pkt.typ[0] == packet.PKTTYPE_mkchild:
            print_feed_tree(repo, lvl+1, pkt.payload[:32])

    pkt = feed[-1]
    if pkt.typ[0] != packet.PKTTYPE_contdas or pkt.payload[:32] == bytes(32):
        return
    fid = pkt.payload[:32]
    print_feed_tree(repo, lvl, fid)

# ----------------------------------------------------------------------

if __name__ == '__main__':
    import sys

    root_feed_path = sys.argv[1]
    root = repository.LOG(root_feed_path, None)
    repo_path = '/'.join(root_feed_path.split('/')[:-2])
    repo = repository.REPO(repo_path, None)

    print(sys.argv[0], f"- display feed tree from repo at '{repo_path}'")
    print(
"""
    / xx   'this is the root feed'
    + xx   'this is a sub feed'
    > xx   'this is a continuation feed'
    xx..   'feed can still be appended to'
    xx>>   'feed has a continuation'
    xx]]   'feed has ended'
""")

    print_feed_tree(repo, 0, root.fid)

# eof

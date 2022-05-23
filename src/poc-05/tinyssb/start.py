# tinyssb/start.py
import json
import os
import bipf
import cbor2

from . import io, keystore, node, packet
from . import repository, util, identity
from .dbg import *

DATA_FOLDER = './data/'

# ----------------------------------------------------------------------------------------

def generate_id(peer_name):
    prefix = DATA_FOLDER + peer_name
    ks = keystore.Keystore()
    pk = ks.new(peer_name)
    root = _mount_identity(prefix, peer_name, ks, pk)
    default = {}

    for n in ['aliases', 'public', 'apps']:
        fid = root.ks.new(n)
        name = cbor2.dumps(n)
        name += bytes(16 - len(name))
        root.repo.mk_child_log(root.me, root.ks.get_signFct(root.me), fid,
                               root.ks.get_signFct(fid), name)
        default[n] = fid
    return identity.Identity(root, peer_name, default)

def write_bipf(write_to, content, fid):
    data = bipf.dumps(content)
    # dbg(RED, f"{len(data)}")
    if len(data) > 48:
        write_to.write_blob_chain(fid, data, lambda msg: write_to.ks.sign(fid, msg))
    else:
        data = data + bytes(48 - len(data))
        write_to.write_plain_48B(fid, data, lambda msg: write_to.ks.sign(fid, msg))

def read_bipf(repo, fid, seq=-1):
    log = repo.get_log(fid)
    if seq < 0:
        seq = log.frontS
    pack = log.__getitem__(seq)
    # dbg(RED, f"{pack.typ}")
    if pack.typ[0] == packet.PKTTYPE_chain20:
        # We first need to fetch the data for blob packets
        pack.undo_chain(lambda h: repo.fetch_blob(h))
    # dbg(GRE, f"\nactual  {bipf.loads(pack.get_content())}")
    return pack.get_content()

def _mount_identity(pfx, name, ks, pk):
    """
    Create a new identity (not following any other peer).
    :param name: the given name for the peer
    :param ks: Keystore
    :param pk: public key
    :return: instance of Node
    """

    os.system(f"mkdir -p {pfx}/_blob")
    os.system(f"mkdir -p {pfx}/_logs")
    os.system(f"mkdir -p {pfx}/_backed")
    with open(f"{pfx}/_backed/config.json", "w") as f:
        f.write(util.json_pp({'name': name,
                              'rootFeedID': util.hex(pk)}))
    # with open(f"{pfx}/_backed/keystore.json", "w") as f:
    #     f.write(str(ks))
    repo = repository.REPO(pfx, lambda fid, msg, sig: ks.verify(fid, msg, sig))
    repo.mk_generic_log(pk, packet.PKTTYPE_plain48,
                        b'log entry 1', lambda msg: ks.sign(pk, msg))
    return _start_node(repo, ks, pk, [])


def load_identity(name):
    """Matching version of mount_identity() for existing peers"""
    pfx = DATA_FOLDER + name
    with open(pfx + '/_backed/config.json') as f:
        cfg = json.load(f)
    me = util.fromhex(cfg['rootFeedID'])
    # alias = {util.fromhex(k): v for k, v in cfg['alias'].items()}
    # peer_list = [pk for pk in alias if pk != me]
    # alias = {v: k for k, v in alias.items()}

    ks = keystore.Keystore()
    ks.load(pfx + '/_backed/' + cfg['rootFeedID'])
    # dbg(MAG, f"CHILD: {name}:fid")

    repo = repository.REPO(pfx, lambda pk, sig, msg: ks.verify(pk, sig, msg))
    root = _start_node(repo, ks, me, [])
    log = root.repo.get_log(me)
    default = {}
    for i in range(len(log)+1):
        pkt = log[i]
        # dbg(MAG, f"LOOK: {util.hex(pkt.typ)}:{pkt.typ[0]}; {packet.PKTTYPE_mkchild}")
        if pkt.typ[0] == packet.PKTTYPE_mkchild:
            fid = pkt.payload[:32]
            log_name = cbor2.loads(pkt.payload[32:])
            default[log_name] = fid
            # dbg(MAG, f"CHILD: \n{log_name} for {fid} typ = {pkt.typ}")
    return identity.Identity(root, name, default)


def _start_node(repo, ks, me, peer_list):
    faces = [io.UDP_MULTICAST(('224.1.1.1', 5000))]
    nd = node.NODE(faces, ks, repo, me, peer_list)
    nd.start()
    return nd


def follow(nd, pk, nickname):
    """
    Follow / subscribe to a feed
    :param nd: an instance of node
    :param pk: the bin encoded feedID (public key)
    :param nickname: name to give to the peer
    :return:
    """
    # at the start to throw error before doing anything else if not valid
    public_key = util.hex(pk)
    with open(f"{nd.repo.path}/config.json") as f:
        config = json.load(f)
    if public_key in config['alias']:
        dbg(GRE, f"Public key {public_key[:8]} already trusted")
    else:
        dbg(GRE, f"Public key {public_key[:8]} not yet trusted")
        name = config['name']
        feedID = config['feedID']
        alias = config['alias']
        alias[public_key] = nickname
        with open(f"{nd.repo.path}/config.json", "w") as f:
            f.write(util.json_pp({'name': name,
                                  'feedID': feedID,
                                  'alias': alias}))
        # install trust anchor
        print(f"Ret: {nd.repo.allocate_log(pk, 0, pk[:20])}")
    return nd

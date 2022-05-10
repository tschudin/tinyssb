# tinyssb/__init__.py
import json
import os
import bipf

from . import io, keystore, node, packet
from . import repository, util
from .dbg import *

DATA_FOLDER = './data/'

# ----------------------------------------------------------------------------------------


def create_keys(name):
    ks = keystore.Keystore()
    pk = ks.new(name)
    return ks, pk

def generate_id(name):
    prefix = DATA_FOLDER + name
    ks, pk = create_keys(name)
    root = _mount_identity(prefix, name, ks, pk)
    default = {}

    for l in ['aliases', 'info', 'apps']:
        fid = root.ks.new(l)
        root.repo.mk_child_log(root.me, root.ks.get_signFct(root.me), fid,
                          root.ks.get_signFct(fid))
        default[l] = fid
    set = {'set': default}
    _write_in_feed(root, default)

def set_in_feed(write_to, name, feedID):
    data = bipf.dumps({name: feedID})
    dbg(YEL, f"{len(data)}, {data}")
    read = bipf.loads(data)
    dbg(YEL, read)

def _write_in_feed(write_to, message):
    data = bipf.dumps(message)
    dbg(YEL, f"{len(data)}, {data}")
    read = bipf.loads(data)
    dbg(YEL, read)
    pass

def _mount_identity(pfx, name, ks, pk):
    """
    Create a new identity (not following any other peer).
    :param name: the given name for the peer
    :param ks: Keystore
    :param pk: public key
    :return: instance of Node
    """
    alias = {util.hex(pk): name}

    os.system(f"mkdir -p {pfx}/_blob")
    os.system(f"mkdir -p {pfx}/_logs")
    with open(f"{pfx}/config.json", "w") as f:
        f.write(util.json_pp({'name': name,
                              'feedID': util.hex(pk),
                              'alias': alias}))
    with open(f"{pfx}/keystore.json", "w") as f:
        f.write(str(ks))
    repo = repository.REPO(pfx, lambda fid, msg, sig: ks.verify(fid, msg, sig))
    repo.mk_generic_log(pk, packet.PKTTYPE_plain48,
                        b'log entry 1', lambda msg: ks.sign(pk, msg))
    return _start_node(repo, ks, pk, [])


def load_identity(name):
    """Matching version of mount_identity() for existing peers"""
    path = DATA_FOLDER + name
    with open(path + '/config.json') as f:
        cfg = json.load(f)
    me = util.fromhex(cfg['feedID'])
    alias = {util.fromhex(k): v for k, v in cfg['alias'].items()}
    peer_list = [pk for pk in alias if pk != me]
    alias = {v: k for k, v in alias.items()}

    ks = keystore.Keystore()
    ks.load(path + '/_backed/' + cfg['feedID'])

    repo = repository.REPO(path, lambda pk, sig, msg: ks.verify(pk, sig, msg))
    return _start_node(repo, ks, me, peer_list)

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

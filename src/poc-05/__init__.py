# tinyssb/__init__.py
import os
import json

from tinyssb import util
from tinyssb import io, keystore, node, packet
from tinyssb import repository, session, symtab, util
from tinyssb.dbg import *


__all__ = [
    'clean',
    'load_ids',
    'create_identity',
    'find_identities'
]

DATA_FOLDER = './data/'  # Should be editable

def clean():
    """
    Delete the data folder.
    This action can't be undone.
    # FIXME link to DATA_FOLDER
    """
    os.system("rm -rf data")

def load_ids(local_name='', force_local=False):
    """
    Loads the peers stored in the file system.

    :return: the local peer as Node, a list of name:Log for remotes
    """
    remote_peers = {}
    names = find_identities()
    local_node = None
    for n in names:
        opened, x, self_id = _open_identity(n, n != local_name or force_local)
        if self_id and local_node is None:
            local_node = opened
        else:
            print(f"opened: {opened}")
            remote_peers[opened] = n
    return local_node, remote_peers


def create_identity(name, follow=None):
    """
    Create a new identity
    :param name: the given name for the peer
    :param follow: a dict list of peers to follow,
                   key is peer id (hex encoded), value is the name
    :return: instance of Node
    """
    ks = keystore.Keystore()
    pk = ks.new(name)
    if follow is None:
        follow = {}
    follow[pk] = name
    alias = {util.hex(pk): name}

    pfx = DATA_FOLDER + name
    os.system(f"mkdir -p {pfx}/_blob")
    os.system(f"mkdir -p {pfx}/_logs")
    with open(f"{pfx}/config.json", "w") as f:
        f.write(util.json_pp({'name': name,
                              'feedID': util.hex(pk),
                              'alias': alias}))
    with open(f"{pfx}/keystore.json", "w") as f:
        f.write(str(ks))
    nd = _start_local_peer(pfx, pk, ks, follow)
    return nd

def find_identities():
    try:
        aliases = os.listdir(DATA_FOLDER)
    except:
        dbg(GRA, f"No identity found")
        return []
    print(f"Identity found: {aliases}")
    return aliases

# ----------------------------------------------------------------------------------------

def _open_identity(name, as_remote=False):
    """
    :param name: the name for the identity
    :param as_remote: open the peer as a remote user
    :return:
    """
    with open(DATA_FOLDER + name + '/config.json') as f:
        cfg = json.load(f)
    fid = util.fromhex(cfg['feedID'])
    alias = {util.fromhex(k): v for k, v in cfg['alias'].items()}
    peer_list = [pk for pk in alias if pk != fid]
    alias = {v: k for k, v in alias.items()}
    if not as_remote:
        try:
            with open(DATA_FOLDER + name + '/keystore.json') as f:
                ks = keystore.Keystore(json.load(f))
            return _start_local_peer(DATA_FOLDER + name, fid, ks, peer_list), alias, True
        except FileNotFoundError:
            pass
    return fid, None, False

def _start_local_peer(prefix, pk, ks, peer_list):
    faces = [io.UDP_MULTICAST(('224.1.1.1', 5000))]
    repo = repository.REPO(prefix, lambda fid, msg, sig: ks.verify(fid, msg, sig))
    repo.mk_generic_log(pk, packet.PKTTYPE_plain48,
                        b'log entry 1', lambda msg: ks.sign(pk, msg))
    nd = node.NODE(faces, ks, repo, pk, peer_list)
    nd.start()
    print(f"peer_list = {peer_list}")
    for other in peer_list:  # install mutual trust
        if util.hex(other) != pk:
            print(
                f"Ret: {nd.repo.allocate_log(other, 0, other[:20])}")  # install trust anchor
    return nd


if __name__ == '__main__':
    clean()
    find_identities()

    local, peer_nodes = load_ids('Bob')
    print(f"Found : {peer_nodes}")
    load_ids()
    for p in peer_nodes.values():
        print(f"{p}\n")
    # if local is None:
    local = create_identity('Carla', peer_nodes)
    print(local.repo.path)
    opened, x, self_id = _open_identity('Carla', True)

# tinyssb/api.py
import os
import json

import bipf
import cbor2

from tinyssb import util, start, identity
from tinyssb import io, keystore, node, packet
from tinyssb import repository, session, symtab, util
from tinyssb.dbg import *
from tinyssb.start import *

"""
Nodejs :
  ssb-keys = [
    'generate', # (create_new_peer)
    'load_or_create_sync',  # with path to folder
    'sign_obj',
    'verify_obj'
  ]:
  only generate. load is not secure yet, and sign/verify are automatic
  
  ssb-validate = [
    'initial',  # return 'state'
    'append',  # takes <state, smth?, message>
    'create',  # takes <list_of_dest, fid, null?, content(?), timestamp>
  ]:
  First version: have only
  
  ssb-ref = [
    'isFeed'  # takes <fid>
  ]
  secret_stack = [
    'secretStack',  # takes <{appKey:"..."}>
    'stack',  # takes <{port, keys}>, return exampleApp
    'exampleApp.manifest',
    'exampleApp.address',
    'exampleApp.close'
  ]
"""

__all__ = [
    'erase_all',
    'list_identities',
    'generate_id',
    'fetch_id'
    # 'Identity'
]  # Context

__id__ = [
    'get_root_directory',
    'list_contacts',
    'follow',
    'unfollow',
    'launch_app',
    'add_app',
    'open_session',
    'send',
    'request_latest',
    'add_interface',
    'sync'
]

def erase_all():
    """
    Delete all data on the file system.
    :return: None
    """
    os.system("rm -rf data")

def list_identities():
    """
    List identities that are on the data folder.
    Use case: different people use the same computer.
    To do: add security checks
    :return: an array of strings
    """
    return os.listdir(start.DATA_FOLDER)

def generate_id(name):
    """
    Create new peer (delete data if existing).
    Stores the data on the file system, make generic log, create default sub-feeds and
    add udp_multicast as interface and start it (listen/read loops).
    Only trusted peer is self
    :param name: string
    :return: an instance of Node
    """
    return start.generate_id(name)

def fetch_id(name):
    """
    Launch a peer whose data is stored locally
    :param name: the name of the folder
    :return: instance of node
    """
    return start.load_identity(name)

if __name__ == "__main__":
    # erase_all()
    # peer = generate_id("Charlie")
    peer = load_identity("Charlie")
    peer.follow(util.fromhex('ca5066b203a02b2c1c200f9d9e6fb096058bfa01d0aef146d3856388964df56d'), "Paul")
    peer.follow(util.fromhex('da5066b203a02b2c1c200f9d9e6fb096058bfa01d0aef146d3856388964df56d'), "John")
    peer.unfollow(util.fromhex('da5066b203a02b2c1c200f9d9e6fb096058bfa01d0aef146d3856388964df56d'))

    dbg(BLU, f"{peer.directory['aliases']}")
    # dbg(GRE, util.hex(peer._node.peers[0]))
    # dbg(BLU, f"{[util.hex(v) for k, v in peer.directory['aliases'].items()]}")

    # ids = list_identities()
    # # i = input(f"Choose an identity to open (write its index): {ids} ")
    # i = 0
    # dbg(GRE, f"load:\n\n\n\n")
    #
    # identity = fetch_id(ids[int(i)])
    # dbg(YEL, identity.directory)
    # dbg(BLU, f"{identity.follow(util.fromhex('da5066b203a02b2c1c200f9d9e6fa096058bfa01d0aef146d3856388964df56d'), 'Kaci')}")
    # # TODO add app
    # identity.add_app("test")
    # dbg(YEL, identity.directory)
    # sess = identity.open_session(identity.directory['aliases']['Kaci'])
    # sess.send(bipf.dumps("Hello"))
    """
    rd = identity.get_root_directory()
    ad = rd['apps']
    chess_games = ad['chess']
    ui = ...
    identity.launch_app(chess_games, ui)  # enter the app

    # print the different sessions (subfeeds) available
    # Example: a chat, a chess game, ...
    with_ = input(rd['alias'])

    session = identity.open_session(with_)
    # session.register(upcall_function)
    while True:
        msg = ui.input("> ")
        if msg == 'quit':
            identity.sync()
            break
        else:
            session.send(msg)
    """

    # erase_all()
    # # dbg(BLU, list_identities())
    # # start.set_in_feed(1, 'hello', 'dasdibvsdbfi')
    # peer = generate_id("Charlie")
    # peer.follow(util.fromhex("5920e93bd6ebbaa57a3a571d3bc1eeb850f4948fde07e08bcd25ce49820978aa"), "Carla")
    # dbg(GRE, peer.directory)
    # # start.write_bipf(peer, {'set': {'Chark': peer.me}}, peer.me)
    # # start.read_bipf(peer.repo, peer.me)
    #
    # peer._node.ks.dump(start.DATA_FOLDER + "Charlie" + "/_backed/" + util.hex(peer._node.me))
    # peer._node.ks.load(start.DATA_FOLDER + "Charlie" + "/_backed/" + util.hex(peer._node.me))

    """
    # nd = load_identity("Charlie")
    if sys.argv[1] == 'C':
        my_name = "Charlie"
        friend_name = "David"
        clean()
        local_peer = generate_id(my_name)
        remote_peer = generate_id(friend_name)

        friend = remote_peer.me
        follow(local_peer, remote_peer.me, friend_name)
        follow(remote_peer, local_peer.me, my_name)
        close(remote_peer, friend_name)
    else:
        my_name = "David"
        friend_name = "Charlie"
        local_peer = load_identity(my_name)
        dbg(GRE, f"friend = {list(list_trusted(my_name).keys())[1]}...")
        friend = util.fromhex(list(list_trusted(my_name).keys())[1])

    me = util.hex(local_peer.me)

    # bob = util.fromhex(list(list_trusted('Charlie').keys())[1])

    dbg(BLU, f"{util.hex(local_peer.me)} and {friend}")
    sess = {start_session(local_peer, local_peer.me, friend, None, 15)}
                         # lambda m: print(f"Received: {m}"), 5)
    # send_blob(sess, bytes(1000))
    # dbg(YEL, f"Blob done")
    # for i in range(105):
    #     send_log(sess, bytes(str(i), 'utf-8'))
    dbg(YEL, f"Log done")
    while True:
        try:
            cmd = input("> ")
        except (EOFError, KeyboardInterrupt):
            close(local_peer, my_name)
            print("Exiting")
            exit(0)
        if cmd == 'q':
            break
        if cmd.startswith('add'):
            key = cmd.split(' ')[1]
            follow(local_peer, key, cmd.split(' ')[2])
            sess.add(start_session(local_peer, local_peer.me, util.fromhex(key), None, 5))
        if cmd.startswith('r'):
            request_latest(local_peer, friend)
        if cmd.startswith('m'):
            make_child_log(local_peer, list(sess)[0])

        for s in sess:
            send(s, cmd)
    close(local_peer, my_name)
    pass
"""

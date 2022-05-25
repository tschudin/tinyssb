# tinyssb/api.py
import json
import os
import bipf

from tinyssb.dbg import *
from tinyssb import io, keystore, node, packet
from tinyssb import repository, util, identity

__all__ = [
    'erase_all',
    'list_identities',
    'generate_id',
    'load_identity'
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
    return os.listdir(util.DATA_FOLDER)

def generate_id(peer_name):
    """
    Create new peer (delete data if existing).
    Stores the data on the file system, make generic log, create default sub-feeds and
    add udp_multicast as interface and start it (listen/read loops).
    Only trusted peer is self
    :param peer_name: string
    :return: an instance of Node
    """
    pfx = util.DATA_FOLDER + peer_name
    ks = keystore.Keystore()
    pk = ks.new(peer_name)

    os.system(f"mkdir -p {pfx}/_blob")
    os.system(f"mkdir -p {pfx}/_logs")
    os.system(f"mkdir -p {pfx}/_backed")
    with open(f"{pfx}/_backed/config.json", "w") as f:
        f.write(util.json_pp({'name': peer_name,
                              'rootFeedID': util.hex(pk)}))

    repo = repository.REPO(pfx, lambda feed_id, msg, sig: ks.verify(feed_id, msg, sig))
    repo.mk_generic_log(pk, packet.PKTTYPE_plain48,
                        b'log entry 1', lambda msg: ks.sign(pk, msg))
    root = __start_node(repo, ks, pk, [])

    default = {}
    for n in ['aliases', 'public', 'apps']:
        fid = root.ks.new(n)
        name = bipf.dumps(n)
        name += bytes(16 - len(name))
        root.repo.mk_child_log(root.me, root.ks.get_signFct(root.me), fid,
                               root.ks.get_signFct(fid), name)
        default[n] = fid
    return identity.Identity(root, peer_name, default)

def load_identity(peer_name):
    """
    Launch a peer whose data is stored locally
    :param peer_name: the name of the folder
    :return: instance of node
    """
    pfx = util.DATA_FOLDER + peer_name
    with open(pfx + '/_backed/config.json') as f:
        cfg = json.load(f)
    me = util.fromhex(cfg['rootFeedID'])
    ks = keystore.Keystore()
    ks.load(pfx + '/_backed/' + cfg['rootFeedID'])

    repo = repository.REPO(pfx, lambda feed_id, sig, msg: ks.verify(feed_id, sig, msg))
    root = __start_node(repo, ks, me, [])
    log = root.repo.get_log(me)
    default = {}
    for i in range(len(log) + 1):
        pkt = log[i]
        if pkt.typ[0] == packet.PKTTYPE_mkchild:
            fid = pkt.payload[:32]
            log_name = bipf.loads(pkt.payload[32:])
            default[log_name] = fid
    return identity.Identity(root, peer_name, default)

def __start_node(repo, ks, me, peer_list):
    faces = [io.UDP_MULTICAST(('224.1.1.1', 5000))]
    nd = node.NODE(faces, ks, repo, me, peer_list)
    nd.start()
    return nd

if __name__ == "__main__":
    # for i in range(10):
    #     dbg(YEL, util.hex(generate_id("C" + str(i)).nd.me))
    dbg(GRE, f"Exc: {locals()['__builtins__']}")
    bin_key = util.fromhex('da5066b203a02b2c1c200f9d9e6fa096058bfa01d0aef146d3856388964df56d')
    bin_key2 = util.fromhex('ca5066b203a02b2c1c200f9d9e6fb096058bfa01d0aef146d3856388964df56d')
    bin_key3 = util.fromhex('5920e93bd6ebbaa57a3a571d3bc1eeb850f4948fde07e08bcd25ce49820978aa')
    # erase_all()
    # peer = generate_id("Charlie")
    peer = load_identity("Charlie")
    dbg(BLU, f"HERE: {peer.launch_app('chess')}")
    app = peer.open_session(bin_key)
    app.create_inst(bin_key3, bin_key, "Hello World")
    dbg(GRE, f"INST: {app.instances}")

    # peer.follow(util.fromhex('da5066b203a02b2c1c200f9d9e6fa096058bfa01d0aef146d3856388964df56d'), "Kaci")

    # dbg(BLU, f"{peer.directory['aliases']}")
    # peer.follow(util.fromhex('da5066b203a02b2c1c200f9d9e6fb096058bfa01d0aef146d3856388964df56d'), "Kaci")
    # peer.follow(util.fromhex('da5066b203a02b2cabc00f9d9e6fb096058bfa01d0aef146d3856388964df56d'), "Peter")
    # dbg(GRE, util.hex(peer.nd.peers[0]))
    # peer.unfollow(util.fromhex('da5066b203a02b2c1c200f9d9e6fb096058bfa01d0aef146d3856388964df56d'))
    #
    # appID = util.fromhex('ca5066b203a02b2c1c200f9d9e6fb096058bfa01d0aef146d3856388964df56d')
    # appID2 = util.fromhex('da5066b203a02b2c1c200f9d9e6fb096058bfa01d0aef146d3856388964df56d')
    # appID3 = util.fromhex('da5066b203a02b2c1c2012345e6fb096058bfa01d0aef146d3856388964df56d')
    #
    # dbg(BLU, f"{peer.directory['apps']}")
    #
    # # if not peer.has_app('chess'):
    # dbg(MAG, f"{peer.add_app('chess', appID)}")
    # dbg(MAG, f"{peer.add_app('tictactoe', appID3)}")
    # # if not peer.has_app('chat'):
    # dbg(MAG, f"{peer.add_app('chat', appID2)}")
    # # dbg(MAG, f"{peer.launch_app('chat')}")
    # # dbg(MAG, f"Delete: {peer.delete_app('chess1', appID)}")
    # dbg(GRE, f"{peer.directory['apps']}")
    # dbg(MAG, f"Delete: {peer.delete_app('chess', appID2)}")
    # dbg(GRE, f"{peer.directory['apps']}")
    # dbg(MAG, f"Delete: {peer.delete_app('tetris', appID)}")
    # dbg(GRE, f"{peer.directory['apps']}")
    # dbg(MAG, f"Delete: {peer.delete_app('chat', appID2)}")
    # # peer.request_latest()
    #
    # dbg(GRE, f"{peer.directory['apps']}")
    # exit(0)

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
    # peer.nd.ks.dump(start.DATA_FOLDER + "Charlie" + "/_backed/" + util.hex(peer.nd.me))
    # peer.nd.ks.load(start.DATA_FOLDER + "Charlie" + "/_backed/" + util.hex(peer.nd.me))

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
    
    1e032749b2414f9a424772e78d7cbe1fef1fea3464188e907c29fcf31eed52e1
    747da564ff00bf71684bf58775212248c354757b43d2fd5db52dcbc292537c04
    f23df21ca47b3666467222b1037af24162f231f5bb3559822336510af4fae8ed
    b1b64e45bc892ebbe95e0a355a197d967f8389f0426f0056029b375e2e3daf1b
    
    e523a5d864aba515518b711d3bfff3b9052a54d69c82d91d7eb31aa50f0ead70
    0bff3d95af22c60bd817e772fb7fcdcf1d9f9e736e676cc8bc1db21d3bb20f7b
    910530b3d475078bb8884f15f1c90f5dff559c7ea321f53ceb32f7f2504829ab
    6a7599019df4b5bf09781b6a3653946c278a5cdc236ea60d917ede9eedcf714d
    0df3c2a26ce89da05e524212b3202aef8ff07ad5912ca5ecf9920236046c89d1
    bd89ed16cf6802b9eb3346f1cf4dc519453c3db6f59e0d1c21cdd06811691db1
"""

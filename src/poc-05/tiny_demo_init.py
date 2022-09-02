import bipf
import tinyssb as tiny
from demo_app import *
from tinyssb import util
from tinyssb.dbg import *

# randomly chosen ID for my app
APP_ID = util.fromhex("6a7599019df4b5bf09781b6a3653946c278a5cdc236ea60d917ede9ee3cf714d")

def start_peer(name):
    """
    Start a peer that already exists on the local file system
    :param name: the name of the peer
    :return:
    """
    peer = tiny.load_identity(name)

    app = peer.resume_app("chat")
    app.set_callback(lambda msg, from_, pkt, log: callback(peer, name, msg, from_, pkt, log))
    app.resume_inst('0')  # '0' is the default key for the first app
    return peer, app

def callback(peer, name, msg, from_, packet, log):
    """
    Define a callback for managing incoming data
    :param peer: personal instance of Identity
    :param name: my name (string)
    :param msg: the message received
    :param from_: the fid of the "public" feed of the person that sent the message
    :param packet: the PACKET object, giving access to fid, typ, sequence number, etc.
    :param log: the LOG object, giving access to the history of the log entries
    """
    try:
        msg = bipf.loads(msg)
    except KeyError: msg = str(msg)
    except TypeError: msg = str(msg)
    dbg(RED, f"{name} received \"{msg}\" from {peer.get_contact_alias(from_)} (#{packet.seq})")

def initialise():
    """
    Initialise 3 peers
    :return:
    """
    tiny.erase_all()
    peers = {}
    # For each peer, generate the default logs, create an app with one instance
    for n in ["Alice", "Bob", "Charlie"]:
        peers[n] = tiny.generate_id(n)
        app = peers[n].define_app("chat", APP_ID)
        assert app.create_inst("Chat (Alice, Bob and Charlie)") == '0'

    # Add mutual trust (follow) for the peers and add them to the chat group
    for n in ["Alice", "Bob", "Charlie"]:
        for friend in ["Alice", "Bob", "Charlie"]:
            if friend != n:
                peers[n].follow(peers[friend].public, friend)
                game_remote_log = peers[friend].resume_app("chat").instances['0']['l']
                peers[n].resume_app("chat").add_remote('0', game_remote_log, peers[friend].public)

    dbg(YEL, f"\n{util.json_pp(peers['Alice'].manager.node.logs)}")

if __name__ == "__main__":
    if sys.argv[1] in ["Alice", "Bob", "Charlie"]:
        name = sys.argv[1]
        identity, app = start_peer(name)
        demo = DEMO(identity, app)
        demo.demo_loop(name)
        # demo_loop(name, app)

    elif sys.argv[1] == "init":
        initialise()

# eof




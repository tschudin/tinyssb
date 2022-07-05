import bipf
import tinyssb as tiny
from tinyssb import util
from tinyssb.dbg import *

APP_ID = util.fromhex("6a7599019df4b5bf09781b6a3653946c278a5cdc236ea60d917ede9ee3cf714d")

def start_peer(name):
    peer = tiny.load_identity(name)

    app = peer.resume_app("chess")
    app.set_callback(lambda msg: callback(msg, name))
    app.resume_inst('0')  # '0' is the default key for the first app

    while True:
        # inp = input(f"Look at that!")
        dbg(YEL, f"{name} sending inp")
        app.send(bipf.dumps("inp"))
        time.sleep(1)
        if name == "Charlie":
            time.sleep(10)

def callback(msg, name):
    try:
        msg = bipf.loads(msg)
    except KeyError: msg = str(msg)
    dbg(RED, f"{name} received {msg}")

def initialise():
    tiny.erase_all()
    peers = {}
    for n in ["Alice", "Bob", "Charlie"]:
        peers[n] = tiny.generate_id(n)
        app = peers[n].define_app("chess", APP_ID)
        assert app.create_inst() == '0'

    for n in ["Alice", "Bob", "Charlie"]:
        for friend in ["Alice", "Bob", "Charlie"]:
            if friend != n:
                peers[n].follow(peers[friend].public, friend)
                game_remote_log = peers[friend].resume_app("chess").instances['0']['l']
                peers[n].resume_app("chess").add_remote('0', game_remote_log, peers[friend].public)

    dbg(YEL, f"\n{util.json_pp(peers['Alice'].manager.node.logs)}")

if __name__ == "__main__":
    if sys.argv[1] in ["Alice", "Bob", "Charlie"]:
        arg = sys.argv[1]
        start_peer(arg)

    elif sys.argv[1] == "init":
        initialise()

# eof

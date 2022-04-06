#

# tinyssb/util.py

import base64
import sys

if sys.implementation.name == 'micropython':
    import binascii
    fromhex = binascii.unhexlify
    hex = lambda b: binascii.hexlify(b).decode()
else:
    fromhex = lambda h: bytes.fromhex(h)
    hex = lambda b: b.hex()

b64 = lambda b: base64.b64encode(b).decode()


#!/usr/bin/env python3

# rumpelstiltskin-demo.py
# March 2022, <christian.tschudin@unibas.ch>

# For little knows my royal dame / that Rumpelstiltskin is my name!

# config --------------------------------------------------------------------

import os
import sys

print("Demo of 'Rumpelstiltskin Talk' (sending data without sending it)")
print(f"usage: {sys.argv[0]} [-symmetric]")

try:
    import nacl.signing
except:
    sys.argv[1:] = ['-symmetric']  # force symmetric if no ed25519 support

if ''.join(sys.argv[1:]) == '-symmetric':
    import hmac
    pk = os.urandom(16)                      # shared secret
    mksign = lambda m: hmac.new(pk, m, digestmod='md5').digest()
    verify = lambda k,m,s: hmac.compare_digest(s,
                                  hmac.new(k, m, digestmod='md5').digest())
    print("  signature algorithm is HMAC-MD5")
else: # for ed25519
    sk = nacl.signing.SigningKey.generate()  # key pair
    pk = sk.verify_key._key
    mksign = lambda m: sk.sign(m)[:64]
    def verify(pk,m,s):
        try:
            nacl.signing.VerifyKey(pk).verify(m,s)
        except nacl.exceptions.BadSignatureError:
            return False
        return True
    print("  signature algorithm is ed25519")

# demo ----------------------------------------------------------------------

hin = os.urandom(42)         # hidden name is shared secret, recv must know it
                             # (this is the Rumpelstiltskin Name)

msg = os.urandom(1)          # content (1 Byte), random for demo purposes
pkt = mksign(hin + msg)      # pkt creation: signature IS the packet

print(f"  message to transfer: 0x{msg.hex()}")
print(f"  the signature IS the packet: 0x{pkt.hex()} ({len(pkt)} bytes)")

for i in range(256):         # decoding: exhaustive search
    b = bytes([i])           # candidate content
    if verify(pk, hin + b, pkt): # does data fit the received pkt/signature?
        print(f"  reconstructed message: 0x{b.hex()}")
        break
else:
    print("  no decoding found :-(")

# eof

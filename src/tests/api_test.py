#tests/api_test.py
# 2022-05-25 <et.mettaz@unibas.ch>
import time
import unittest

import tinyssb as tiny
from tinyssb.identity import Identity

class ApiTestCase(unittest.TestCase):

    def test_generate_id(self):
        tiny.erase_all()
        peer = tiny.generate_id("Charlie")
        self.assertIsInstance(peer, Identity)

    def test_list_identities(self):
        tiny.erase_all()
        expected = ["Charlie", "Marija", "Paula"]
        for n in expected:
            tiny.generate_id(n)
        self.assertListEqual(expected, sorted(tiny.list_identities()))

    def test_load_identity(self):
        tiny.erase_all()
        peer1 = tiny.generate_id("Charlie")
        time.sleep(0.1)
        peer2 = tiny.load_identity("Charlie")
        self.assertIsInstance(peer2, Identity)
        self.assertEqual(peer1.name, peer2.name)
        self.assertEqual(peer1.manager.node.me, peer2.manager.node.me)

if __name__ == '__main__':
    unittest.main()

# eof

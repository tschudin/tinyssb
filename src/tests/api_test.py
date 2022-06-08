#tests/api_test.py
# 2022-05-25 <et.mettaz@unibas.ch>
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
        peer2 = tiny.load_identity("Charlie")
        self.assertIsInstance(peer2, Identity)
        self.assertEqual(peer1.name, peer2.name)
        self.assertEqual(peer1.nd.me, peer2.nd.me)

if __name__ == '__main__':
    unittest.main()

# eof

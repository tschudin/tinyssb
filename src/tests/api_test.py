#tests/api_test.py
# 2022-05-25 <et.mettaz@unibas.ch>
import unittest

import api
from tinyssb.identity import Identity

class ApiTestCase(unittest.TestCase):

    def test_generate_id(self):
        api.erase_all()
        peer = api.generate_id("Charlie")
        self.assertIsInstance(peer, Identity)

    def test_list_identities(self):
        api.erase_all()
        expected = ["Charlie", "Marija", "Paula"]
        for n in expected:
            api.generate_id(n)
        self.assertListEqual(expected, sorted(api.list_identities()))

    def test_load_identity(self):
        api.erase_all()
        peer1 = api.generate_id("Charlie")
        peer2 = api.load_identity("Charlie")
        self.assertIsInstance(peer2, Identity)
        self.assertEqual(peer1.name, peer2.name)
        self.assertEqual(peer1.nd.me, peer2.nd.me)

if __name__ == '__main__':
    unittest.main()

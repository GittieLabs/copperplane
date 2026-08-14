import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))


class TestToolRegistryStub(unittest.TestCase):
    """CTX-204.1 Phase 3/4 stub -- real tests land with the tool_registry module itself."""

    def test_000_placeholder(self):
        self.assertTrue(True)


if __name__ == '__main__':
    unittest.main()

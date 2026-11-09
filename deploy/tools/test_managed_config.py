import importlib.util
from pathlib import Path
import unittest


SPEC = importlib.util.spec_from_file_location("managed_config", Path(__file__).with_name("managed_config.py"))
CONFIG = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CONFIG)


class ManagedConfigTests(unittest.TestCase):
    def setUp(self):
        self.base = b"server { listen 80; }\n# preserved whitespace  \n"
        self.fragment = CONFIG.BEGIN + b"\nserver { listen 443; }\n" + CONFIG.END + b"\n"

    def test_append_and_remove_preserve_every_other_byte(self):
        updated = CONFIG.replace(self.base, None, self.fragment)
        self.assertEqual(updated, self.base + self.fragment)
        self.assertEqual(CONFIG.replace(updated, self.fragment, None), self.base)

    def test_only_recorded_delta_is_allowed(self):
        self.assertTrue(CONFIG.owned_delta_allowed(self.base + self.fragment, self.base, self.fragment))
        self.assertFalse(CONFIG.owned_delta_allowed(b"# foreign\n" + self.base + self.fragment, self.base, self.fragment))
        self.assertFalse(CONFIG.owned_delta_allowed(self.base + self.fragment, self.base, None))

    def test_unknown_duplicate_or_truncated_blocks_fail(self):
        for bad in (self.fragment + self.fragment, self.fragment[:-1], b"# outside\n" + self.fragment):
            with self.subTest(fragment=bad), self.assertRaises(CONFIG.ManagedConfigError):
                CONFIG.validate_fragment(bad)
        with self.assertRaises(CONFIG.ManagedConfigError):
            CONFIG.replace(self.base + self.fragment, None, self.fragment)


if __name__ == "__main__":
    unittest.main()

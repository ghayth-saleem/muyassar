"""FallbackProvider with stub providers: no network."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from muyassar.providers import FallbackProvider, ModelRefused  # noqa: E402


class Stub:
    def __init__(self, name, error=None):
        self.name, self.error, self.calls = name, error, 0

    def ask(self, system, user, max_tokens=16000, schema=None):
        self.calls += 1
        if self.error:
            raise self.error
        return f"from {self.name}"


class Fallback(unittest.TestCase):
    def test_primary_answers(self):
        main, backup = Stub("claude"), Stub("gemini")
        p = FallbackProvider(main, backup)
        self.assertEqual(p.ask("s", "u"), "from claude")
        self.assertEqual((p.name, backup.calls), ("claude", 0))

    def test_failure_moves_to_backup_and_the_name_follows(self):
        p = FallbackProvider(Stub("claude", ConnectionError()), Stub("gemini"))
        self.assertEqual(p.ask("s", "u"), "from gemini")
        self.assertEqual(p.name, "gemini")

    def test_name_returns_when_primary_recovers(self):
        main = Stub("claude", ConnectionError())
        p = FallbackProvider(main, Stub("gemini"))
        p.ask("s", "u")
        main.error = None
        p.ask("s", "u")
        self.assertEqual(p.name, "claude")

    def test_refusal_does_not_fall_through(self):
        backup = Stub("gemini")
        p = FallbackProvider(Stub("claude", ModelRefused("no")), backup)
        with self.assertRaises(ModelRefused):
            p.ask("s", "u")
        self.assertEqual(backup.calls, 0)


if __name__ == "__main__":
    unittest.main()

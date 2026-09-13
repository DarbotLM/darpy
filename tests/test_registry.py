import contextlib
import io
import json
import unittest

from darpy.cli import main
from darpy.registry import Capability, CapabilityRegistry, CapabilityState, capabilities, default_registry


class RegistryTests(unittest.TestCase):
    def test_scoped_and_planned_entries_explain_limitations(self):
        for item in capabilities():
            if item.state in (CapabilityState.SCOPED, CapabilityState.PLANNED):
                self.assertTrue(item.limitations)
        registry = default_registry()
        self.assertEqual(registry.get("numpy-parity").state, CapabilityState.PLANNED)
        self.assertEqual(registry.get("distributed-swarm").state, CapabilityState.PLANNED)
        self.assertEqual(registry.get("runtime").state, CapabilityState.NATIVE)

    def test_registration_never_silently_replaces(self):
        registry = CapabilityRegistry()
        item = Capability("example", CapabilityState.NATIVE, "Example")
        registry.register(item)
        with self.assertRaises(ValueError):
            registry.register(item)
        self.assertIs(registry.get("example"), item)

    def test_fresh_registry_and_stable_filter(self):
        first, second = default_registry(), default_registry()
        first.register(Capability("custom", CapabilityState.NATIVE, "Custom"))
        with self.assertRaises(KeyError):
            second.get("custom")
        selected = first.list(state=CapabilityState.SCOPED)
        self.assertTrue(all(item.state == CapabilityState.SCOPED for item in selected))
        self.assertEqual([item.name for item in selected], sorted(item.name for item in selected))

    def test_registry_rejects_unsupported_scope_claims(self):
        with self.assertRaises(ValueError):
            Capability("x", CapabilityState.SCOPED, "Missing limitation")
        with self.assertRaises(TypeError):
            Capability("x", "native", "Wrong state type")

    def test_cli_commands_emit_parseable_truthful_json(self):
        for command in [["doctor"], ["capabilities"], ["schema", "Task"]]:
            with self.subTest(command=command):
                output = io.StringIO()
                with contextlib.redirect_stdout(output):
                    self.assertEqual(main(command), 0)
                data = json.loads(output.getvalue())
                if command[0] == "doctor":
                    self.assertFalse(data["full_numpy_parity"])
                    self.assertEqual(data["core_external_dependencies"], [])
                if command[0] == "schema":
                    self.assertEqual(data["title"], "Task")


if __name__ == "__main__":
    unittest.main()

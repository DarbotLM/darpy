import json
import unittest

from darpy.schemas import RunBudget, RunResult, Task, schema, strict_json_loads


class SchemaTests(unittest.TestCase):
    def test_contract_round_trips(self):
        contracts = [
            Task("hi", "session", payload_json='{"n": 3}', request_id="r1"),
            RunBudget(2.0, 500, 200),
            RunResult("r1", "session", "acp", "ok", 0.25),
        ]
        for contract in contracts:
            with self.subTest(contract=type(contract).__name__):
                self.assertEqual(type(contract).from_json(contract.to_json()), contract)

    def test_strict_json_rejects_duplicate_and_nonfinite_numbers(self):
        for value in ['{"x": 1, "x": 2}', '{"x": {"a": 1, "a": 2}}', "NaN", "Infinity", "1e1000"]:
            with self.subTest(value=value), self.assertRaises(ValueError):
                strict_json_loads(value)

    def test_payload_must_be_json(self):
        for value in ["{", '{"value": NaN}', "undefined", ""]:
            with self.subTest(value=value), self.assertRaises(ValueError):
                Task("hi", "session", payload_json=value)

    def test_valid_json_scalars_allowed(self):
        for value in ["null", "false", "0", "[]", '"text"']:
            self.assertEqual(Task("", "s", payload_json=value).payload_json, value)

    def test_unknown_fields_and_schema_versions_rejected(self):
        data = Task("hi", "s").to_dict()
        for change in [{"new_field": "x"}, {"schema_version": "2.0"}]:
            with self.subTest(change=change), self.assertRaises(ValueError):
                Task.from_dict({**data, **change})
        del data["schema_version"]
        with self.assertRaises(ValueError):
            Task.from_dict(data)

    def test_task_validation(self):
        for kwargs in [
            {"prompt": 1},
            {"session_id": " "},
            {"protocol": "http"},
            {"request_id": ""},
            {"cwd": ""},
            {"payload_json": {}},
        ]:
            with self.subTest(kwargs=kwargs), self.assertRaises((TypeError, ValueError)):
                Task(**{"prompt": "hi", "session_id": "s", **kwargs})

    def test_budget_rejects_invalid_numeric_types_and_ranges(self):
        for value in [True, 0, -1, float("nan"), float("inf"), "1", 10**1000]:
            with self.subTest(value=str(value)[:20]), self.assertRaises((TypeError, ValueError)):
                RunBudget(timeout_seconds=value)
        for name in ("max_input_chars", "max_output_chars"):
            for value in (True, 1.5, 0, -1):
                with self.subTest(name=name, value=value), self.assertRaises((TypeError, ValueError)):
                    RunBudget(**{name: value})

    def test_results_cannot_contain_invalid_elapsed_time(self):
        for value in [-1, float("nan"), True]:
            with self.assertRaises((TypeError, ValueError)):
                RunResult("r", "s", "local", "x", value)

    def test_schema_exports_are_fresh_and_versioned(self):
        for name in ("Task", "RunBudget", "RunResult"):
            result = schema(name)
            self.assertEqual(result["$schema"], "https://json-schema.org/draft/2020-12/schema")
            self.assertFalse(result["additionalProperties"])
            self.assertIn("schema_version", result["required"])
            json.dumps(result, allow_nan=False)
        result = schema("Task")
        result["properties"]["prompt"]["type"] = "number"
        self.assertEqual(schema("Task")["properties"]["prompt"]["type"], "string")
        with self.assertRaises(ValueError):
            schema("Unknown")


if __name__ == "__main__":
    unittest.main()

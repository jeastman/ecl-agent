from __future__ import annotations

import unittest

from packages.config.local_agent_config.loader import load_runtime_config
from services.subagent_runtime.local_agent_subagent_runtime.model_routing import (
    RuntimeModelResolver,
)


class RuntimeModelResolverTests(unittest.TestCase):
    def test_role_override_wins_when_present(self) -> None:
        config = load_runtime_config("docs/architecture/runtime.example.toml")
        config.subagent_model_overrides["coder"] = config.subagent_model_overrides["researcher"]

        route = RuntimeModelResolver(config).resolve_subagent("coder", "coder")

        self.assertEqual(route.provider, "openai")
        self.assertEqual(route.model, "gpt-5-mini")
        self.assertEqual(route.profile_name, "coder")
        self.assertEqual(route.source, "subagent_override")

    def test_declared_model_profile_uses_matching_config(self) -> None:
        config = load_runtime_config("docs/architecture/runtime.example.toml")

        route = RuntimeModelResolver(config).resolve_subagent("librarian", "researcher")

        self.assertEqual(route.provider, "openai")
        self.assertEqual(route.model, "gpt-5-mini")
        self.assertEqual(route.profile_name, "researcher")
        self.assertEqual(route.source, "role_profile")

    def test_missing_override_or_profile_falls_back_to_primary_model(self) -> None:
        config = load_runtime_config("docs/architecture/runtime.example.toml")

        route = RuntimeModelResolver(config).resolve_subagent("verifier", "verifier")

        self.assertEqual(route.provider, config.primary_model.provider)
        self.assertEqual(route.model, config.primary_model.model)
        self.assertEqual(route.profile_name, "primary")
        self.assertEqual(route.source, "primary_model")


if __name__ == "__main__":
    unittest.main()

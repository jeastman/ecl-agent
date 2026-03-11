from __future__ import annotations

from apps.runtime.local_agent_runtime.subagents import ResolvedModelRoute
from packages.config.local_agent_config.models import RuntimeConfig


class RuntimeModelResolver:
    def __init__(self, config: RuntimeConfig) -> None:
        self._config = config

    def resolve_primary(self) -> ResolvedModelRoute:
        return ResolvedModelRoute(
            provider=self._config.primary_model.provider,
            model=self._config.primary_model.model,
            profile_name="primary",
            source="primary_model",
        )

    def resolve_subagent(self, role_id: str, model_profile: str | None) -> ResolvedModelRoute:
        if role_id in self._config.subagent_model_overrides:
            override = self._config.subagent_model_overrides[role_id]
            return ResolvedModelRoute(
                provider=override.provider,
                model=override.model,
                profile_name=role_id,
                source="subagent_override",
            )

        profile_name = (model_profile or "").strip()
        if profile_name and profile_name in self._config.subagent_model_overrides:
            profile = self._config.subagent_model_overrides[profile_name]
            return ResolvedModelRoute(
                provider=profile.provider,
                model=profile.model,
                profile_name=profile_name,
                source="role_profile",
            )

        primary = self.resolve_primary()
        return ResolvedModelRoute(
            provider=primary.provider,
            model=primary.model,
            profile_name=primary.profile_name,
            source=primary.source,
        )

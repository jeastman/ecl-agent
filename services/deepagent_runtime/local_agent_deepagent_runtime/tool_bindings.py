from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from langchain_core.tools import BaseTool, tool

from apps.runtime.local_agent_runtime.subagents import ResolvedToolBinding
from packages.protocol.local_agent_protocol.models import ArtifactReference
from services.artifact_service.local_agent_artifact_service.store import ArtifactStore
from services.memory_service.local_agent_memory_service.memory_store import MemoryStore
from services.policy_service.local_agent_policy_service.policy_models import OperationContext
from services.sandbox_service.local_agent_sandbox_service.sandbox import ExecutionSandbox

EventCallback = Callable[[str, dict[str, Any]], None]

_READ_CAPABILITIES = {"read_file", "filesystem", "files.read"}
_WRITE_CAPABILITIES = {"write_file", "filesystem", "files.write"}
_LIST_CAPABILITIES = {"list_files", "filesystem", "files.list", "files.read", "read_file"}
_EXECUTE_CAPABILITIES = {"execute_command", "commands", "sandbox.execute"}
_MEMORY_CAPABILITIES = {"memory_lookup", "memory", "memory.read"}
_PLAN_CAPABILITIES = {"plan_update", "planning", "plan.write"}
_ARTIFACT_CAPABILITIES = {"artifact_inspect", "artifacts", "artifacts.read"}
_SKILL_INSTALL_CAPABILITIES = {"skill_installer", "skills.install"}


class FilesystemScopeError(PermissionError):
    pass


@dataclass(slots=True)
class SandboxToolBindings:
    sandbox: ExecutionSandbox
    task_id: str
    run_id: str
    artifact_store: ArtifactStore
    memory_store: MemoryStore | None = None
    on_event: EventCallback | None = None
    allowed_capabilities: list[str] | None = None
    governed_operation: Callable[[OperationContext], None] | None = None
    skill_install_handler: Callable[..., dict[str, Any]] | None = None
    _written_paths: list[str] | None = None

    def read_file(self, path: str) -> str:
        self._ensure_allowed("read_file", _READ_CAPABILITIES)
        normalized_path = self.sandbox.normalize_path(path)
        self._govern(
            OperationContext(
                task_id=self.task_id,
                run_id=self.run_id,
                operation_type="file.read",
                path_scope=normalized_path,
            )
        )
        self._emit(
            "tool.called",
            {
                "tool": "read_file",
                "arguments": {"path": normalized_path},
                "path": normalized_path,
            },
        )
        return self.sandbox.read_text(normalized_path)

    def write_file(self, path: str, content: str) -> str:
        self._ensure_allowed("write_file", _WRITE_CAPABILITIES)
        normalized_path = self.sandbox.normalize_path(path)
        self._govern(
            OperationContext(
                task_id=self.task_id,
                run_id=self.run_id,
                operation_type="file.write",
                path_scope=normalized_path,
            )
        )
        self._emit(
            "tool.called",
            {
                "tool": "write_file",
                "arguments": {"path": normalized_path},
                "path": normalized_path,
                "bytes_written": len(content.encode("utf-8")),
            },
        )
        self.sandbox.write_text(normalized_path, content)
        if self._written_paths is None:
            self._written_paths = []
        if normalized_path not in self._written_paths:
            self._written_paths.append(normalized_path)
        return normalized_path

    def list_files(self, root: str) -> list[str]:
        self._ensure_allowed("list_files", _LIST_CAPABILITIES)
        normalized_root = self.sandbox.normalize_path(root)
        self._govern(
            OperationContext(
                task_id=self.task_id,
                run_id=self.run_id,
                operation_type="file.list",
                path_scope=normalized_root,
            )
        )
        self._emit(
            "tool.called",
            {
                "tool": "list_files",
                "arguments": {"root": normalized_root},
                "path": normalized_root,
            },
        )
        return self.sandbox.list_files(normalized_root)

    def execute_command(self, command: list[str], cwd: str | None = None) -> dict[str, Any]:
        self._ensure_allowed("execute_command", _EXECUTE_CAPABILITIES)
        normalized_cwd = self.sandbox.normalize_path(cwd or "/")
        self._govern(
            OperationContext(
                task_id=self.task_id,
                run_id=self.run_id,
                operation_type="command.execute",
                path_scope=normalized_cwd,
                command_class=_classify_command(command),
                metadata={"command": list(command)},
            )
        )
        self._emit(
            "tool.called",
            {
                "tool": "execute_command",
                "arguments": {"command": list(command), "cwd": normalized_cwd},
                "command": list(command),
                "cwd": normalized_cwd,
            },
        )
        result = self.sandbox.execute_command(command, normalized_cwd)
        return {
            "exit_code": result.exit_code,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "cwd": result.cwd,
        }

    def memory_lookup(
        self, namespace: str | None = None, scope: str | None = None
    ) -> list[dict[str, Any]]:
        self._ensure_allowed("memory_lookup", _MEMORY_CAPABILITIES)
        if self.memory_store is None:
            return []
        records = self.memory_store.list_memory(scope=scope, namespace=namespace)
        self._emit(
            "tool.called",
            {
                "tool": "memory_lookup",
                "arguments": {"namespace": namespace, "scope": scope},
                "count": len(records),
            },
        )
        return [record.to_dict() for record in records]

    def plan_update(self, summary: str, phase: str | None = None) -> dict[str, Any]:
        self._ensure_allowed("plan_update", _PLAN_CAPABILITIES)
        payload = {"summary": summary.strip()}
        if phase is not None and phase.strip():
            payload["phase"] = phase.strip()
        self._emit("plan.updated", payload)
        self._emit(
            "tool.called",
            {
                "tool": "plan_update",
                "arguments": payload,
            },
        )
        return payload

    def artifact_inspect(self) -> list[dict[str, Any]]:
        self._ensure_allowed("artifact_inspect", _ARTIFACT_CAPABILITIES)
        artifacts = self.artifact_store.list_artifacts(self.task_id, self.run_id)
        self._emit(
            "tool.called",
            {
                "tool": "artifact_inspect",
                "arguments": {"task_id": self.task_id, "run_id": self.run_id},
                "count": len(artifacts),
            },
        )
        return [self._artifact_payload(artifact) for artifact in artifacts]

    def skill_installer(
        self,
        source_path: str,
        target_scope: str,
        target_role: str | None,
        install_mode: str,
        reason: str,
    ) -> dict[str, Any]:
        self._ensure_allowed("skill_installer", _SKILL_INSTALL_CAPABILITIES)
        if self.skill_install_handler is None:
            raise ValueError("skill_installer is not configured for this runtime")
        self._emit(
            "tool.called",
            {
                "tool": "skill_installer",
                "arguments": {
                    "source_path": source_path,
                    "target_scope": target_scope,
                    "target_role": target_role,
                    "install_mode": install_mode,
                    "reason": reason,
                },
            },
        )
        return self.skill_install_handler(
            source_path=source_path,
            target_scope=target_scope,
            target_role=target_role,
            install_mode=install_mode,
            reason=reason,
        )

    def as_langchain_tools(
        self,
        resolved_bindings: tuple[ResolvedToolBinding, ...],
        *,
        memory_scopes: tuple[str, ...] = (),
        filesystem_scopes: tuple[str, ...] = (),
    ) -> list[BaseTool]:
        allowed_tool_ids = {binding.tool_id for binding in resolved_bindings}
        tools: list[BaseTool] = []

        if "read_files" in allowed_tool_ids:

            @tool
            def read_file(path: str) -> str:
                """Read a UTF-8 text file from a virtual sandbox path such as /README.md."""
                self._ensure_filesystem_scope(path, filesystem_scopes, operation="read_file")
                return self.read_file(path)

            @tool
            def list_files(root: str = "/") -> list[str]:
                """List governed files rooted at a virtual sandbox path such as / or /tmp."""
                self._ensure_filesystem_scope(root, filesystem_scopes, operation="list_files")
                return self.list_files(root)

            tools.extend([read_file, list_files])

        if "write_files" in allowed_tool_ids:

            @tool
            def write_file(path: str, content: str) -> str:
                """Write UTF-8 text content to a virtual sandbox path such as /artifacts/out.md."""
                self._ensure_filesystem_scope(path, filesystem_scopes, operation="write_file")
                return self.write_file(path, content)

            tools.append(write_file)

        if "execute_commands" in allowed_tool_ids:

            @tool
            def execute_command(command: list[str], cwd: str | None = None) -> dict[str, Any]:
                """Execute a command inside the virtual sandbox filesystem and return structured output."""
                self._ensure_filesystem_scope(
                    cwd or "/",
                    filesystem_scopes,
                    operation="execute_command",
                )
                return self.execute_command(command, cwd)

            tools.append(execute_command)

        if "memory_lookup" in allowed_tool_ids:

            @tool
            def memory_lookup(
                namespace: str | None = None, scope: str | None = None
            ) -> list[dict[str, Any]]:
                """Inspect runtime memory records for the allowed scope."""
                normalized_scope = scope if scope in set(memory_scopes) else None
                records = self.memory_lookup(namespace=namespace, scope=normalized_scope)
                if normalized_scope is None and memory_scopes:
                    return [
                        record
                        for record in records
                        if str(record.get("scope") or "") in set(memory_scopes)
                    ]
                return records

            tools.append(memory_lookup)

        if "plan_update" in allowed_tool_ids:

            @tool
            def plan_update(summary: str, phase: str | None = None) -> dict[str, Any]:
                """Emit a runtime-friendly plan update."""
                return self.plan_update(summary, phase)

            tools.append(plan_update)

        if "artifact_inspect" in allowed_tool_ids:

            @tool
            def artifact_inspect() -> list[dict[str, Any]]:
                """Inspect task artifacts and return metadata with previews when available."""
                return self.artifact_inspect()

            tools.append(artifact_inspect)

        if "skill_installer" in allowed_tool_ids:

            @tool("skill-installer")
            def skill_installer(
                source_path: str,
                target_scope: str,
                target_role: str | None = None,
                install_mode: str = "fail_if_exists",
                reason: str = "",
            ) -> dict[str, Any]:
                """Install a staged skill into a managed runtime skill scope."""
                self._ensure_filesystem_scope(
                    source_path,
                    filesystem_scopes or ("workspace",),
                    operation="skill_installer",
                )
                return self.skill_installer(
                    source_path,
                    target_scope,
                    target_role,
                    install_mode,
                    reason,
                )

            tools.append(skill_installer)

        return tools

    @property
    def written_paths(self) -> list[str]:
        return list(self._written_paths or [])

    def _artifact_payload(self, artifact: ArtifactReference) -> dict[str, Any]:
        payload = artifact.to_dict()
        sandbox_path = _artifact_to_sandbox_path(artifact)
        preview: str | None = None
        if self.sandbox.exists(sandbox_path):
            try:
                preview = self.sandbox.read_text(sandbox_path)[:500]
            except UnicodeDecodeError:
                preview = None
        payload["preview"] = preview
        payload["sandbox_path"] = sandbox_path
        return payload

    def _ensure_allowed(self, tool_name: str, aliases: set[str]) -> None:
        allowed_capabilities = {item.strip() for item in self.allowed_capabilities or [] if item}
        if not allowed_capabilities:
            return
        if allowed_capabilities.isdisjoint(aliases):
            raise PermissionError(f"{tool_name} is not allowed for this run")

    def _emit(self, event_type: str, payload: dict[str, Any]) -> None:
        if self.on_event is not None:
            self.on_event(event_type, payload)

    def _govern(self, context: OperationContext) -> None:
        if self.governed_operation is not None:
            self.governed_operation(context)

    def _ensure_filesystem_scope(
        self,
        sandbox_path: str,
        filesystem_scopes: tuple[str, ...],
        *,
        operation: str,
    ) -> None:
        allowed_scopes = {scope.strip() for scope in filesystem_scopes if scope.strip()}
        if not allowed_scopes:
            return
        normalized_path = self.sandbox.normalize_path(sandbox_path)
        scope = (
            "memory"
            if normalized_path == "/.memory" or normalized_path.startswith("/.memory/")
            else "workspace"
        )
        if scope not in allowed_scopes:
            allowed = ", ".join(sorted(allowed_scopes))
            raise FilesystemScopeError(
                f"{operation} denied for {normalized_path}: allowed filesystem scopes are {allowed}"
            )


def _artifact_to_sandbox_path(artifact: ArtifactReference) -> str:
    if artifact.persistence_class == "project":
        return artifact.logical_path
    if artifact.persistence_class == "ephemeral":
        return artifact.logical_path
    return artifact.logical_path or "/"


def _classify_command(command: list[str]) -> str:
    if not command:
        return "unknown"
    head = command[0].rsplit("/", 1)[-1]
    if head in {"curl", "wget", "nc", "telnet"}:
        return "network"
    if head in {"rm", "dd", "mkfs", "shutdown", "reboot"}:
        return "destructive"
    if head in {"ls", "find", "rg", "grep", "cat", "sed", "head", "tail", "wc", "pwd", "git"}:
        return "safe_read"
    if head in {"python", "python3"} and len(command) >= 2 and command[1] == "-c":
        return "safe_exec"
    return "safe_exec"

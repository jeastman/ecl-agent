from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Callable

from langchain_core.tools import BaseTool, tool
from pydantic import ValidationError

from apps.runtime.local_agent_runtime.subagents import ResolvedToolBinding
from packages.protocol.local_agent_protocol.models import ArtifactReference
from packages.protocol.local_agent_protocol.models import utc_now_timestamp
from packages.task_model.local_agent_task_model.ids import new_memory_id
from packages.task_model.local_agent_task_model.models import RecoverableToolRejection
from services.artifact_service.local_agent_artifact_service.store import ArtifactStore
from services.memory_service.local_agent_memory_service.memory_models import MemoryRecord
from services.memory_service.local_agent_memory_service.memory_store import MemoryStore
from services.policy_service.local_agent_policy_service.policy_models import OperationContext
from services.sandbox_service.local_agent_sandbox_service.sandbox import ExecutionSandbox
from services.web_service.local_agent_web_service.ports import WebFetchPort, WebSearchPort

EventCallback = Callable[[str, dict[str, Any]], None]

_READ_CAPABILITIES = {"read_file", "filesystem", "files.read"}
_WRITE_CAPABILITIES = {"write_file", "filesystem", "files.write"}
_LIST_CAPABILITIES = {"list_files", "filesystem", "files.list", "files.read", "read_file"}
_EXECUTE_CAPABILITIES = {"execute_command", "commands", "sandbox.execute"}
_MEMORY_CAPABILITIES = {"memory_lookup", "memory", "memory.read"}
_MEMORY_WRITE_CAPABILITIES = {"memory_write", "memory", "memory.write"}
_PLAN_CAPABILITIES = {"plan_update", "planning", "plan.write"}
_ARTIFACT_CAPABILITIES = {"artifact_inspect", "artifacts", "artifacts.read"}
_SKILL_INSTALL_CAPABILITIES = {"skill_installer", "skills.install"}
_USER_INPUT_CAPABILITIES = {"request_user_input", "user_input", "conversation"}
_WEB_FETCH_CAPABILITIES = {"web_fetch", "web.fetch", "web"}
_WEB_SEARCH_CAPABILITIES = {"web_search", "web.search", "web"}


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
    user_input_handler: Callable[..., None] | None = None
    web_fetch_port: WebFetchPort | None = None
    web_search_port: WebSearchPort | None = None
    _written_paths: list[str] | None = None

    def read_file(self, path: str) -> str:
        self._ensure_allowed("read_file", _READ_CAPABILITIES)
        try:
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
        except RecoverableToolRejection as exc:
            return self._handle_recoverable_rejection(
                "read_file",
                {"path": path},
                exc,
            )

    def write_file(self, path: str, content: str) -> str:
        self._ensure_allowed("write_file", _WRITE_CAPABILITIES)
        try:
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
        except RecoverableToolRejection as exc:
            return self._handle_recoverable_rejection(
                "write_file",
                {"path": path},
                exc,
            )

    def list_files(self, root: str) -> list[str]:
        self._ensure_allowed("list_files", _LIST_CAPABILITIES)
        try:
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
        except RecoverableToolRejection as exc:
            return [self._handle_recoverable_rejection("list_files", {"root": root}, exc)]

    def execute_command(self, command: list[str], cwd: str | None = None) -> dict[str, Any] | str:
        self._ensure_allowed("execute_command", _EXECUTE_CAPABILITIES)
        arguments = {"command": list(command), "cwd": cwd or self.sandbox.get_workspace_root()}
        try:
            normalized_cwd = self.sandbox.normalize_path(cwd or self.sandbox.get_workspace_root())
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
        except FileNotFoundError as exc:
            missing_command = command[0] if command else "<unknown>"
            return self._handle_recoverable_rejection(
                "execute_command",
                arguments,
                RecoverableToolRejection(
                    code="command_not_found",
                    message=f"Command '{missing_command}' is not installed or not on PATH.",
                    category="command_execution",
                    details={
                        "command": missing_command,
                        "errno": getattr(exc, "errno", None),
                    },
                ),
            )
        except RecoverableToolRejection as exc:
            return self._handle_recoverable_rejection(
                "execute_command",
                arguments,
                exc,
            )

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

    def memory_write(
        self,
        content: str,
        summary: str,
        namespace: str,
        scope: str = "run_state",
        confidence: float | None = None,
    ) -> dict[str, Any] | str:
        self._ensure_allowed("memory_write", _MEMORY_WRITE_CAPABILITIES)
        if self.memory_store is None:
            raise ValueError("memory_write is not configured for this runtime")
        arguments = {
            "scope": scope,
            "namespace": namespace,
            "summary": summary,
            "confidence": confidence,
        }
        try:
            normalized_scope = self._normalize_memory_write_scope(scope)
            normalized_content = content.strip()
            normalized_summary = summary.strip()
            normalized_namespace = namespace.strip()
            if not normalized_content:
                raise RecoverableToolRejection(
                    code="invalid_arguments",
                    message="memory_write content must be non-empty",
                    category="argument_validation",
                )
            if not normalized_summary:
                raise RecoverableToolRejection(
                    code="invalid_arguments",
                    message="memory_write summary must be non-empty",
                    category="argument_validation",
                )
            if not normalized_namespace:
                raise RecoverableToolRejection(
                    code="invalid_arguments",
                    message="memory_write namespace must be non-empty",
                    category="argument_validation",
                )
            if confidence is not None and not 0.0 <= confidence <= 1.0:
                raise RecoverableToolRejection(
                    code="invalid_arguments",
                    message="memory_write confidence must be between 0.0 and 1.0",
                    category="argument_validation",
                )
            self._govern(
                OperationContext(
                    task_id=self.task_id,
                    run_id=self.run_id,
                    operation_type="memory.write",
                    memory_scope=normalized_scope,
                    namespace=normalized_namespace,
                )
            )
            now = utc_now_timestamp()
            record = MemoryRecord(
                memory_id=new_memory_id(),
                scope=normalized_scope,
                namespace=normalized_namespace,
                content=normalized_content,
                summary=normalized_summary,
                provenance={
                    "task_id": self.task_id,
                    "run_id": self.run_id,
                    "source": "agent_tool",
                    "tool": "memory_write",
                },
                created_at=now,
                updated_at=now,
                source_run=self.run_id,
                confidence=confidence,
            )
            self.memory_store.write_memory(record)
            payload = record.to_dict()
            self._emit(
                "tool.called",
                {
                    "tool": "memory_write",
                    "arguments": {
                        "scope": normalized_scope,
                        "namespace": normalized_namespace,
                        "summary": normalized_summary,
                        "confidence": confidence,
                    },
                    "memory_id": record.memory_id,
                    "scope": normalized_scope,
                    "namespace": normalized_namespace,
                    "summary": normalized_summary,
                },
            )
            self._emit(
                "memory.updated",
                {
                    "scope": normalized_scope,
                    "summary": normalized_summary,
                    "entry_count_delta": 1,
                    "namespace": normalized_namespace,
                    "memory_id": record.memory_id,
                },
            )
            return payload
        except RecoverableToolRejection as exc:
            return self._handle_recoverable_rejection("memory_write", arguments, exc)

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

    def request_user_input(self, question: str, reason_code: str | None = None) -> None:
        self._ensure_allowed("request_user_input", _USER_INPUT_CAPABILITIES)
        if self.user_input_handler is None:
            raise ValueError("request_user_input is not configured for this runtime")
        payload = {"question": question.strip()}
        if reason_code is not None and reason_code.strip():
            payload["reason_code"] = reason_code.strip()
        self._emit(
            "tool.called",
            {
                "tool": "request_user_input",
                "arguments": payload,
            },
        )
        self.user_input_handler(**payload)

    def web_fetch(
        self,
        url: str,
        *,
        max_bytes: int | None = None,
        timeout: float | None = None,
        user_agent: str | None = None,
    ) -> dict[str, Any]:
        self._ensure_allowed("web_fetch", _WEB_FETCH_CAPABILITIES)
        if self.web_fetch_port is None:
            raise ValueError("web_fetch is not configured for this runtime")
        self._govern(
            OperationContext(
                task_id=self.task_id,
                run_id=self.run_id,
                operation_type="web.fetch",
                path_scope=url.strip(),
                metadata={"url": url.strip()},
            )
        )
        document = self.web_fetch_port.fetch(
            url,
            max_bytes=max_bytes,
            timeout=timeout,
            user_agent=user_agent,
        )
        payload = document.to_dict()
        self._emit(
            "tool.called",
            {
                "tool": "web_fetch",
                "arguments": {
                    "url": url.strip(),
                    "max_bytes": max_bytes,
                    "timeout": timeout,
                },
                "url": payload["final_url"],
                "content_type": payload["content_type"],
                "status_code": payload["status_code"],
                "content_length": len(document.markdown_content),
            },
        )
        return payload

    def web_search(
        self,
        query: str,
        *,
        limit: int = 5,
        locale: str | None = None,
    ) -> list[dict[str, Any]]:
        self._ensure_allowed("web_search", _WEB_SEARCH_CAPABILITIES)
        if self.web_search_port is None:
            raise ValueError("web_search is not configured for this runtime")
        self._govern(
            OperationContext(
                task_id=self.task_id,
                run_id=self.run_id,
                operation_type="web.search",
                path_scope="https://duckduckgo.com",
                metadata={"query": query.strip(), "limit": limit, "locale": locale},
            )
        )
        results = self.web_search_port.search(query, limit=limit, locale=locale)
        payload = [result.to_dict() for result in results]
        self._emit(
            "tool.called",
            {
                "tool": "web_search",
                "arguments": {"query": query.strip(), "limit": limit, "locale": locale},
                "result_count": len(payload),
            },
        )
        return payload

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
                """Read a UTF-8 text file from a virtual sandbox path such as /workspace/README.md."""
                try:
                    self._ensure_filesystem_scope(path, filesystem_scopes, operation="read_file")
                    return self.read_file(path)
                except RecoverableToolRejection as exc:
                    return self._handle_recoverable_rejection("read_file", {"path": path}, exc)

            @tool
            def list_files(root: str = "/workspace") -> list[str]:
                """List governed files rooted at a virtual sandbox path such as /workspace or /tmp."""
                try:
                    self._ensure_filesystem_scope(root, filesystem_scopes, operation="list_files")
                    return self.list_files(root)
                except RecoverableToolRejection as exc:
                    return [self._handle_recoverable_rejection("list_files", {"root": root}, exc)]

            tools.extend(
                [
                    self._with_validation_handler(read_file, "read_file"),
                    self._with_validation_handler(list_files, "list_files"),
                ]
            )

        if "write_files" in allowed_tool_ids:

            @tool
            def write_file(path: str, content: str) -> str:
                """Write UTF-8 text content to a virtual sandbox path such as /workspace/artifacts/out.md."""
                try:
                    self._ensure_filesystem_scope(path, filesystem_scopes, operation="write_file")
                    return self.write_file(path, content)
                except RecoverableToolRejection as exc:
                    return self._handle_recoverable_rejection("write_file", {"path": path}, exc)

            tools.append(self._with_validation_handler(write_file, "write_file"))

        if "execute_commands" in allowed_tool_ids:

            @tool
            def execute_command(command: Any, cwd: str | None = None) -> dict[str, Any] | str:
                """Execute a command inside the virtual sandbox filesystem and return structured output."""
                try:
                    self._ensure_filesystem_scope(
                        cwd or self.sandbox.get_workspace_root(),
                        filesystem_scopes,
                        operation="execute_command",
                    )
                    parsed_command = _coerce_execute_command(command)
                    if parsed_command is None:
                        return self._handle_recoverable_rejection(
                            "execute_command",
                            {"command": command, "cwd": cwd or self.sandbox.get_workspace_root()},
                            RecoverableToolRejection(
                                code="invalid_arguments",
                                message="`command` must be a list[str] or a JSON string that parses to list[str].",
                                category="argument_validation",
                            ),
                        )
                    return self.execute_command(parsed_command, cwd)
                except RecoverableToolRejection as exc:
                    return self._handle_recoverable_rejection(
                        "execute_command",
                        {"command": command, "cwd": cwd or self.sandbox.get_workspace_root()},
                        exc,
                    )

            tools.append(self._with_validation_handler(execute_command, "execute_command"))

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

            tools.append(self._with_validation_handler(memory_lookup, "memory_lookup"))

        if "memory_write" in allowed_tool_ids:

            @tool
            def memory_write(
                content: str,
                summary: str,
                namespace: str,
                scope: str = "run_state",
                confidence: float | None = None,
            ) -> dict[str, Any] | str:
                """Create a new runtime memory entry in run_state or project scope."""
                return self.memory_write(
                    content=content,
                    summary=summary,
                    namespace=namespace,
                    scope=scope,
                    confidence=confidence,
                )

            tools.append(self._with_validation_handler(memory_write, "memory_write"))

        if "plan_update" in allowed_tool_ids:

            @tool
            def plan_update(summary: str, phase: str | None = None) -> dict[str, Any]:
                """Emit a runtime-friendly plan update."""
                return self.plan_update(summary, phase)

            tools.append(self._with_validation_handler(plan_update, "plan_update"))

        if "artifact_inspect" in allowed_tool_ids:

            @tool
            def artifact_inspect() -> list[dict[str, Any]]:
                """Inspect task artifacts and return metadata with previews when available."""
                return self.artifact_inspect()

            tools.append(self._with_validation_handler(artifact_inspect, "artifact_inspect"))

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

            tools.append(self._with_validation_handler(skill_installer, "skill-installer"))

        if "request_user_input" in allowed_tool_ids:

            @tool
            def request_user_input(question: str, reason_code: str | None = None) -> str:
                """Pause execution and ask the operator a concise plain-text question before continuing."""
                self.request_user_input(question, reason_code)
                return "awaiting_user_input"

            tools.append(self._with_validation_handler(request_user_input, "request_user_input"))

        if "web_fetch" in allowed_tool_ids:

            @tool
            def web_fetch(
                url: str,
                max_bytes: int | None = None,
                timeout: float | None = None,
                user_agent: str | None = None,
            ) -> dict[str, Any]:
                """Fetch an HTTP page and return normalized markdown plus metadata."""
                return self.web_fetch(
                    url,
                    max_bytes=max_bytes,
                    timeout=timeout,
                    user_agent=user_agent,
                )

            tools.append(self._with_validation_handler(web_fetch, "web_fetch"))

        if "web_search" in allowed_tool_ids:

            @tool
            def web_search(
                query: str,
                limit: int = 5,
                locale: str | None = None,
            ) -> list[dict[str, Any]]:
                """Search the public web and return normalized result metadata."""
                return self.web_search(query, limit=limit, locale=locale)

            tools.append(self._with_validation_handler(web_search, "web_search"))

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
            raise RecoverableToolRejection(
                code="scope_denied",
                message=(
                    f"{operation} denied for {normalized_path}: "
                    f"allowed filesystem scopes are {allowed}"
                ),
                category="scope_denied",
                details={"path": normalized_path, "allowed_scopes": sorted(allowed_scopes)},
            )

    def _handle_recoverable_rejection(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        rejection: RecoverableToolRejection,
    ) -> str:
        payload = {
            "tool": tool_name,
            "arguments": _sanitize_tool_arguments(arguments),
            "code": rejection.code,
            "category": rejection.category,
            "message": rejection.message,
            "retryable": rejection.retryable,
            "details": _sanitize_tool_arguments(rejection.details),
            "summary": f"{tool_name} rejected: {rejection.message}",
        }
        self._emit("tool.rejected", payload)
        if rejection.code == "invalid_arguments":
            return _format_invalid_arguments_message(tool_name, rejection.message)
        return _format_tool_rejection_message(rejection)

    def _with_validation_handler(self, tool_obj: BaseTool, tool_name: str) -> BaseTool:
        tool_obj.handle_validation_error = (
            lambda exc: self._handle_validation_error(tool_name=tool_name, exc=exc)
        )
        return tool_obj

    def _handle_validation_error(
        self,
        *,
        tool_name: str,
        exc: ValidationError | Any,
    ) -> str:
        details = exc.errors() if hasattr(exc, "errors") else []
        message = str(exc)
        payload = {
            "tool": tool_name,
            "arguments": {},
            "code": "invalid_arguments",
            "category": "argument_validation",
            "message": message,
            "retryable": True,
            "details": {"errors": details},
            "summary": f"{tool_name} rejected: {message}",
        }
        self._emit("tool.rejected", payload)
        return _format_invalid_arguments_message(tool_name, message)

    def _normalize_memory_write_scope(self, scope: str) -> str:
        normalized = scope.strip().lower()
        if normalized == "run":
            return "run_state"
        if normalized in {"run_state", "project"}:
            return normalized
        raise RecoverableToolRejection(
            code="invalid_arguments",
            message="memory_write scope must be either run_state or project",
            category="argument_validation",
        )


def _artifact_to_sandbox_path(artifact: ArtifactReference) -> str:
    if artifact.persistence_class == "project":
        return artifact.logical_path
    if artifact.persistence_class == "ephemeral":
        return artifact.logical_path
    return artifact.logical_path or "/"


def _coerce_execute_command(command: Any) -> list[str] | None:
    if isinstance(command, list) and all(isinstance(part, str) for part in command):
        return command
    if not isinstance(command, str):
        return None
    try:
        parsed = json.loads(command)
    except json.JSONDecodeError:
        return None
    if isinstance(parsed, list) and all(isinstance(part, str) for part in parsed):
        return parsed
    return None


def _format_invalid_arguments_message(tool_name: str, message: str) -> str:
    if tool_name == "execute_command":
        return (
            f"TOOL_REJECTED [invalid_arguments]: {message} "
            "execute_command requires `command` to be an argv list of strings. "
            "A stringified JSON array is a common mistake; if you have one, pass it as a real list instead, "
            'for example {"command":["python3","-c","print(1)"],"cwd":"/workspace"}.'
        )
    return (
        f"TOOL_REJECTED [invalid_arguments]: {message} "
        "Adjust the tool arguments to satisfy the schema and try again."
    )


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


def _format_tool_rejection_message(rejection: RecoverableToolRejection) -> str:
    message = rejection.message
    rejected_path = rejection.details.get("path")
    if rejection.category == "path_validation" and isinstance(rejected_path, str) and rejected_path:
        message = f"Path '{rejected_path}' is invalid for the sandbox. {rejection.message}"
    guidance = {
        "path_validation": "Use a virtual path under '/workspace', '/tmp', or '/.memory'.",
        "file_access": "Verify the path exists or list nearby files before retrying.",
        "scope_denied": "Use a path within the delegated filesystem scope for this tool call.",
        "policy_denied": "Use a non-destructive or otherwise policy-compliant alternative.",
        "command_execution": "Pick an installed command or verify the executable name before retrying.",
    }.get(rejection.category, "Adjust the tool arguments and try again.")
    return f"TOOL_REJECTED [{rejection.code}]: {message} {guidance}"


def _sanitize_tool_arguments(value: Any) -> Any:
    if isinstance(value, str):
        return "<host-native-path>" if _looks_like_host_path(value.strip()) else value
    if isinstance(value, list):
        return [_sanitize_tool_arguments(item) for item in value]
    if isinstance(value, tuple):
        return [_sanitize_tool_arguments(item) for item in value]
    if isinstance(value, dict):
        return {key: _sanitize_tool_arguments(item) for key, item in value.items()}
    return value


def _looks_like_host_path(raw: str) -> bool:
    if raw.startswith("~") or raw.startswith("$"):
        return True
    if len(raw) >= 3 and raw[1] == ":" and raw[2] in {"\\", "/"}:
        return True
    return raw.startswith("/") and not raw.startswith(("/workspace", "/tmp", "/.memory"))

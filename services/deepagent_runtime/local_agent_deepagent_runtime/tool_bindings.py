from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from langchain_core.tools import BaseTool, tool

from services.sandbox_service.local_agent_sandbox_service.sandbox import ExecutionSandbox

EventCallback = Callable[[str, dict[str, Any]], None]

_READ_CAPABILITIES = {"read_file", "filesystem", "files.read"}
_WRITE_CAPABILITIES = {"write_file", "filesystem", "files.write"}
_LIST_CAPABILITIES = {"list_files", "filesystem", "files.list"}
_EXECUTE_CAPABILITIES = {"execute_command", "commands", "sandbox.execute"}


@dataclass(slots=True)
class SandboxToolBindings:
    sandbox: ExecutionSandbox
    on_event: EventCallback | None = None
    allowed_capabilities: list[str] | None = None

    def read_file(self, path: str) -> str:
        self._ensure_allowed("read_file", _READ_CAPABILITIES)
        normalized_path = self.sandbox.normalize_path(path)
        self._emit(
            "tool.called",
            {
                "tool": "read_file",
                "path": normalized_path,
            },
        )
        return self.sandbox.read_text(normalized_path)

    def write_file(self, path: str, content: str) -> str:
        self._ensure_allowed("write_file", _WRITE_CAPABILITIES)
        normalized_path = self.sandbox.normalize_path(path)
        self._emit(
            "tool.called",
            {
                "tool": "write_file",
                "path": normalized_path,
                "bytes_written": len(content.encode("utf-8")),
            },
        )
        self.sandbox.write_text(normalized_path, content)
        return normalized_path

    def list_files(self, root: str) -> list[str]:
        self._ensure_allowed("list_files", _LIST_CAPABILITIES)
        normalized_root = self.sandbox.normalize_path(root)
        self._emit(
            "tool.called",
            {
                "tool": "list_files",
                "path": normalized_root,
            },
        )
        return self.sandbox.list_files(normalized_root)

    def execute_command(self, command: list[str], cwd: str | None = None) -> dict[str, Any]:
        self._ensure_allowed("execute_command", _EXECUTE_CAPABILITIES)
        normalized_cwd = self.sandbox.normalize_path(cwd or "workspace")
        self._emit(
            "tool.called",
            {
                "tool": "execute_command",
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

    def as_langchain_tools(self) -> list[BaseTool]:
        @tool
        def read_file(path: str) -> str:
            """Read a UTF-8 text file from a governed sandbox path."""
            return self.read_file(path)

        @tool
        def write_file(path: str, content: str) -> str:
            """Write UTF-8 text content to a governed sandbox path."""
            return self.write_file(path, content)

        @tool
        def list_files(root: str) -> list[str]:
            """List governed files rooted at a sandbox path."""
            return self.list_files(root)

        @tool
        def execute_command(command: list[str], cwd: str | None = None) -> dict[str, Any]:
            """Execute a command inside the governed sandbox and return structured output."""
            return self.execute_command(command, cwd)

        return [read_file, write_file, list_files, execute_command]

    def _ensure_allowed(self, tool_name: str, aliases: set[str]) -> None:
        allowed_capabilities = {item.strip() for item in self.allowed_capabilities or [] if item}
        if not allowed_capabilities:
            return
        if allowed_capabilities.isdisjoint(aliases):
            raise PermissionError(f"{tool_name} is not allowed for this run")

    def _emit(self, event_type: str, payload: dict[str, Any]) -> None:
        if self.on_event is not None:
            self.on_event(event_type, payload)

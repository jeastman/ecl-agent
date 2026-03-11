from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
from pathlib import Path
from typing import Any
import re
import shutil

from services.sandbox_service.local_agent_sandbox_service.sandbox import ExecutionSandbox
from services.subagent_runtime.local_agent_subagent_runtime.skill_catalog import (
    RuntimeSkillCatalog,
    SkillInstallTarget,
)

MAX_SKILL_BYTES = 1_000_000
_SECRET_PATTERNS = (
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    re.compile(r"\bghp_[A-Za-z0-9]{20,}\b"),
    re.compile(r"\bsk-[A-Za-z0-9]{20,}\b"),
    re.compile(r"(?i)(api[_-]?key|secret|token)\s*[:=]\s*['\"][^'\"]+['\"]"),
)


@dataclass(frozen=True, slots=True)
class SkillValidationFinding:
    severity: str
    code: str
    message: str
    path: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {key: value for key, value in asdict(self).items() if value is not None}


@dataclass(frozen=True, slots=True)
class SkillValidationResult:
    status: str
    findings: tuple[SkillValidationFinding, ...] = ()
    has_scripts: bool = False
    total_bytes: int = 0
    file_count: int = 0
    skill_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "findings": [finding.to_dict() for finding in self.findings],
            "has_scripts": self.has_scripts,
            "total_bytes": self.total_bytes,
            "file_count": self.file_count,
            "skill_id": self.skill_id,
        }


@dataclass(frozen=True, slots=True)
class PreparedSkillInstall:
    source_sandbox_path: str
    source_host_path: Path
    target: SkillInstallTarget
    target_skill_path: Path
    install_mode: str
    reason: str
    manifest: tuple[str, ...]
    validation: SkillValidationResult
    overwrite: bool


@dataclass(frozen=True, slots=True)
class SkillInstallOutcome:
    status: str
    summary: str
    target_path: str
    validation: SkillValidationResult
    approval_required: bool = False
    approval_id: str | None = None
    artifacts: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        payload = {
            "status": self.status,
            "summary": self.summary,
            "target_path": self.target_path,
            "validation": self.validation.to_dict(),
            "approval_required": self.approval_required,
            "artifacts": list(self.artifacts),
        }
        if self.approval_id is not None:
            payload["approval_id"] = self.approval_id
        return payload


class SkillInstallationService:
    def __init__(self, catalog: RuntimeSkillCatalog) -> None:
        self._catalog = catalog

    def prepare_install(
        self,
        *,
        sandbox: ExecutionSandbox,
        source_path: str,
        target_scope: str,
        target_role: str | None,
        install_mode: str,
        reason: str,
    ) -> PreparedSkillInstall:
        if install_mode not in {"fail_if_exists", "replace"}:
            raise ValueError("skill.install install_mode must be fail_if_exists or replace")
        source_sandbox_path = sandbox.normalize_path(source_path)
        source_host_path = sandbox.resolve_path(source_sandbox_path)
        if not source_host_path.exists():
            raise ValueError(f"skill.install source_path does not exist: {source_sandbox_path}")
        if not source_host_path.is_dir():
            raise ValueError(
                f"skill.install source_path must be a directory: {source_sandbox_path}"
            )
        target = self._catalog.resolve_install_target(target_scope, target_role)
        validation, manifest = _validate_skill(source_host_path)
        skill_id = validation.skill_id
        if skill_id is None:
            raise ValueError("skill.install could not derive a skill id from the staged directory")
        target_skill_path = target.managed_root / skill_id
        overwrite = target_skill_path.exists()
        if overwrite and install_mode == "fail_if_exists":
            validation = _with_finding(
                validation,
                SkillValidationFinding(
                    severity="error",
                    code="conflict",
                    message="Skill already exists at the target path.",
                    path=str(target_skill_path),
                ),
            )
        if validation.status == "fail":
            return PreparedSkillInstall(
                source_sandbox_path=source_sandbox_path,
                source_host_path=source_host_path,
                target=target,
                target_skill_path=target_skill_path,
                install_mode=install_mode,
                reason=reason.strip(),
                manifest=manifest,
                validation=validation,
                overwrite=overwrite,
            )
        return PreparedSkillInstall(
            source_sandbox_path=source_sandbox_path,
            source_host_path=source_host_path,
            target=target,
            target_skill_path=target_skill_path,
            install_mode=install_mode,
            reason=reason.strip(),
            manifest=manifest,
            validation=validation,
            overwrite=overwrite,
        )

    def execute_install(self, prepared: PreparedSkillInstall) -> None:
        prepared.target.managed_root.mkdir(parents=True, exist_ok=True)
        target_path = prepared.target_skill_path
        parent = target_path.parent
        staging_path = parent / f".{target_path.name}.installing"
        if staging_path.exists():
            shutil.rmtree(staging_path)
        shutil.copytree(prepared.source_host_path, staging_path, dirs_exist_ok=False)
        if target_path.exists():
            shutil.rmtree(target_path)
        staging_path.replace(target_path)

    def artifact_payloads(self, prepared: PreparedSkillInstall) -> dict[str, str]:
        skill_id = prepared.validation.skill_id or prepared.source_host_path.name
        base = f"workspace/artifacts/skill-installs/{skill_id}"
        validation_payload = (
            json.dumps(prepared.validation.to_dict(), sort_keys=True, indent=2) + "\n"
        )
        summary_payload = (
            json.dumps(
                {
                    "source_path": prepared.source_sandbox_path,
                    "target_path": str(prepared.target_skill_path),
                    "target_scope": prepared.target.target_scope,
                    "target_role": prepared.target.role_id,
                    "install_mode": prepared.install_mode,
                    "reason": prepared.reason,
                    "overwrite": prepared.overwrite,
                    "manifest_sha256": _manifest_hash(prepared.manifest),
                },
                sort_keys=True,
                indent=2,
            )
            + "\n"
        )
        manifest_payload = "\n".join(prepared.manifest) + ("\n" if prepared.manifest else "")
        conflict_payload = ""
        if prepared.overwrite:
            conflict_payload = (
                json.dumps(
                    {
                        "status": "replace" if prepared.install_mode == "replace" else "conflict",
                        "target_path": str(prepared.target_skill_path),
                    },
                    sort_keys=True,
                    indent=2,
                )
                + "\n"
            )
        return {
            f"{base}/validation-report.json": validation_payload,
            f"{base}/install-summary.json": summary_payload,
            f"{base}/file-manifest.txt": manifest_payload,
            f"{base}/conflict-report.json": conflict_payload,
        }


def _validate_skill(source_root: Path) -> tuple[SkillValidationResult, tuple[str, ...]]:
    findings: list[SkillValidationFinding] = []
    manifest: list[str] = []
    skill_id = source_root.name.strip()
    if not skill_id:
        findings.append(
            SkillValidationFinding(
                severity="error",
                code="invalid_name",
                message="Skill directory name must be non-empty.",
            )
        )

    total_bytes = 0
    file_count = 0
    has_scripts = False
    has_skill_md = False
    for candidate in sorted(source_root.rglob("*")):
        relative = candidate.relative_to(source_root)
        relative_text = relative.as_posix()
        if candidate.is_symlink():
            findings.append(
                SkillValidationFinding(
                    severity="error",
                    code="symlink_not_allowed",
                    message="Symlinks are not allowed in skill bundles.",
                    path=relative_text,
                )
            )
            continue
        if candidate.is_dir():
            continue
        file_count += 1
        manifest.append(relative_text)
        if relative.parts and relative.parts[0] == "scripts":
            has_scripts = True
        if relative_text == "SKILL.md":
            has_skill_md = True
        total_bytes += candidate.stat().st_size
        if total_bytes > MAX_SKILL_BYTES:
            findings.append(
                SkillValidationFinding(
                    severity="warning",
                    code="package_large",
                    message=f"Skill package exceeds {MAX_SKILL_BYTES} bytes.",
                )
            )
        if candidate.suffix.lower() in {".md", ".txt", ".py", ".sh", ".json", ".yaml", ".yml"}:
            try:
                text = candidate.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                continue
            for pattern in _SECRET_PATTERNS:
                if pattern.search(text):
                    findings.append(
                        SkillValidationFinding(
                            severity="error",
                            code="secret_detected",
                            message="Skill bundle appears to contain a secret-like value.",
                            path=relative_text,
                        )
                    )
                    break
    if not has_skill_md:
        findings.append(
            SkillValidationFinding(
                severity="error",
                code="missing_skill_md",
                message="Skill bundle must contain SKILL.md at the root.",
                path="SKILL.md",
            )
        )
    status = "pass"
    if any(finding.severity == "error" for finding in findings):
        status = "fail"
    elif findings:
        status = "pass_with_warnings"
    return (
        SkillValidationResult(
            status=status,
            findings=tuple(findings),
            has_scripts=has_scripts,
            total_bytes=total_bytes,
            file_count=file_count,
            skill_id=skill_id or None,
        ),
        tuple(manifest),
    )


def _with_finding(
    validation: SkillValidationResult, finding: SkillValidationFinding
) -> SkillValidationResult:
    findings = list(validation.findings)
    findings.append(finding)
    return SkillValidationResult(
        status="fail" if finding.severity == "error" else "pass_with_warnings",
        findings=tuple(findings),
        has_scripts=validation.has_scripts,
        total_bytes=validation.total_bytes,
        file_count=validation.file_count,
        skill_id=validation.skill_id,
    )


def _manifest_hash(manifest: tuple[str, ...]) -> str:
    digest = hashlib.sha256()
    for entry in manifest:
        digest.update(entry.encode("utf-8"))
        digest.update(b"\n")
    return digest.hexdigest()

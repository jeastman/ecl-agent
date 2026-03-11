from __future__ import annotations

import hashlib
from pathlib import Path

from packages.identity.local_agent_identity.models import IdentityBundle


def validate_identity_document(content: str) -> None:
    stripped = content.strip()
    if not stripped:
        raise ValueError("identity file is empty")
    if not stripped.startswith("# "):
        raise ValueError("identity file must start with a level-1 markdown heading")


def load_identity_bundle(path: str) -> IdentityBundle:
    identity_path = Path(path)
    if not identity_path.is_file():
        raise ValueError(f"identity file not found: {path}")

    content = identity_path.read_text(encoding="utf-8")
    validate_identity_document(content)
    sha256 = hashlib.sha256(content.encode("utf-8")).hexdigest()
    return IdentityBundle(
        source_path=str(identity_path.resolve()),
        version=f"sha256:{sha256[:12]}",
        sha256=sha256,
        content=content,
    )

from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class IdentityBundle:
    source_path: str
    version: str
    sha256: str
    content: str

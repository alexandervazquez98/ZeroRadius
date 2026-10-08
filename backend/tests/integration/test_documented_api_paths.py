"""Regression test for issue #77: documented API paths must match the backend.

The ZeroRadius backend mounts every route directly under `/` (no prefix).
The docs originally referenced `/api/v1/...` everywhere, which made every
example curl return 404.

This test enforces the no-prefix contract: any future change that adds
an `/api/v1` (or any other) prefix to the live backend will fail this
test, forcing the author to either revert the prefix or update the docs
explicitly.

It also runs a static check across the docs tree to make sure no
documented example still uses the obsolete `/api/v1/` prefix.
"""

import os
import re
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[3]  # backend/tests/integration -> repo root
DOCS_DIR = REPO_ROOT / "docs"
EXEMPT_DOCS = {
    # docs/api-reference.md front-matter explicitly mentions /api/v1 in
    # the corrective note "no /api/v1 prefix — the backend mounts
    # routes directly under /". Future re-introductions must be
    # deliberate.
    "api-reference.md",
}


# ---------------------------------------------------------------------------
# Live backend: OpenAPI paths must not carry an /api/v1 prefix
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_openapi_paths_have_no_api_v1_prefix(async_client):
    """The live FastAPI app must expose routes under `/` directly.

    If the backend ever gains an `/api/v1` prefix (or any other prefix)
    this test fails — forcing a doc update or a deliberate revert.
    """
    response = await async_client.get("/openapi.json")
    assert response.status_code == 200, (
        f"OpenAPI spec not reachable: HTTP {response.status_code}"
    )

    spec = response.json()
    paths = list(spec.get("paths", {}).keys())
    assert paths, "OpenAPI spec has no paths — the backend is empty?"

    forbidden = [p for p in paths if p.startswith("/api")]
    assert not forbidden, (
        f"Backend exposes routes under an /api prefix — docs do not match.\n"
        f"  Offending paths: {forbidden}\n"
        f"  All paths: {sorted(paths)}\n"
        f"  Either remove the prefix from the backend or update the docs."
    )


# ---------------------------------------------------------------------------
# Static check: docs must not reference the obsolete /api/v1/ prefix
# ---------------------------------------------------------------------------


def test_docs_do_not_reference_api_v1_path():
    """A documented path like `POST /api/v1/auth/token` returns 404.

    Walk the docs tree and fail on any reference to the literal
    `/api/v1/` token — except in the api-reference.md corrective
    note that explicitly documents its absence.
    """
    pattern = re.compile(r"/api/v1/")
    offenders: list[tuple[Path, int, str]] = []

    for md_path in DOCS_DIR.rglob("*.md"):
        if md_path.name in EXEMPT_DOCS:
            continue
        for lineno, line in enumerate(md_path.read_text().splitlines(), start=1):
            if pattern.search(line):
                offenders.append((md_path, lineno, line.strip()))

    assert not offenders, (
        "Docs reference the obsolete /api/v1/ path — every example returns 404.\n"
        + "\n".join(
            f"  {p.relative_to(REPO_ROOT)}:{ln}  {snippet}"
            for p, ln, snippet in offenders[:20]
        )
        + (f"\n  ... and {len(offenders) - 20} more" if len(offenders) > 20 else "")
    )

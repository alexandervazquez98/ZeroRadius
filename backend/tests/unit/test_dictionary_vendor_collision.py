"""
Regression tests for the vendor-ID collision check in the dictionary loader.

Issue #76: ``POST /dictionary/upload`` rejected a Cisco dictionary with
``VENDOR Cisco 9`` because the validator's hard-coded
``_BUILTIN_VENDOR_IDS`` list claimed vendor 9 was "built-in" — but the
``radius/Dockerfile`` deliberately removes ``dictionary.cisco*`` from
the upstream image.  The vendor-ID check has been refactored to query
the running ``radius-server`` container for the vendor IDs it
*actually* ships with, and to fall back to a minimal static list
(Microsoft 311) when Docker is unavailable.

These tests cover both layers:

* the pure-Python ``_check_vendor_id_collision`` helper (no Docker, no FS)
* the end-to-end ``DictionaryService.validate_and_save`` path that
  exercises the validator pipeline (used by the upload endpoint)
"""

import os
import tempfile

import pytest

from app.services import dictionary_loader
from app.services.dictionary_loader import (
    DictionaryService,
    _check_vendor_id_collision,
    _get_builtin_vendor_ids,
    _get_builtin_vendor_ids_from_container,
    reset_builtin_vendor_ids_cache,
)


# ---------------------------------------------------------------------------
# Test fixtures / helpers
# ---------------------------------------------------------------------------

CISCO_VENDOR_9_CONTENT = """\
VENDOR    Cisco    9
BEGIN-VENDOR    Cisco
ATTRIBUTE    Cisco-AVPair    1    string
ATTRIBUTE    Cisco-NAS-Port    2    integer
END-VENDOR    Cisco
"""

MICROSOFT_VENDOR_311_CONTENT = """\
VENDOR    Microsoft    311
BEGIN-VENDOR    Microsoft
ATTRIBUTE    MS-CHAP-Response    1    octets
END-VENDOR    Microsoft
"""

ACME_VENDOR_99999_CONTENT = """\
VENDOR    AcmeCorp    99999
BEGIN-VENDOR    AcmeCorp
ATTRIBUTE    Acme-Attr    1    string
END-VENDOR    AcmeCorp
"""


@pytest.fixture(autouse=True)
def _reset_builtin_vendor_cache():
    """Reset the built-in vendor cache before each test.

    The cache is process-global, so without this every test would see
    whatever the previous test resolved (which is fine for unit tests
    since the fallback path is deterministic, but we want explicit
    control).
    """
    reset_builtin_vendor_ids_cache()
    yield
    reset_builtin_vendor_ids_cache()


@pytest.fixture
def tmp_dict_dir(tmp_path):
    """Return a fresh, empty custom-dictionaries directory."""
    d = tmp_path / "dictionaries"
    d.mkdir()
    return d


# ---------------------------------------------------------------------------
# Direct tests of the collision helper
# ---------------------------------------------------------------------------

class TestCheckVendorIdCollision:
    """Tests for ``_check_vendor_id_collision`` (no Docker, no FS writes)."""

    def test_empty_content_returns_no_collisions(self):
        # No VENDOR declarations => nothing to check.
        assert _check_vendor_id_collision("ATTRIBUTE  Foo  1  string\n", []) == []

    def test_cisco_vendor_9_no_collision_in_unit_test_mode(self):
        """Issue #76 — vendor 9 (Cisco) is no longer treated as built-in.

        With Docker unavailable, the fallback list is just
        ``{311: "Microsoft"}``.  A Cisco upload must therefore pass.
        """
        collisions = _check_vendor_id_collision(CISCO_VENDOR_9_CONTENT, [])
        assert collisions == [], (
            f"Cisco upload should be accepted in unit-test mode, got: {collisions}"
        )

    def test_microsoft_vendor_311_still_rejected(self):
        """Regression protection — Microsoft remains the only built-in vendor."""
        collisions = _check_vendor_id_collision(MICROSOFT_VENDOR_311_CONTENT, [])
        assert len(collisions) == 1
        assert "311" in collisions[0]
        assert "Microsoft" in collisions[0]

    def test_arbitrary_vendor_id_is_accepted(self):
        """A vendor ID that is neither built-in nor used elsewhere is allowed."""
        collisions = _check_vendor_id_collision(ACME_VENDOR_99999_CONTENT, [])
        assert collisions == []

    def test_collision_against_existing_custom_dictionary(self):
        """Two custom dictionaries that share a vendor ID must collide."""
        with tempfile.NamedTemporaryFile(
            "w", suffix=".dict", delete=False
        ) as first:
            first.write(CISCO_VENDOR_9_CONTENT)
            first_path = first.name
        try:
            collisions = _check_vendor_id_collision(
                CISCO_VENDOR_9_CONTENT, [first_path]
            )
            assert len(collisions) == 1
            assert "9" in collisions[0]
            assert os.path.basename(first_path) in collisions[0]
        finally:
            os.unlink(first_path)

    def test_skip_filename_allows_overwrite(self):
        """Overwriting a custom dictionary with the same vendor ID is allowed.

        Used by the ``PUT /content/{filename}`` flow so users can edit a
        file without being told it conflicts with itself.
        """
        with tempfile.NamedTemporaryFile(
            "w", suffix=".dict", delete=False
        ) as first:
            first.write(CISCO_VENDOR_9_CONTENT)
            first_path = first.name
        try:
            # Same content, same vendor ID, same file => no collision
            collisions = _check_vendor_id_collision(
                CISCO_VENDOR_9_CONTENT,
                [first_path],
                skip_filename=os.path.basename(first_path),
            )
            assert collisions == []
        finally:
            os.unlink(first_path)

    def test_corrupt_existing_file_does_not_raise(self):
        """If an existing custom file is unreadable, the check should skip
        it gracefully rather than crash the upload."""
        with tempfile.NamedTemporaryFile(
            "w", suffix=".dict", delete=False
        ) as bad:
            # Use a path that will fail to open by deleting it after the
            # file handle closes.
            bad.write("placeholder")
            bad_path = bad.name
        os.unlink(bad_path)  # delete the file but keep the path
        # No exception should be raised; result is just no extra collisions
        collisions = _check_vendor_id_collision(
            CISCO_VENDOR_9_CONTENT, [bad_path]
        )
        assert collisions == []


# ---------------------------------------------------------------------------
# End-to-end tests through the public service API
# ---------------------------------------------------------------------------

class TestDictionaryServiceAcceptsCisco:
    """``DictionaryService.validate_and_save`` should accept Cisco dicts."""

    def test_regression_cisco_vendor_9_upload_accepted(self, tmp_dict_dir):
        """Regression for issue #76 — the canonical Cisco dict uploads cleanly.

        Before the fix this raised::

            ValueError: Vendor ID conflict detected — FreeRADIUS would
            fail to start: Vendor ID 9 (Cisco) conflicts with built-in
            FreeRADIUS vendor 'Cisco'...

        After the fix it returns ``{conversions, renames}`` and writes
        the file to disk.
        """
        svc = DictionaryService(str(tmp_dict_dir))
        result = svc.validate_and_save(
            "dictionary.cisco", CISCO_VENDOR_9_CONTENT.encode("utf-8")
        )
        assert result["conversions"] == 0
        assert result["renames"] == []
        # File landed on disk
        out_path = tmp_dict_dir / "dictionary.cisco"
        assert out_path.exists()
        # And is parseable by pyrad end-to-end
        from pyrad.dictionary import Dictionary
        d = Dictionary()
        d.ReadDictionary(str(out_path))
        assert d["Cisco-AVPair"].code == 1
        assert d["Cisco-AVPair"].type == "string"
        # pyrad exposes the vendor name as a string here, not an object
        assert str(d["Cisco-AVPair"].vendor) == "Cisco"

    def test_regression_microsoft_still_rejected(self, tmp_dict_dir):
        """Regression protection — Microsoft is the *only* still-rejected vendor."""
        svc = DictionaryService(str(tmp_dict_dir))
        with pytest.raises(ValueError) as exc_info:
            svc.validate_and_save(
                "dictionary.microsoft", MICROSOFT_VENDOR_311_CONTENT.encode("utf-8")
            )
        msg = str(exc_info.value)
        assert "Vendor ID conflict" in msg
        assert "311" in msg
        assert "Microsoft" in msg

    def test_cisco_upload_under_arbitrary_filename(self, tmp_dict_dir):
        """The validator is independent of the on-disk filename — the file
        can be named anything; what matters is the ``VENDOR`` line."""
        svc = DictionaryService(str(tmp_dict_dir))
        result = svc.validate_and_save(
            "cisco_supplement.dict", CISCO_VENDOR_9_CONTENT.encode("utf-8")
        )
        assert result["conversions"] == 0
        assert (tmp_dict_dir / "cisco_supplement.dict").exists()

    def test_cisco_vendor_accepted_after_microsoft_rejected(self, tmp_dict_dir):
        """A first attempt that fails must not poison the directory state
        for the next attempt (cache + listdir must stay in sync)."""
        svc = DictionaryService(str(tmp_dict_dir))

        # First: Microsoft upload (rejected)
        with pytest.raises(ValueError):
            svc.validate_and_save(
                "dictionary.microsoft", MICROSOFT_VENDOR_311_CONTENT.encode("utf-8")
            )
        # The directory must still be empty — failure must not leave a
        # partial file behind.
        assert list(tmp_dict_dir.iterdir()) == []

        # Then: Cisco upload (accepted) in the same directory
        result = svc.validate_and_save(
            "dictionary.cisco", CISCO_VENDOR_9_CONTENT.encode("utf-8")
        )
        assert (tmp_dict_dir / "dictionary.cisco").exists()
        assert result["conversions"] == 0


# ---------------------------------------------------------------------------
# Cache behaviour
# ---------------------------------------------------------------------------

class TestBuiltinVendorIdCache:
    """The built-in-vendor cache must fall back safely when Docker is absent."""

    def test_fallback_is_microsoft_only(self):
        """In unit tests (no Docker) the fallback must be the post-Dockerfile
        reality: only Microsoft (311) survives ``radius/Dockerfile``."""
        # Force the resolution path (no Docker available here)
        builtin = _get_builtin_vendor_ids()
        assert 311 in builtin
        assert builtin[311] == "Microsoft"
        # All the other vendors that used to be hard-coded are now gone
        for old_vid in (9, 43, 529, 562, 1584, 2352, 2636, 3076, 4874,
                        5003, 6527, 8164, 10415, 25053):
            assert old_vid not in builtin, (
                f"Vendor {old_vid} should not be in the fallback list — "
                f"its dictionary is removed by radius/Dockerfile"
            )

    def test_cache_returns_same_dict_object(self):
        """The cache must be stable for the process lifetime — call sites
        rely on a single resolved view, not fresh dicts every call."""
        first = _get_builtin_vendor_ids()
        second = _get_builtin_vendor_ids()
        assert first is second

    def test_reset_clears_cache(self):
        _get_builtin_vendor_ids()  # populate
        assert dictionary_loader._builtin_vendor_ids_cache is not None
        reset_builtin_vendor_ids_cache()
        assert dictionary_loader._builtin_vendor_ids_cache is None


# ---------------------------------------------------------------------------
# Container-resolution helper
# ---------------------------------------------------------------------------

class TestGetBuiltinVendorIdsFromContainer:
    """``_get_builtin_vendor_ids_from_container`` must fail open (return None)."""

    def test_returns_none_when_docker_unavailable(self, monkeypatch):
        """If the Docker SDK cannot import / connect, the function returns
        ``None`` so the caller can fall back to the static list."""
        # Force the import of docker to fail
        import builtins

        real_import = builtins.__import__

        def _blocked(name, *args, **kwargs):
            if name == "docker" or name.startswith("docker."):
                raise ImportError("docker SDK disabled for this test")
            return real_import(name, *args, **kwargs)

        monkeypatch.setattr(builtins, "__import__", _blocked)
        # Also clear any cached resolution
        result = _get_builtin_vendor_ids_from_container()
        assert result is None

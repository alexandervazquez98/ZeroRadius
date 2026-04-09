import os
import re
import shutil
import tempfile
import logging
from pathlib import Path
from pyrad.dictionary import Dictionary, ParseError
from typing import List, Dict, Set

logger = logging.getLogger(__name__)

# FreeRADIUS 4.x -> 3.x type mapping.
# Dictionaries downloaded from modern sources use v4 type names that
# FreeRADIUS 3.x (and pyrad) do not recognise.
TYPE_MAP_V4_TO_V3 = {
    "uint8": "byte",
    "uint16": "short",
    "uint32": "integer",
    "uint64": "integer64",
    "int32": "signed",
    "bool": "byte",
    "time_delta": "integer",
    "float32": "integer",
}

# Regex that matches an ATTRIBUTE line:
#   ATTRIBUTE  <name>  <code>  <type>  [options...]
_ATTR_RE = re.compile(
    r"^(\s*ATTRIBUTE\s+\S+\s+\S+\s+)("
    + "|".join(re.escape(k) for k in TYPE_MAP_V4_TO_V3)
    + r")(\s|$)",
    re.IGNORECASE | re.MULTILINE,
)

# Regex to extract attribute names from dictionary content.
# Matches:  ATTRIBUTE  <name>  <code>  <type>
_ATTR_NAME_RE = re.compile(
    r"^\s*ATTRIBUTE\s+(\S+)\s+\d+\s+\S+",
    re.IGNORECASE | re.MULTILINE,
)

# Keywords only valid in FreeRADIUS 4.x — must be stripped from 3.x dicts.
_V4_ONLY_KEYWORDS = {"ALIAS", "STRUCT", "MEMBER", "FLAGS"}

# Regex to detect and remove FreeRADIUS 4.x-only keyword lines.
_V4_KEYWORD_RE = re.compile(
    r"^\s*(?:" + "|".join(_V4_ONLY_KEYWORDS) + r")\s+",
    re.IGNORECASE | re.MULTILINE,
)

# Built-in FreeRADIUS vendor IDs that are already loaded from /usr/share/freeradius/.
# Uploading a custom dictionary with any of these IDs would cause a collision.
# Source: freeradius-server 3.2 dictionary files.
_BUILTIN_VENDOR_IDS: Dict[int, str] = {
    9: "Cisco",
    43: "3Com",
    # 161 intentionally excluded: the Dockerfile disables dictionary.motorola.wimax,
    # so Cambium custom dictionaries (vendor 161) are allowed without conflict.
    311: "Microsoft",
    529: "Ascend",
    562: "USR",
    1584: "Cosine",
    2352: "Foundry",
    2636: "Juniper",
    3076: "Altiga/Cisco-VPN",
    4874: "Extreme",
    5003: "Colubris",
    6527: "Alcatel",
    8164: "Starent",
    10415: "3GPP",
    25053: "Ruckus",
}

# Regex to match VENDOR lines: VENDOR <name> <id>  OR  VENDOR <id> <name>
_VENDOR_RE = re.compile(
    r"^\s*VENDOR\s+(\S+)\s+(\d+)",
    re.IGNORECASE | re.MULTILINE,
)

# ---------- Built-in dictionary attribute parser ----------

# Matches:  ATTRIBUTE <name> <code> <type>  [optional-extras...]
_BUILTIN_ATTR_LINE_RE = re.compile(
    r"^ATTRIBUTE\s+(\S+)\s+(\d+)\s+(\S+)",
    re.IGNORECASE,
)
_BUILTIN_BEGIN_VENDOR_RE = re.compile(r"^BEGIN-VENDOR\s+(\S+)", re.IGNORECASE)
_BUILTIN_END_VENDOR_RE = re.compile(r"^END-VENDOR", re.IGNORECASE)


def _parse_builtin_attr_grep_output(grep_output: str) -> List[Dict]:
    """Parse ``grep -rE`` output into RADIUS attribute dicts compatible with
    ``DictionaryService.get_attributes()``.

    Expected input is the combined stdout of::

        grep -rE "^(ATTRIBUTE|VENDOR|BEGIN-VENDOR|END-VENDOR)" \\
             /usr/share/freeradius/

    Each input line has the form::

        /usr/share/freeradius/dictionary.cisco:ATTRIBUTE  Cisco-AVPair  1  string

    The function tracks BEGIN-VENDOR / END-VENDOR state **per source file**
    because ``grep -r`` interleaves lines from multiple files.

    Returns a list of dicts with keys:
        name, code (int), type (str), vendor (str), dictionary (str)

    The ``dictionary`` value is prefixed with ``[Sistema]`` so the
    AttributeSelector component groups built-ins separately from custom files.

    Duplicate attribute names across built-in files are deduplicated; the
    first occurrence wins (files are processed in filesystem order).
    """
    # vendor_ctx maps filename → current vendor name (None if outside a BEGIN-VENDOR block)
    vendor_ctx: Dict[str, Optional[str]] = {}
    attrs: List[Dict] = []
    seen_names: Set[str] = set()

    for raw_line in grep_output.splitlines():
        raw_line = raw_line.strip()
        if not raw_line:
            continue

        # grep -r format: /path/to/file:content
        colon_idx = raw_line.find(":")
        if colon_idx == -1:
            continue

        filepath = raw_line[:colon_idx]
        content = raw_line[colon_idx + 1 :].strip()

        if not content or content.startswith("#"):
            continue

        filename = os.path.basename(filepath)

        # Track BEGIN-VENDOR / END-VENDOR state per file
        bm = _BUILTIN_BEGIN_VENDOR_RE.match(content)
        if bm:
            vendor_ctx[filename] = bm.group(1)
            continue

        if _BUILTIN_END_VENDOR_RE.match(content):
            vendor_ctx[filename] = None
            continue

        # VENDOR declaration lines carry no attribute data — skip
        if re.match(r"^VENDOR\s", content, re.IGNORECASE):
            continue

        am = _BUILTIN_ATTR_LINE_RE.match(content)
        if not am:
            continue

        name, code, attr_type = am.group(1), am.group(2), am.group(3)

        # Dedup: first occurrence wins (alphabetical file order via grep -r)
        if name in seen_names:
            continue
        seen_names.add(name)

        vendor = vendor_ctx.get(filename) or "IETF (Standard)"
        attrs.append(
            {
                "name": name,
                "code": int(code),
                "type": attr_type,
                "vendor": vendor,
                "dictionary": f"[Sistema] {filename}",
            }
        )

    return attrs


def _load_base_attribute_names() -> Set[str]:
    """Load all attribute names from pyrad's built-in dictionary.

    pyrad ships with a copy of the FreeRADIUS base dictionary that
    covers all standard RFCs.  We parse it once at import time and
    use the resulting set to detect name collisions when users upload
    custom vendor dictionaries.

    This replaces the previous hard-coded _BASE_RADIUS_ATTRIBUTES set
    and automatically covers every RFC dictionary that pyrad knows about.
    """
    try:
        base = Dictionary()
        # pyrad ships a default 'dictionary' in its package data
        # that includes all standard attributes.  Dictionary() without
        # arguments loads it automatically.  Some pyrad installations
        # may not populate .attributes until a file is read, so we also
        # try the pyrad package path.
        names = set()
        if hasattr(base, "attributes"):
            for attr_name in base.attributes:
                names.add(attr_name)
        if names:
            logger.info("Loaded %d base RADIUS attribute names from pyrad", len(names))
            return names
    except Exception as exc:
        logger.warning("Could not load pyrad base dictionary: %s", exc)

    # Fallback: a comprehensive static set covering the most common RFCs.
    logger.info("Using static fallback for base RADIUS attribute names")
    return {
        # RFC 2865
        "User-Name",
        "User-Password",
        "CHAP-Password",
        "NAS-IP-Address",
        "NAS-Port",
        "Service-Type",
        "Framed-Protocol",
        "Framed-IP-Address",
        "Framed-IP-Netmask",
        "Framed-Routing",
        "Filter-Id",
        "Framed-MTU",
        "Framed-Compression",
        "Login-IP-Host",
        "Login-Service",
        "Login-TCP-Port",
        "Reply-Message",
        "Callback-Number",
        "Callback-Id",
        "Framed-Route",
        "Framed-IPX-Network",
        "State",
        "Class",
        "Vendor-Specific",
        "Session-Timeout",
        "Idle-Timeout",
        "Termination-Action",
        "Called-Station-Id",
        "Calling-Station-Id",
        "NAS-Identifier",
        "Proxy-State",
        "Login-LAT-Service",
        "Login-LAT-Node",
        "Login-LAT-Group",
        "Framed-AppleTalk-Link",
        "Framed-AppleTalk-Network",
        "Framed-AppleTalk-Zone",
        "CHAP-Challenge",
        "NAS-Port-Type",
        "Port-Limit",
        "Login-LAT-Port",
        # RFC 2866
        "Acct-Status-Type",
        "Acct-Delay-Time",
        "Acct-Input-Octets",
        "Acct-Output-Octets",
        "Acct-Session-Id",
        "Acct-Authentic",
        "Acct-Session-Time",
        "Acct-Input-Packets",
        "Acct-Output-Packets",
        "Acct-Terminate-Cause",
        "Acct-Multi-Session-Id",
        "Acct-Link-Count",
        # RFC 2867
        "Acct-Tunnel-Connection",
        "Acct-Tunnel-Packets-Lost",
        # RFC 2868
        "Tunnel-Type",
        "Tunnel-Medium-Type",
        "Tunnel-Client-Endpoint",
        "Tunnel-Server-Endpoint",
        "Tunnel-Password",
        "Tunnel-Private-Group-Id",
        "Tunnel-Assignment-Id",
        "Tunnel-Preference",
        "Tunnel-Client-Auth-Id",
        "Tunnel-Server-Auth-Id",
        # RFC 2869
        "Acct-Input-Gigawords",
        "Acct-Output-Gigawords",
        "Event-Timestamp",
        "ARAP-Password",
        "ARAP-Features",
        "ARAP-Zone-Access",
        "ARAP-Security",
        "ARAP-Security-Data",
        "Password-Retry",
        "Prompt",
        "Connect-Info",
        "Configuration-Token",
        "EAP-Message",
        "Message-Authenticator",
        "ARAP-Challenge-Response",
        "Acct-Interim-Interval",
        "NAS-Port-Id",
        "Framed-Pool",
        # RFC 3162
        "NAS-IPv6-Address",
        "Framed-Interface-Id",
        "Framed-IPv6-Prefix",
        "Login-IPv6-Host",
        "Framed-IPv6-Route",
        "Framed-IPv6-Pool",
        # RFC 3576
        "Error-Cause",
        # RFC 4372
        "Chargeable-User-Identity",
        # RFC 4675
        "Egress-VLANID",
        "Ingress-Filters",
        "Egress-VLAN-Name",
        "User-Priority-Table",
        # RFC 4818
        "Delegated-IPv6-Prefix",
        # RFC 4849
        "NAS-Filter-Rule",
        # RFC 5580
        "Operator-Name",
        "Location-Information",
        "Location-Data",
        "Basic-Location-Policy-Rules",
        "Extended-Location-Policy-Rules",
        "Location-Capable",
        "Requested-Location-Info",
        # RFC 6572
        "Service-Selection",
        "Mobile-Node-Identifier",
        # RFC 6911
        "Framed-IPv6-Address",
        "DNS-Server-IPv6-Address",
        "Route-IPv6-Information",
        "Delegated-IPv6-Prefix-Pool",
        "Stateful-IPv6-Address-Pool",
        # Compat aliases
        "Client-Id",
        "Client-Port-Id",
        "User-Service-Type",
        "Framed-Address",
        "Framed-Netmask",
        "Framed-Filter-Id",
        "Login-Host",
        "Login-Port",
        "Old-Password",
        "Port-Message",
        "Dialback-No",
        "Dialback-Name",
        "Challenge-State",
    }


# Loaded once at module import time.
_BASE_RADIUS_ATTRIBUTES: Set[str] = _load_base_attribute_names()


def _convert_v4_types(content: str) -> tuple[str, int]:
    """Replace FreeRADIUS 4.x data-types with their 3.x equivalents
    and strip v4-only keywords (ALIAS, STRUCT, MEMBER, FLAGS).

    Returns (converted_content, number_of_replacements).
    """
    count = 0

    def _replacer(m: re.Match) -> str:
        nonlocal count
        old_type = m.group(2)
        new_type = TYPE_MAP_V4_TO_V3.get(old_type.lower(), old_type)
        count += 1
        return m.group(1) + new_type + m.group(3)

    converted = _ATTR_RE.sub(_replacer, content)

    # Strip lines with FreeRADIUS 4.x-only keywords (ALIAS, STRUCT, etc.)
    # These cause parse errors on FreeRADIUS 3.x.
    lines = converted.splitlines(keepends=True)
    cleaned: list[str] = []
    stripped_count = 0
    for line in lines:
        s = line.strip()
        if s and not s.startswith("#"):
            first_word = s.split()[0].upper()
            if first_word in _V4_ONLY_KEYWORDS:
                stripped_count += 1
                # Replace with a comment so line numbers stay meaningful
                cleaned.append(f"# [removed v4 keyword] {s}\n")
                continue
        cleaned.append(line)

    if stripped_count:
        count += stripped_count
        logger.info("Stripped %d FreeRADIUS 4.x keyword line(s)", stripped_count)

    return "".join(cleaned), count


def _find_duplicate_attributes(content: str) -> List[str]:
    """Check if a dictionary file redefines any standard RADIUS attributes.

    Checks ALL attributes (both top-level and vendor-specific) because
    FreeRADIUS 3.x rejects duplicate attribute *names* globally,
    even when the duplicate is inside a BEGIN-VENDOR block.

    Returns a list of duplicate attribute names found.
    """
    duplicates: List[str] = []

    for line in content.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue

        m = _ATTR_NAME_RE.match(stripped)
        if m:
            attr_name = m.group(1)
            if attr_name in _BASE_RADIUS_ATTRIBUTES:
                duplicates.append(attr_name)

    return duplicates


def _extract_vendor_ids(content: str) -> Dict[int, str]:
    """Parse all VENDOR declarations from dictionary content.

    Supports both formats used in practice:
      VENDOR  <name>  <id>    (FreeRADIUS format)

    Returns a dict mapping vendor_id -> vendor_name.
    """
    vendors: Dict[int, str] = {}
    for m in _VENDOR_RE.finditer(content):
        name, raw_id = m.group(1), m.group(2)
        try:
            vid = int(raw_id)
            vendors[vid] = name
        except ValueError:
            pass
    return vendors


def _check_vendor_id_collision(
    new_content: str,
    existing_files: List[str],
    skip_filename: str = "",
) -> List[str]:
    """Check if new_content declares a vendor ID already in use.

    Compares against:
    1. Built-in FreeRADIUS vendor IDs (_BUILTIN_VENDOR_IDS).
    2. Vendor IDs declared in every existing custom dictionary file
       (skip_filename is excluded to allow overwrites on edit).

    Returns a list of human-readable collision descriptions.
    """
    new_vendors = _extract_vendor_ids(new_content)
    if not new_vendors:
        return []

    collisions: List[str] = []

    # Check against built-ins
    for vid, vname in new_vendors.items():
        if vid in _BUILTIN_VENDOR_IDS:
            collisions.append(
                f"Vendor ID {vid} ({vname}) conflicts with built-in "
                f"FreeRADIUS vendor '{_BUILTIN_VENDOR_IDS[vid]}'. "
                f"Use this vendor's official dictionary or rename your vendor."
            )

    # Check against existing custom dictionaries
    for filepath in existing_files:
        fname = os.path.basename(filepath)
        if fname == skip_filename:
            continue
        try:
            with open(filepath, "r", encoding="utf-8", errors="replace") as fh:
                existing_content = fh.read()
            existing_vendors = _extract_vendor_ids(existing_content)
            for vid, vname in new_vendors.items():
                if vid in existing_vendors:
                    collisions.append(
                        f"Vendor ID {vid} ({vname}) is already declared in "
                        f"'{fname}' as vendor '{existing_vendors[vid]}'. "
                        f"Each dictionary must use a unique vendor ID."
                    )
        except OSError:
            pass

    return collisions


# Regex to match BEGIN-VENDOR lines and capture the vendor name.
_BEGIN_VENDOR_RE = re.compile(r"^\s*BEGIN-VENDOR\s+(\S+)", re.IGNORECASE)

# Regex to match ATTRIBUTE lines and capture name, code, type, and optional extras.
_ATTR_FULL_RE = re.compile(r"^(\s*ATTRIBUTE\s+)(\S+)(\s+\d+\s+\S+.*)$", re.IGNORECASE)


def _auto_prefix_vendor_attributes(content: str) -> tuple[str, List[str]]:
    """Auto-prefix vendor-specific attributes with the vendor name.

    FreeRADIUS 3.x enforces globally unique attribute names.  Vendor
    dictionaries that use generic names (e.g. ``NAS-Port`` or
    ``Service-Name`` inside ``BEGIN-VENDOR Cisco``) will collide with
    the base dictionary or other loaded dictionaries.

    This function prefixes every vendor attribute that does NOT already
    start with ``<Vendor>-`` with the vendor name, matching the official
    FreeRADIUS convention (e.g. ``NAS-Port`` → ``Cisco-NAS-Port``).

    VALUE lines referencing renamed attributes are also updated.

    Returns (fixed_content, list_of_renames_applied).
    """
    lines = content.splitlines(keepends=True)
    current_vendor: str | None = None
    renames: List[str] = []
    # Map old_name -> new_name for VALUE line fixups
    rename_map: Dict[str, str] = {}

    for i, line in enumerate(lines):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue

        upper = stripped.upper()
        if upper.startswith("BEGIN-VENDOR"):
            m = _BEGIN_VENDOR_RE.match(stripped)
            if m:
                current_vendor = m.group(1)
            continue
        if upper.startswith("END-VENDOR"):
            current_vendor = None
            continue

        if current_vendor:
            prefix = f"{current_vendor}-"

            # Handle ATTRIBUTE lines
            m = _ATTR_FULL_RE.match(line)
            if m:
                attr_name = m.group(2)
                # Only rename if the attribute doesn't already have the vendor prefix
                if not attr_name.startswith(prefix):
                    new_name = f"{prefix}{attr_name}"
                    lines[i] = m.group(1) + new_name + m.group(3)
                    if not lines[i].endswith("\n") and line.endswith("\n"):
                        lines[i] += "\n"
                    renames.append(f"{attr_name} -> {new_name}")
                    rename_map[attr_name] = new_name
                continue

            # Handle VALUE lines: VALUE <attr-name> <value-name> <number>
            if upper.startswith("VALUE"):
                parts = stripped.split()
                if len(parts) >= 4:
                    val_attr = parts[1]
                    if val_attr in rename_map:
                        # Replace the old attribute name with the new one
                        lines[i] = line.replace(val_attr, rename_map[val_attr], 1)

    return "".join(lines), renames


class DictionaryService:
    def __init__(self, dict_dir: str = "dictionaries"):
        self.dict_dir = dict_dir
        if not os.path.exists(self.dict_dir):
            os.makedirs(self.dict_dir)
        self._dictionary = None

    def _validate_path(self, filename: str) -> Path:
        """Validate that filename stays within dict_dir to prevent path traversal."""
        from fastapi import HTTPException

        base = Path(self.dict_dir).resolve()
        target = (base / filename).resolve()
        if not str(target).startswith(str(base) + os.sep) and target != base:
            raise HTTPException(
                status_code=400, detail="Invalid filename: path traversal detected"
            )
        return target

    @property
    def dictionary(self):
        if self._dictionary is None:
            self.load()
        return self._dictionary

    def load(self):
        """(Re)load every dictionary file into a single pyrad Dictionary."""
        self._dictionary = Dictionary()
        self.attribute_sources = {}

        if not os.path.exists(self.dict_dir):
            return

        files = sorted(os.listdir(self.dict_dir))

        # Ensure 'dictionary' (standard) is loaded first if present.
        if "dictionary" in files:
            files.remove("dictionary")
            files.insert(0, "dictionary")

        for filename in files:
            filepath = os.path.join(self.dict_dir, filename)
            if not os.path.isfile(filepath):
                continue
            try:
                temp_dict = Dictionary()
                temp_dict.ReadDictionary(filepath)

                for attr_name in temp_dict.attributes:
                    self.attribute_sources[attr_name] = filename

                self._dictionary.ReadDictionary(filepath)

            except Exception as e:
                print(f"Error loading dictionary {filename}: {e}")

    # ---- file helpers ----

    def rename_file(self, old_name: str, new_name: str) -> bool:
        self._validate_path(old_name)
        self._validate_path(new_name)
        old_path = os.path.join(self.dict_dir, old_name)
        new_path = os.path.join(self.dict_dir, new_name)

        if not os.path.exists(old_path):
            raise FileNotFoundError(f"Source file {old_name} not found")
        if os.path.exists(new_path):
            raise FileExistsError(f"Destination file {new_name} already exists")

        os.rename(old_path, new_path)
        self.load()
        return True

    def delete_file(self, filename: str) -> bool:
        """Delete a dictionary file and reload."""
        self._validate_path(filename)
        filepath = os.path.join(self.dict_dir, filename)
        if not os.path.exists(filepath):
            raise FileNotFoundError(f"File {filename} not found")
        os.unlink(filepath)
        self.load()
        return True

    def list_files(self) -> List[str]:
        if not os.path.exists(self.dict_dir):
            return []
        return [
            f
            for f in os.listdir(self.dict_dir)
            if os.path.isfile(os.path.join(self.dict_dir, f))
        ]

    def read_content(self, filename: str) -> str:
        """Return the raw text content of a dictionary file."""
        self._validate_path(filename)
        filepath = os.path.join(self.dict_dir, filename)
        if not os.path.exists(filepath):
            raise FileNotFoundError(f"File {filename} not found")
        with open(filepath, "r", encoding="utf-8", errors="replace") as fh:
            return fh.read()

    def write_content(self, filename: str, content: str) -> dict:
        """Validate and overwrite a dictionary file with new content.

        Auto-converts FreeRADIUS 4.x types before validation.
        NOTE: Auto-prefix disabled - dictionaries uploaded via UI must keep
        their original attribute names without modification.
        Rejects files that still redefine standard RADIUS attributes
        at the top level after auto-rename.
        Returns {"conversions": int, "renames": list} with fixes applied.
        """
        self._validate_path(filename)
        converted, conversions = _convert_v4_types(content)

        # NOTE: Auto-prefix disabled - dictionaries uploaded via UI must keep
        # their original attribute names without modification.
        renames = []

        # Check for remaining duplicate attributes (top-level, not auto-fixable)
        duplicates = _find_duplicate_attributes(converted)
        if duplicates:
            raise ValueError(
                f"Dictionary redefines standard RADIUS attribute(s) that "
                f"already exist in the FreeRADIUS base dictionary: "
                f"{', '.join(duplicates)}. "
                f"Remove these attributes — they are already built-in."
            )

        # Check for vendor ID collisions against built-ins and existing dictionaries.
        # Use skip_filename=filename so editing an existing file doesn't reject itself.
        existing = [
            os.path.join(self.dict_dir, f)
            for f in os.listdir(self.dict_dir)
            if os.path.isfile(os.path.join(self.dict_dir, f))
        ]
        collisions = _check_vendor_id_collision(
            converted, existing, skip_filename=filename
        )
        if collisions:
            raise ValueError(
                "Vendor ID conflict detected — FreeRADIUS would fail to start: "
                + " | ".join(collisions)
            )

        # Validate by writing to a temp file and parsing with pyrad
        with tempfile.NamedTemporaryFile(
            delete=False, mode="w", encoding="utf-8", suffix=".dict"
        ) as tmp:
            tmp.write(converted)
            tmp_path = tmp.name

        try:
            test_dict = Dictionary()
            test_dict.ReadDictionary(tmp_path)
        except Exception as e:
            os.unlink(tmp_path)
            raise ValueError(f"Invalid dictionary format: {e}")

        # Write validated content to the real file
        dest_path = os.path.join(self.dict_dir, filename)
        shutil.move(tmp_path, dest_path)
        self.load()
        return {"conversions": conversions, "renames": renames}

    def validate_and_save(self, filename: str, content: bytes) -> dict:
        """Validate an uploaded dictionary file, auto-converting v4 types.

        Auto-renames vendor attributes that collide with standard names.
        Rejects files that still redefine standard RADIUS attributes
        at the top level after auto-rename.
        Rejects files whose vendor ID collides with a built-in or existing
        custom dictionary to prevent FreeRADIUS startup failures.
        Returns {"conversions": int, "renames": list}.
        """
        self._validate_path(filename)
        text = content.decode("utf-8", errors="replace")
        converted, conversions = _convert_v4_types(text)

        # NOTE: Auto-prefix disabled - dictionaries uploaded via UI must keep
        # their original attribute names without modification.
        # Original logic that auto-prefixed vendor attributes has been removed.
        renames = []

        # Check for remaining duplicate attributes (top-level, not auto-fixable)
        duplicates = _find_duplicate_attributes(converted)
        if duplicates:
            raise ValueError(
                f"Dictionary redefines standard RADIUS attribute(s) that "
                f"already exist in the FreeRADIUS base dictionary: "
                f"{', '.join(duplicates)}. "
                f"Remove these attributes — they are already built-in."
            )

        # Check for vendor ID collisions against built-ins and existing dictionaries.
        # Pass filename so an overwrite of the same file isn't falsely rejected.
        existing = [
            os.path.join(self.dict_dir, f)
            for f in os.listdir(self.dict_dir)
            if os.path.isfile(os.path.join(self.dict_dir, f))
        ]
        collisions = _check_vendor_id_collision(
            converted, existing, skip_filename=filename
        )
        if collisions:
            raise ValueError(
                "Vendor ID conflict detected — FreeRADIUS would fail to start: "
                + " | ".join(collisions)
            )

        with tempfile.NamedTemporaryFile(
            delete=False, mode="w", encoding="utf-8", suffix=".dict"
        ) as tmp:
            tmp.write(converted)
            tmp_path = tmp.name

        try:
            test_dict = Dictionary()
            test_dict.ReadDictionary(tmp_path)

            dest_path = os.path.join(self.dict_dir, filename)
            shutil.move(tmp_path, dest_path)

            self.load()
            return {"conversions": conversions, "renames": renames}
        except Exception as e:
            os.unlink(tmp_path)
            raise ValueError(f"Invalid dictionary format: {e}")

    # ---- attribute queries ----

    def get_attributes(self, source_file: str = None) -> List[Dict]:
        attrs = []
        if not hasattr(self.dictionary, "attributes"):
            return []

        for name in self.dictionary.attributes:
            attr = self.dictionary.attributes[name]

            attr_source = self.attribute_sources.get(name, "Unknown/Standard")
            if source_file and attr_source != source_file:
                continue

            vendor_name = "IETF (Standard)"
            try:
                if hasattr(attr, "vendor") and attr.vendor:
                    vendor_name = (
                        str(attr.vendor.name)
                        if hasattr(attr.vendor, "name")
                        else str(attr.vendor)
                    )
            except Exception:
                vendor_name = "Unknown Vendor"

            attrs.append(
                {
                    "name": attr.name,
                    "code": attr.code,
                    "type": attr.type,
                    "vendor": vendor_name,
                    "dictionary": attr_source,
                }
            )
        return sorted(attrs, key=lambda x: x["name"])

    def get_values(self, attribute_name: str) -> List[Dict]:
        if attribute_name not in self.dictionary:
            return []
        attr = self.dictionary[attribute_name]
        return [{"name": k, "value": v} for k, v in attr.values.items()]


dictionary_service = DictionaryService()

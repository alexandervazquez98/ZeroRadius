"""
Unit tests for dictionary_loader._parse_builtin_attr_grep_output.

No Docker, no filesystem, no DB required — purely tests the regex parser
that converts ``grep -rE`` output from the radius-server container into
attribute dicts compatible with DictionaryService.get_attributes().

Coverage targets (dictionary_loader.py was at 34%):
- Basic ATTRIBUTE parsing
- BEGIN-VENDOR / END-VENDOR tracking per file
- IETF (Standard) fallback when attribute is outside any vendor block
- Deduplication across files (first occurrence wins)
- Graceful handling of blank lines, comments, and unknown keywords
- [Sistema] prefix in the dictionary field
"""

import pytest
from app.services.dictionary_loader import _parse_builtin_attr_grep_output


# ---------------------------------------------------------------------------
# Minimal grep output snippets used across tests
# ---------------------------------------------------------------------------

_CISCO_GREP_OUTPUT = """\
/usr/share/freeradius/dictionary.cisco:VENDOR\t\tCisco\t\t9
/usr/share/freeradius/dictionary.cisco:BEGIN-VENDOR\tCisco
/usr/share/freeradius/dictionary.cisco:ATTRIBUTE\tCisco-AVPair\t\t1\tstring
/usr/share/freeradius/dictionary.cisco:ATTRIBUTE\tCisco-NAS-Port\t\t2\tinteger
/usr/share/freeradius/dictionary.cisco:END-VENDOR\tCisco
"""

_MICROSOFT_GREP_OUTPUT = """\
/usr/share/freeradius/dictionary.microsoft:VENDOR\t\tMicrosoft\t\t311
/usr/share/freeradius/dictionary.microsoft:BEGIN-VENDOR\tMicrosoft
/usr/share/freeradius/dictionary.microsoft:ATTRIBUTE\tMS-CHAP-Response\t\t1\toctets
/usr/share/freeradius/dictionary.microsoft:ATTRIBUTE\tMS-CHAP-Challenge\t\t11\toctets
/usr/share/freeradius/dictionary.microsoft:END-VENDOR\tMicrosoft
"""

# Standard (IETF) attribute — outside any BEGIN-VENDOR block
_IETF_GREP_OUTPUT = """\
/usr/share/freeradius/dictionary:ATTRIBUTE\tUser-Name\t\t1\tstring
/usr/share/freeradius/dictionary:ATTRIBUTE\tUser-Password\t\t2\tstring
/usr/share/freeradius/dictionary:ATTRIBUTE\tService-Type\t\t6\tinteger
"""


class TestParseBuiltinGrepOutput:

    def test_returns_empty_list_on_empty_input(self):
        result = _parse_builtin_attr_grep_output("")
        assert result == []

    def test_returns_empty_list_on_blank_lines_only(self):
        result = _parse_builtin_attr_grep_output("\n\n\n")
        assert result == []

    def test_returns_empty_list_on_comment_lines_only(self):
        grep_out = (
            "/usr/share/freeradius/dictionary.cisco:# This is a comment\n"
            "/usr/share/freeradius/dictionary.cisco:#ATTRIBUTE  ignored 1 string\n"
        )
        result = _parse_builtin_attr_grep_output(grep_out)
        assert result == []

    # -----------------------------------------------------------------------
    # Vendor attribute extraction
    # -----------------------------------------------------------------------

    def test_cisco_attributes_parsed(self):
        result = _parse_builtin_attr_grep_output(_CISCO_GREP_OUTPUT)
        names = [a["name"] for a in result]
        assert "Cisco-AVPair" in names
        assert "Cisco-NAS-Port" in names

    def test_cisco_attributes_vendor_tagged(self):
        result = _parse_builtin_attr_grep_output(_CISCO_GREP_OUTPUT)
        by_name = {a["name"]: a for a in result}
        assert by_name["Cisco-AVPair"]["vendor"] == "Cisco"
        assert by_name["Cisco-NAS-Port"]["vendor"] == "Cisco"

    def test_cisco_attribute_code_is_int(self):
        result = _parse_builtin_attr_grep_output(_CISCO_GREP_OUTPUT)
        by_name = {a["name"]: a for a in result}
        assert by_name["Cisco-AVPair"]["code"] == 1
        assert isinstance(by_name["Cisco-AVPair"]["code"], int)

    def test_cisco_attribute_type_preserved(self):
        result = _parse_builtin_attr_grep_output(_CISCO_GREP_OUTPUT)
        by_name = {a["name"]: a for a in result}
        assert by_name["Cisco-AVPair"]["type"] == "string"
        assert by_name["Cisco-NAS-Port"]["type"] == "integer"

    def test_dictionary_field_has_sistema_prefix(self):
        """[Sistema] prefix distinguishes built-ins from custom dicts in the UI."""
        result = _parse_builtin_attr_grep_output(_CISCO_GREP_OUTPUT)
        by_name = {a["name"]: a for a in result}
        assert by_name["Cisco-AVPair"]["dictionary"] == "[Sistema] dictionary.cisco"

    # -----------------------------------------------------------------------
    # IETF (Standard) attributes — outside any vendor block
    # -----------------------------------------------------------------------

    def test_ietf_attributes_parsed(self):
        result = _parse_builtin_attr_grep_output(_IETF_GREP_OUTPUT)
        names = [a["name"] for a in result]
        assert "User-Name" in names
        assert "Service-Type" in names

    def test_ietf_attributes_vendor_is_ietf_standard(self):
        result = _parse_builtin_attr_grep_output(_IETF_GREP_OUTPUT)
        by_name = {a["name"]: a for a in result}
        assert by_name["User-Name"]["vendor"] == "IETF (Standard)"

    def test_ietf_dictionary_field_uses_filename(self):
        result = _parse_builtin_attr_grep_output(_IETF_GREP_OUTPUT)
        by_name = {a["name"]: a for a in result}
        assert by_name["User-Name"]["dictionary"] == "[Sistema] dictionary"

    # -----------------------------------------------------------------------
    # Multi-file merge and deduplication
    # -----------------------------------------------------------------------

    def test_merged_cisco_and_microsoft(self):
        combined = _CISCO_GREP_OUTPUT + _MICROSOFT_GREP_OUTPUT
        result = _parse_builtin_attr_grep_output(combined)
        names = [a["name"] for a in result]
        assert "Cisco-AVPair" in names
        assert "MS-CHAP-Response" in names

    def test_deduplication_first_occurrence_wins(self):
        """If the same attribute name appears in two files, first occurrence wins."""
        dup_output = (
            "/usr/share/freeradius/dictionary.a:ATTRIBUTE\tDup-Attr\t1\tstring\n"
            "/usr/share/freeradius/dictionary.b:ATTRIBUTE\tDup-Attr\t2\tinteger\n"
        )
        result = _parse_builtin_attr_grep_output(dup_output)
        dup_attrs = [a for a in result if a["name"] == "Dup-Attr"]
        assert len(dup_attrs) == 1
        # First file wins
        assert dup_attrs[0]["dictionary"] == "[Sistema] dictionary.a"
        assert dup_attrs[0]["type"] == "string"

    # -----------------------------------------------------------------------
    # BEGIN-VENDOR / END-VENDOR tracking per file
    # -----------------------------------------------------------------------

    def test_vendor_context_resets_after_end_vendor(self):
        """ATTRIBUTE lines after END-VENDOR should be tagged as IETF (Standard)."""
        grep_out = (
            "/usr/share/freeradius/dictionary.cisco:BEGIN-VENDOR\tCisco\n"
            "/usr/share/freeradius/dictionary.cisco:ATTRIBUTE\tCisco-Inside\t1\tstring\n"
            "/usr/share/freeradius/dictionary.cisco:END-VENDOR\tCisco\n"
            "/usr/share/freeradius/dictionary.cisco:ATTRIBUTE\tAfter-Vendor\t2\tstring\n"
        )
        result = _parse_builtin_attr_grep_output(grep_out)
        by_name = {a["name"]: a for a in result}
        assert by_name["Cisco-Inside"]["vendor"] == "Cisco"
        assert by_name["After-Vendor"]["vendor"] == "IETF (Standard)"

    def test_two_files_independent_vendor_contexts(self):
        """Vendor context for file A must not bleed into file B."""
        grep_out = (
            # file A opens a Cisco block but never closes it
            "/usr/share/freeradius/dictionary.cisco:BEGIN-VENDOR\tCisco\n"
            "/usr/share/freeradius/dictionary.cisco:ATTRIBUTE\tCisco-AVPair\t1\tstring\n"
            # file B has an IETF attribute — should NOT inherit Cisco vendor
            "/usr/share/freeradius/dictionary.rfc:ATTRIBUTE\tUser-Name\t1\tstring\n"
        )
        result = _parse_builtin_attr_grep_output(grep_out)
        by_name = {a["name"]: a for a in result}
        assert by_name["Cisco-AVPair"]["vendor"] == "Cisco"
        assert by_name["User-Name"]["vendor"] == "IETF (Standard)"

    # -----------------------------------------------------------------------
    # Malformed / edge-case input
    # -----------------------------------------------------------------------

    def test_lines_without_colon_are_skipped(self):
        result = _parse_builtin_attr_grep_output("ATTRIBUTE  Something  1  string\n")
        assert result == []

    def test_attribute_line_without_enough_fields_is_skipped(self):
        # Missing type field
        grep_out = "/usr/share/freeradius/dictionary.x:ATTRIBUTE  Broken  1\n"
        result = _parse_builtin_attr_grep_output(grep_out)
        assert result == []

    def test_vendor_declaration_line_does_not_produce_attribute(self):
        """VENDOR lines should not appear in the output."""
        grep_out = "/usr/share/freeradius/dictionary.cisco:VENDOR\tCisco\t9\n"
        result = _parse_builtin_attr_grep_output(grep_out)
        assert result == []

    def test_result_contains_required_keys(self):
        result = _parse_builtin_attr_grep_output(_CISCO_GREP_OUTPUT)
        assert len(result) > 0
        for attr in result:
            assert "name" in attr
            assert "code" in attr
            assert "type" in attr
            assert "vendor" in attr
            assert "dictionary" in attr

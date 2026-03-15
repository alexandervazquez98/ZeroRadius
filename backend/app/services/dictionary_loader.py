import os
import re
import shutil
import tempfile
from pyrad.dictionary import Dictionary, ParseError
from typing import List, Dict

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


def _convert_v4_types(content: str) -> tuple[str, int]:
    """Replace FreeRADIUS 4.x data-types with their 3.x equivalents.

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
    return converted, count


class DictionaryService:
    def __init__(self, dict_dir: str = "dictionaries"):
        self.dict_dir = dict_dir
        if not os.path.exists(self.dict_dir):
            os.makedirs(self.dict_dir)
        self._dictionary = None

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
        filepath = os.path.join(self.dict_dir, filename)
        if not os.path.exists(filepath):
            raise FileNotFoundError(f"File {filename} not found")
        with open(filepath, "r", encoding="utf-8", errors="replace") as fh:
            return fh.read()

    def write_content(self, filename: str, content: str) -> dict:
        """Validate and overwrite a dictionary file with new content.

        Auto-converts FreeRADIUS 4.x types before validation.
        Returns {"conversions": int} with the number of type fixes applied.
        """
        converted, conversions = _convert_v4_types(content)

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
        return {"conversions": conversions}

    def validate_and_save(self, filename: str, content: bytes) -> dict:
        """Validate an uploaded dictionary file, auto-converting v4 types.

        Returns {"conversions": int}.
        """
        text = content.decode("utf-8", errors="replace")
        converted, conversions = _convert_v4_types(text)

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
            return {"conversions": conversions}
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

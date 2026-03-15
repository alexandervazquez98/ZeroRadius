import os
import shutil
import tempfile
from pyrad.dictionary import Dictionary, ParseError
from typing import List, Dict

class DictionaryService:
    def __init__(self, dict_dir: str = "dictionaries"):
        self.dict_dir = dict_dir
        if not os.path.exists(self.dict_dir):
            os.makedirs(self.dict_dir)
        self._dictionary = None
        
    @property
    def dictionary(self):
        if self._dictionary is None:
            print("Dictionary is None, loading...")
            self.load()
        return self._dictionary
    
    def load(self):
        # Create empty dict
        print("Initializing Dictionary...")
        self._dictionary = Dictionary()
        self.attribute_sources = {}
        
        # Load all files in directory
        if os.path.exists(self.dict_dir):
            files = sorted(os.listdir(self.dict_dir))
            
            # Ensure 'dictionary' (standard) is loaded first if possible
            if 'dictionary' in files:
                files.remove('dictionary')
                files.insert(0, 'dictionary')

            for filename in files:
                filepath = os.path.join(self.dict_dir, filename)
                if os.path.isfile(filepath):
                    try:
                        # We want to know EVERY attribute inside this file
                        # so we parse it into a temporary dictionary first
                        temp_dict = Dictionary()
                        temp_dict.ReadDictionary(filepath)
                        
                        for attr_name in temp_dict.attributes:
                            # Map attribute to this file
                            # If multiple files define same attr, the last one in 'files' list "wins" 
                            # for the mapping, but they will all be reachable if we filter by file.
                            self.attribute_sources[attr_name] = filename
                        
                        # Now load into the main dictionary
                        self._dictionary.ReadDictionary(filepath)
                            
                    except Exception as e:
                        print(f"Error loading dictionary {filename}: {e}")
        
        # Check removed

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

    def list_files(self) -> List[str]:
        if not os.path.exists(self.dict_dir):
            return []
        return [f for f in os.listdir(self.dict_dir) if os.path.isfile(os.path.join(self.dict_dir, f))]

    def validate_and_save(self, filename: str, content: bytes) -> bool:
        # 1. Create temp file
        with tempfile.NamedTemporaryFile(delete=False, mode='wb') as tmp:
            tmp.write(content)
            tmp_path = tmp.name
            
        try:
            # 2. Try to parse with fresh Dictionary
            # We assume it should parse either standalone or extending standard
            # To be safe, we try parsing it into a dict that already has standard attrs if needed,
            # but for strict validation of syntax, a clean dict is better to catch format errors.
            test_dict = Dictionary()
            test_dict.ReadDictionary(tmp_path)
            
            # 3. If success, move to dict dir
            dest_path = os.path.join(self.dict_dir, filename)
            shutil.move(tmp_path, dest_path)
            
            # 4. Reload to apply changes
            self.load()
            return True
        except Exception as e:
            # Clean up temp
            os.unlink(tmp_path)
            raise ValueError(f"Invalid dictionary format: {str(e)}")

    def get_attributes(self, source_file: str = None) -> List[Dict]:
        attrs = []
        # Inspect pyrad dictionary safe iteration
        # Access underlying dict directly to avoid __getitem__ issues
        if not hasattr(self.dictionary, 'attributes'):
             return []
             
        for name in self.dictionary.attributes:
            attr = self.dictionary.attributes[name]
            
            # If source_file is provided, only return attrs from that file
            attr_source = self.attribute_sources.get(name, "Unknown/Standard")
            if source_file and attr_source != source_file:
                continue

            # Extract vendor name reliably
            vendor_name = "IETF (Standard)"
            try:
                if hasattr(attr, 'vendor') and attr.vendor:
                     # attr.vendor might be a string or object depending on pyrad version/context
                     vendor_name = str(attr.vendor.name) if hasattr(attr.vendor, 'name') else str(attr.vendor)
            except Exception:
                vendor_name = "Unknown Vendor"

            attrs.append({
                "name": attr.name,
                "code": attr.code,
                "type": attr.type,
                "vendor": vendor_name,
                "dictionary": attr_source
            })
        return sorted(attrs, key=lambda x: x['name'])
    
    def get_values(self, attribute_name: str) -> List[Dict]:
        if attribute_name not in self.dictionary:
            return []
        
        attr = self.dictionary[attribute_name]
        return [{"name": k, "value": v} for k, v in attr.values.items()]

dictionary_service = DictionaryService()

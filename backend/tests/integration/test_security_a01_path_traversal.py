"""Tests A01: Path traversal en DictionaryService."""

import pytest
from fastapi import HTTPException
from app.services.dictionary_loader import DictionaryService


class TestPathTraversal:
    """Verifica que DictionaryService rechaza path traversal."""

    def test_validate_path_traversal_rejected(self, tmp_path):
        """_validate_path debe rechazar filenames con ../"""
        svc = DictionaryService(dict_dir=str(tmp_path))
        with pytest.raises(HTTPException) as exc_info:
            svc._validate_path("../etc/passwd")
        assert exc_info.value.status_code == 400

    def test_validate_path_absolute_rejected(self, tmp_path):
        """_validate_path debe rechazar rutas absolutas."""
        svc = DictionaryService(dict_dir=str(tmp_path))
        with pytest.raises(HTTPException):
            svc._validate_path("/etc/shadow")

    def test_validate_path_valid_filename_ok(self, tmp_path):
        """_validate_path debe aceptar filenames simples válidos."""
        svc = DictionaryService(dict_dir=str(tmp_path))
        # No debe lanzar excepción
        result = svc._validate_path("custom.dict")
        assert result.name == "custom.dict"

    def test_read_content_path_traversal_rejected(self, tmp_path):
        """read_content debe rechazar path traversal con 400."""
        svc = DictionaryService(dict_dir=str(tmp_path))
        with pytest.raises(HTTPException) as exc_info:
            svc.read_content("../../../etc/passwd")
        assert exc_info.value.status_code == 400

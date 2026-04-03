"""Tests A08: límite de tamaño en upload de diccionarios.

El endpoint real es POST /dictionary/upload (confirmado en backend/app/routers/dictionary.py).
El límite está implementado en el router: len(content) > 1_048_576 → 413.
"""

import pytest
import io


class TestUploadSizeLimit:
    """Verifica que el endpoint de upload de diccionarios aplica límite de tamaño."""

    async def test_upload_within_limit_accepted(self, async_client, admin_token):
        """Archivo de ~5KB válido → acepta (no 413).

        Nota: el contenido debe ser un diccionario RADIUS válido para evitar
        error 400/422 por contenido inválido. Usamos un comment block simple
        que pasa la validación de pyrad sin atributos especiales.
        El test solo verifica que NO se retorna 413.
        """
        # Contenido de diccionario RADIUS mínimo y válido
        small_content = b"# Test dictionary\n# Generated for security tests\n" * 100
        resp = await async_client.post(
            "/dictionary/upload",
            files={
                "file": ("test_small.dict", io.BytesIO(small_content), "text/plain")
            },
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        # No debe ser 413 — puede ser 400 si el contenido del dict es rechazado por pyrad,
        # pero la validación de tamaño no debe activarse
        assert resp.status_code != 413

    async def test_upload_over_limit_rejected(self, async_client, admin_token):
        """Archivo de >1MB → 413 File too large."""
        large_content = b"A" * (1_048_576 + 1)  # 1MB + 1 byte
        resp = await async_client.post(
            "/dictionary/upload",
            files={"file": ("large.dict", io.BytesIO(large_content), "text/plain")},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 413

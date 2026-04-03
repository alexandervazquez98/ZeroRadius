"""Tests A07: timing oracle mitigado en login."""

import pytest
import time


class TestTimingOracle:
    """Verifica que el timing del login no revela si un usuario existe."""

    async def test_login_timing_oracle_mitigated(self, async_client):
        """Tiempo de respuesta para usuario inexistente ≈ usuario con password incorrecto.

        El código de auth.py usa dummy bcrypt en ambos casos (usuario no existe
        y usuario existe con password incorrecto) para igualar los tiempos.
        Permitimos hasta 500ms de diferencia para entornos CI lentos.
        """
        N = 5

        # Measure: nonexistent user
        nonexistent_times = []
        for _ in range(N):
            start = time.perf_counter()
            await async_client.post(
                "/auth/token",
                data={"username": "nonexistent_user_xyz_abc", "password": "AnyPass1!"},
            )
            nonexistent_times.append(time.perf_counter() - start)

        # Measure: existing user, wrong password
        wrong_pw_times = []
        for _ in range(N):
            start = time.perf_counter()
            await async_client.post(
                "/auth/token",
                data={"username": "test_superadmin", "password": "WrongPassword999!"},
            )
            wrong_pw_times.append(time.perf_counter() - start)

        avg_nonexistent = sum(nonexistent_times) / N
        avg_wrong_pw = sum(wrong_pw_times) / N
        diff = abs(avg_nonexistent - avg_wrong_pw)

        # Allow up to 500ms difference in test environment (CI can be slow)
        assert diff < 0.5, (
            f"Timing oracle detected: nonexistent_user avg={avg_nonexistent:.3f}s, "
            f"wrong_password avg={avg_wrong_pw:.3f}s, diff={diff:.3f}s"
        )

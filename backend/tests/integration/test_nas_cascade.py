import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.models import AccessPolicyAssignment

_VALID_SECRET = "a" * 32


@pytest.mark.asyncio
class TestNasCascadeUpdate:
    """Regression test for NAS IP cascade updates to access_policy_assignments"""

    async def test_regression_nas_ip_cascade(
        self, async_client, superadmin_token, test_db: AsyncSession
    ):
        # 1. Create a NAS
        payload = {
            "nasname": "10.99.100.1",
            "shortname": "cascade-nas",
            "secret": _VALID_SECRET,
            "type": "other",
        }
        resp = await async_client.post(
            "/nas",
            json=payload,
            headers={"Authorization": f"Bearer {superadmin_token}"},
        )
        assert resp.status_code in (200, 201)
        nas_id = resp.json()["id"]

        # 2. Create an AccessPolicyAssignment linked to this NAS IP
        policy = AccessPolicyAssignment(
            username="test_cascade_user",
            nas_ip="10.99.100.1",
            radius_group="test_group",
            is_active=1,
        )
        test_db.add(policy)
        await test_db.commit()

        # Get initial state to compare target_key
        result = await test_db.execute(
            select(AccessPolicyAssignment).where(
                AccessPolicyAssignment.username == "test_cascade_user"
            )
        )
        db_policy = result.scalars().first()
        assert db_policy.nas_ip == "10.99.100.1"
        old_target_key = db_policy.target_key

        # 3. Update the NAS IP via the API
        update_payload = {
            "nasname": "10.99.200.2",
            "shortname": "cascade-nas-updated",
            "secret": _VALID_SECRET,
            "type": "other",
        }
        resp_put = await async_client.put(
            f"/nas/{nas_id}",
            json=update_payload,
            headers={"Authorization": f"Bearer {superadmin_token}"},
        )
        assert resp_put.status_code == 200

        # 4. Verify the cascade update on AccessPolicyAssignment
        # Refresh the session or execute a new query to get latest DB changes
        test_db.expire_all()
        result_after = await test_db.execute(
            select(AccessPolicyAssignment).where(
                AccessPolicyAssignment.username == "test_cascade_user"
            )
        )
        db_policy_after = result_after.scalars().first()

        assert db_policy_after is not None
        assert db_policy_after.nas_ip == "10.99.200.2"
        # Since target_key depends on nas_ip, it should have been recomputed by the before_update event
        assert db_policy_after.target_key != old_target_key

        # Cleanup
        await test_db.delete(db_policy_after)
        await test_db.commit()

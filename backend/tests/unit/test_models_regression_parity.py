import pytest
from sqlalchemy import UniqueConstraint
from pathlib import Path

from app.models.models import RadAcct, RadPostAuth, AccessPolicyAssignment


def test_radacct_callingstationid_rejects_non_hex_even_with_len_12():
    with pytest.raises(ValueError, match="12 hex chars"):
        RadAcct(callingstationid="zzzzzzzzzzzz")


def test_access_policy_assignments_unique_constraints_match_init_sql():
    table_constraints = {
        c.name: tuple(c.columns.keys())
        for c in AccessPolicyAssignment.__table__.constraints
        if isinstance(c, UniqueConstraint)
    }

    assert table_constraints == {
        "uq_unpm_target_key": ("target_key",),
        "uq_user_nas_ip": ("username", "nas_ip"),
        "uq_user_nas_cat": ("username", "nas_category_id"),
        "uq_user_segment_target": ("username", "segment_id", "segment_target_key"),
    }


def test_access_policy_assignments_segment_fk_ondelete_restrict():
    segment_fk = next(
        fk
        for fk in AccessPolicyAssignment.__table__.c.segment_id.foreign_keys
        if fk.column.table.name == "network_segments"
    )
    assert segment_fk.constraint.name == "fk_unpm_segment"
    assert segment_fk.ondelete == "RESTRICT"


def test_access_policy_assignments_nas_category_fk_target_and_ondelete_set_null():
    category_fk = next(iter(AccessPolicyAssignment.__table__.c.nas_category_id.foreign_keys))

    assert category_fk.constraint.name == "fk_unpm_category"
    assert category_fk.column.table.name == "nas_categories"
    assert category_fk.column.name == "id"
    assert category_fk.ondelete == "SET NULL"


def test_access_policy_assignments_fk_constraints_have_expected_column_composition():
    fk_constraints = {
        fk.name: tuple(fk.column_keys)
        for fk in AccessPolicyAssignment.__table__.foreign_key_constraints
        if fk.name in {"fk_unpm_category", "fk_unpm_segment"}
    }

    assert fk_constraints == {
        "fk_unpm_category": ("nas_category_id",),
        "fk_unpm_segment": ("segment_id",),
    }


@pytest.mark.parametrize(
    ("model_cls", "field_name", "raw_mac"),
    [
        (RadAcct, "callingstationid", "AA:BB:CC:DD:EE:FF"),
        (RadAcct, "callingstationid", "AA-BB-CC-DD-EE-FF"),
        (RadAcct, "callingstationid", "AABB.CCDD.EEFF"),
        (RadAcct, "callingstationid", "AABBCCDDEEFF"),
        (RadPostAuth, "calling_station_id", "AA:BB:CC:DD:EE:FF"),
        (RadPostAuth, "calling_station_id", "AA-BB-CC-DD-EE-FF"),
        (RadPostAuth, "calling_station_id", "AABB.CCDD.EEFF"),
        (RadPostAuth, "calling_station_id", "AABBCCDDEEFF"),
        (AccessPolicyAssignment, "calling_station_id", "AA:BB:CC:DD:EE:FF"),
        (AccessPolicyAssignment, "calling_station_id", "AA-BB-CC-DD-EE-FF"),
        (AccessPolicyAssignment, "calling_station_id", "AABB.CCDD.EEFF"),
        (AccessPolicyAssignment, "calling_station_id", "AABBCCDDEEFF"),
    ],
)
def test_mac_validators_normalize_supported_mac_formats(model_cls, field_name, raw_mac):
    obj = model_cls(**{field_name: raw_mac})
    assert getattr(obj, field_name) == "aabbccddeeff"


@pytest.mark.parametrize(
    ("model_cls", "field_name"),
    [
        (RadAcct, "callingstationid"),
        (RadPostAuth, "calling_station_id"),
        (AccessPolicyAssignment, "calling_station_id"),
    ],
)
def test_mac_validators_reject_non_hex_values(model_cls, field_name):
    with pytest.raises(ValueError, match="12 hex chars"):
        model_cls(**{field_name: "zzzzzzzzzzzz"})


@pytest.mark.parametrize(
    ("model_cls", "field_name", "raw_mac"),
    [
        (RadAcct, "callingstationid", "AA::BB::CC::DD::EE::FF"),
        (RadAcct, "callingstationid", "A:A:B:B:C:C:D:D:E:E:F:F"),
        (RadPostAuth, "calling_station_id", "AA::BB::CC::DD::EE::FF"),
        (RadPostAuth, "calling_station_id", "A:A:B:B:C:C:D:D:E:E:F:F"),
        (AccessPolicyAssignment, "calling_station_id", "AA::BB::CC::DD::EE::FF"),
        (AccessPolicyAssignment, "calling_station_id", "A:A:B:B:C:C:D:D:E:E:F:F"),
    ],
)
def test_mac_validators_reject_malformed_delimiter_patterns(
    model_cls, field_name, raw_mac
):
    with pytest.raises(ValueError, match="12 hex chars"):
        model_cls(**{field_name: raw_mac})


def test_access_policy_assignments_constraints_are_present_in_init_sql_text():
    init_sql = (
        Path(__file__).resolve().parents[2] / ".." / "database" / "init.sql"
    ).read_text(encoding="utf-8").lower()

    assert "unique key uq_unpm_target_key (target_key)" in init_sql
    assert "unique key uq_user_nas_ip  (username, nas_ip)" in init_sql
    assert "unique key uq_user_nas_cat (username, nas_category_id)" in init_sql
    assert "unique key uq_user_segment_target (username, segment_id, segment_target_key)" in init_sql


def test_access_policy_assignments_fk_ondelete_clauses_present_in_init_sql_text():
    init_sql = (
        Path(__file__).resolve().parents[2] / ".." / "database" / "init.sql"
    ).read_text(encoding="utf-8").lower()

    assert (
        "alter table access_policy_assignments add constraint fk_unpm_category "
        "foreign key (nas_category_id) references nas_categories(id) on delete set null"
    ) in init_sql
    assert (
        "alter table access_policy_assignments add constraint fk_unpm_segment "
        "foreign key (segment_id) references network_segments(id) on delete restrict"
    ) in init_sql

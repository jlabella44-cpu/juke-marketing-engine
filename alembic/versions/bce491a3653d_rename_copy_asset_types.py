"""rename_copy_asset_types

Revision ID: bce491a3653d
Revises: 1facbfa43575
Create Date: 2026-03-23 19:04:41.098389

"""
import json
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'bce491a3653d'
down_revision: Union[str, Sequence[str], None] = '1facbfa43575'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()

    # 1. Rename copy_mls → copy_mls_full
    conn.execute(sa.text(
        "UPDATE project_assets SET asset_type = 'copy_mls_full' WHERE asset_type = 'copy_mls'"
    ))

    # 2. Split copy_social rows into copy_facebook + copy_instagram
    rows = conn.execute(sa.text(
        "SELECT id, project_id, content, status FROM project_assets WHERE asset_type = 'copy_social'"
    )).fetchall()

    for row in rows:
        data = json.loads(row.content or '{}')
        for new_type, key in (("copy_facebook", "facebook"), ("copy_instagram", "instagram")):
            conn.execute(sa.text(
                "INSERT INTO project_assets "
                "(id, project_id, asset_type, status, content, created_at, updated_at) "
                "VALUES (gen_random_uuid(), :pid, :atype, :status, :content, now(), now())"
            ), {
                "pid": str(row.project_id),
                "atype": new_type,
                "status": row.status,
                "content": data.get(key, ""),
            })

    # 3. Delete old copy_social rows
    conn.execute(sa.text("DELETE FROM project_assets WHERE asset_type = 'copy_social'"))

    # 4. Add copy_mls_short rows for any project with copy_mls_full (content blank — needs regeneration)
    conn.execute(sa.text(
        "INSERT INTO project_assets (id, project_id, asset_type, status, created_at, updated_at) "
        "SELECT gen_random_uuid(), project_id, 'copy_mls_short', 'pending', now(), now() "
        "FROM project_assets WHERE asset_type = 'copy_mls_full' "
        "AND project_id NOT IN ("
        "  SELECT project_id FROM project_assets WHERE asset_type = 'copy_mls_short'"
        ")"
    ))


def downgrade() -> None:
    conn = op.get_bind()
    # Rename copy_mls_full back to copy_mls
    conn.execute(sa.text(
        "UPDATE project_assets SET asset_type = 'copy_mls' WHERE asset_type = 'copy_mls_full'"
    ))
    # Collapse copy_facebook + copy_instagram back into copy_social (JSON)
    # Note: this is lossy — twitter key will be empty
    fb_rows = conn.execute(sa.text(
        "SELECT project_id, content FROM project_assets WHERE asset_type = 'copy_facebook'"
    )).fetchall()
    for row in fb_rows:
        ig = conn.execute(sa.text(
            "SELECT content FROM project_assets WHERE asset_type = 'copy_instagram' AND project_id = :pid"
        ), {"pid": str(row.project_id)}).scalar()
        social = json.dumps({"facebook": row.content or "", "instagram": ig or "", "twitter": ""})
        conn.execute(sa.text(
            "INSERT INTO project_assets (id, project_id, asset_type, status, content, created_at, updated_at) "
            "VALUES (gen_random_uuid(), :pid, 'copy_social', 'ready', :content, now(), now())"
        ), {"pid": str(row.project_id), "content": social})
    conn.execute(sa.text(
        "DELETE FROM project_assets WHERE asset_type IN ('copy_facebook', 'copy_instagram', 'copy_mls_short')"
    ))

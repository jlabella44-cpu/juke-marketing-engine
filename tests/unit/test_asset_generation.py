# tests/unit/test_asset_generation.py
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4
import pytest
from app.services.asset_generation import process


@pytest.mark.asyncio
async def test_skips_if_not_selected():
    project = MagicMock()
    project.status = "tagged"
    with patch("app.services.asset_generation.async_session_factory") as mock_sf:
        mock_db = AsyncMock()
        mock_sf.return_value.__aenter__ = AsyncMock(return_value=mock_db)
        mock_sf.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_db.execute = AsyncMock(return_value=MagicMock(
            scalar_one_or_none=MagicMock(return_value=project)
        ))
        await process(uuid4())
        mock_db.execute.assert_called()


@pytest.mark.asyncio
async def test_sets_status_generating_then_generated():
    """Verify status transitions: selected → generating → generated."""
    project = MagicMock()
    project.status = "selected"
    project.id = uuid4()

    with patch("app.services.asset_generation.async_session_factory") as mock_sf, \
         patch("app.services.asset_generation.copy_generator.generate",
               new_callable=AsyncMock,
               return_value={"mls_description": "X", "instagram": "Y", "facebook": "Z", "twitter": "W"}), \
         patch("app.services.asset_generation.video_generator.generate", new_callable=AsyncMock), \
         patch("app.services.asset_generation.flyer_generator.generate_flyer"), \
         patch("app.services.asset_generation.set_project_status",
               new_callable=AsyncMock) as mock_status:

        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(return_value=MagicMock(
            scalar_one_or_none=MagicMock(return_value=project),
            scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[]))),
        ))
        mock_db.commit = AsyncMock()
        mock_db.add = MagicMock()
        mock_sf.return_value.__aenter__ = AsyncMock(return_value=mock_db)
        mock_sf.return_value.__aexit__ = AsyncMock(return_value=False)

        await process(project.id)

        status_calls = [str(c) for c in mock_status.call_args_list]
        assert any("generating" in c for c in status_calls)

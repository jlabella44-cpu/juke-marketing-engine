# tests/unit/test_dropbox_storage.py
from unittest.mock import MagicMock, patch, AsyncMock
from uuid import uuid4
import pytest
from app.services.dropbox_storage import upload_assets


@pytest.mark.asyncio
async def test_upload_assets_uploads_ready_assets():
    project_id = uuid4()

    video_asset = MagicMock()
    video_asset.asset_type = "video"
    video_asset.status = "ready"
    video_asset.file_path = "/tmp/test/video.mp4"
    video_asset.content = None
    video_asset.id = uuid4()

    copy_asset = MagicMock()
    copy_asset.asset_type = "copy_mls"
    copy_asset.status = "ready"
    copy_asset.file_path = None
    copy_asset.content = "Beautiful home description"
    copy_asset.id = uuid4()

    with patch("app.services.dropbox_storage.async_session_factory") as mock_sf, \
         patch("app.services.dropbox_storage._get_dropbox_client") as mock_client, \
         patch("builtins.open", MagicMock()), \
         patch("pathlib.Path.exists", return_value=True):

        mock_dbx = MagicMock()
        mock_dbx.files_upload = MagicMock()
        mock_client.return_value = mock_dbx

        project = MagicMock()
        project.slug = "4514-w-72nd-st"

        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(return_value=MagicMock(
            scalar_one_or_none=MagicMock(return_value=project),
            scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[video_asset, copy_asset]))),
        ))
        mock_db.commit = AsyncMock()
        mock_sf.return_value.__aenter__ = AsyncMock(return_value=mock_db)
        mock_sf.return_value.__aexit__ = AsyncMock(return_value=False)

        await upload_assets(project_id)
        mock_dbx.files_upload.assert_called()

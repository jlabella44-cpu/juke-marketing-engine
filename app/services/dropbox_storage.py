# app/services/dropbox_storage.py
# SKELETON — Phase 2 full implementation
# Interfaces defined; bodies raise NotImplementedError with clear TODO comments

from uuid import UUID


def upload_source(project_id: UUID) -> None:
    """
    Upload all source photos for a project to Dropbox.

    TODO Phase 2:
    - Create Dropbox folder: {DROPBOX_ROOT_FOLDER}/{address}/01_Source_Photos/
    - Upload all photos from temp_dir using ThreadPoolExecutor(max_workers=4)
    - Chunked upload for files > 150MB
    - AuthError handling: refresh token once; second AuthError → FAILED + CRITICAL log
    - RateLimitError: exponential backoff (NOT FAILED)
    """
    raise NotImplementedError("Dropbox upload — Phase 2")


def upload_selected(project_id: UUID) -> None:
    """
    Upload selected photos for a project to Dropbox.

    TODO Phase 2:
    - Upload selected photos to {DROPBOX_ROOT_FOLDER}/{address}/02_Selected_Photos/
    - Same parallelism and error handling as upload_source
    - ThreadPoolExecutor(max_workers=4) for parallel file uploads
    - Chunked upload for individual files > 150MB
    - AuthError handling: refresh token once; second AuthError → FAILED + CRITICAL
    - RateLimitError: exponential backoff
    """
    raise NotImplementedError("Dropbox selected upload — Phase 2")

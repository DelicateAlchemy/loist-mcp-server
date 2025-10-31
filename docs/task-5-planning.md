# Planning for Task 5: Implement Audio Storage and Management

This document outlines the plan for implementing the audio storage and management module.

## 1. Module Overview

The goal is to create a robust module that handles storing audio files and their associated thumbnails in Google Cloud Storage (GCS). This includes generating unique identifiers, organizing files within GCS, handling uploads with retries, and cleaning up temporary files.

## 2. Key Implementation Steps

Based on the task details and subtasks, the implementation will be broken down as follows:

### 2.1. GCS Client and Configuration

*   A dedicated GCS client will be used to interact with Google Cloud Storage.
*   The GCS bucket name will be managed through the application's configuration (`src/config.py`).
*   The existing `src/storage/gcs_client.py` will be leveraged and extended if necessary.

### 2.2. File Naming and Organization

*   **Unique ID Generation:** A UUID will be generated for each new audio file to serve as its unique identifier.
*   **Directory Structure:** Files will be organized in GCS under a structure like `audio/{audio_id}/`, where `audio_id` is the generated UUID.
    *   The audio file will be stored as `audio/{audio_id}/audio.<ext>`.
    *   The thumbnail will be stored as `audio/{audio_id}/thumbnail.jpg`.

### 2.3. Upload Logic

*   **Core Upload Function:** A function `upload_to_gcs` will handle the low-level upload of a single file to a specified GCS blob.
*   **Orchestration Function:** A higher-level function `store_audio_file` will orchestrate the entire process:
    1.  Generate a unique `audio_id`.
    2.  Define the GCS destination paths for the audio and thumbnail.
    3.  Call `upload_to_gcs` for the audio file.
    4.  If a thumbnail is provided, call `upload_to_gcs` for the thumbnail.
    5.  Implement retry logic for uploads to handle transient network issues.
    6.  Return the GCS paths and the `audio_id`.

### 2.4. Error Handling and Retries

*   The `google-cloud-storage` library has built-in retry mechanisms, but we will wrap upload calls in a custom retry decorator (e.g., using the `tenacity` library if available, or a manual loop) for more granular control and logging.
*   Custom exceptions from `src/exceptions.py` will be used to signal upload failures.

### 2.5. Temporary File Cleanup

*   A `try...finally` block will be used to ensure that local temporary files (both audio and thumbnail) are deleted after the upload process is complete, regardless of whether it succeeded or failed.

## 3. Code Structure

*   The primary logic will reside in a new file: `src/storage/storage_manager.py`.
*   The existing `src/storage/gcs_client.py` might be refactored to contain the generic GCS interaction logic.
*   The main server/handler logic will call the `storage_manager` to perform the storage operations.

## 4. Testing Strategy

*   **Unit Tests:**
    *   Mock the `google.cloud.storage` client.
    *   Test the unique ID and path generation logic.
    *   Test that the upload functions are called with the correct parameters.
    *   Test the temporary file cleanup logic (e.g., using `unittest.mock.patch` on `os.unlink`).
    *   Test the retry mechanism by mocking upload failures.
*   **Integration Tests:**
    *   Create a `test_storage_manager.py` in the `tests/` directory.
    *   Use a real (or emulated) GCS bucket to test the end-to-end upload process for various file types.
    *   Verify that files are correctly organized in the bucket.

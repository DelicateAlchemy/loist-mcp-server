"""
Google Cloud Storage client implementation for audio file management.

Provides functionality for:
- Signed URL generation for secure streaming
- File upload/download operations
- Metadata management
- Lifecycle policy enforcement
"""

import datetime
import logging
from pathlib import Path
from typing import Optional, Dict, Any, List
from google.cloud import storage
from google.cloud.exceptions import NotFound, GoogleCloudError
import os

logger = logging.getLogger(__name__)


class GCSClient:
    """Client for interacting with Google Cloud Storage."""
    
    def __init__(
        self,
        bucket_name: Optional[str] = None,
        project_id: Optional[str] = None,
    ):
        """
        Initialize GCS client.
        
        Args:
            bucket_name: Name of the GCS bucket (defaults to env var GCS_BUCKET_NAME)
            project_id: GCP project ID (defaults to env var GCS_PROJECT_ID)
        """
        self.bucket_name = bucket_name or os.getenv("GCS_BUCKET_NAME")
        self.project_id = project_id or os.getenv("GCS_PROJECT_ID")
        
        if not self.bucket_name:
            raise ValueError("Bucket name must be provided or set in GCS_BUCKET_NAME env var")
        
        self._client: Optional[storage.Client] = None
        self._bucket: Optional[storage.Bucket] = None
        
        logger.info(f"Initialized GCS client for bucket: {self.bucket_name}")
    
    @property
    def client(self) -> storage.Client:
        """Get or create storage client."""
        if self._client is None:
            self._client = storage.Client(project=self.project_id)
        return self._client
    
    @property
    def bucket(self) -> storage.Bucket:
        """Get or create bucket reference."""
        if self._bucket is None:
            self._bucket = self.client.bucket(self.bucket_name)
        return self._bucket
    
    def generate_signed_url(
        self,
        blob_name: str,
        expiration_minutes: int = 15,
        method: str = "GET",
        content_type: Optional[str] = None,
        response_disposition: Optional[str] = None,
    ) -> str:
        """
        Generate a signed URL for temporary access to a blob.
        
        Args:
            blob_name: Name/path of the blob in GCS
            expiration_minutes: URL expiration time in minutes (default: 15)
            method: HTTP method (GET, PUT, POST, DELETE)
            content_type: Content-Type header for PUT/POST requests
            response_disposition: Content-Disposition header (e.g., "attachment; filename=audio.mp3")
        
        Returns:
            Signed URL string
        
        Raises:
            NotFound: If blob doesn't exist (for GET requests)
            GoogleCloudError: If URL generation fails
        """
        try:
            blob = self.bucket.blob(blob_name)
            
            # For GET requests, verify blob exists
            if method == "GET" and not blob.exists():
                raise NotFound(f"Blob not found: {blob_name}")
            
            # Build URL parameters
            url_params: Dict[str, Any] = {
                "version": "v4",
                "expiration": datetime.timedelta(minutes=expiration_minutes),
                "method": method,
            }
            
            if content_type:
                url_params["content_type"] = content_type
            
            if response_disposition:
                url_params["response_disposition"] = response_disposition
            
            url = blob.generate_signed_url(**url_params)
            
            logger.info(
                f"Generated signed URL for blob: {blob_name}, "
                f"expires in {expiration_minutes} minutes"
            )
            
            return url
            
        except NotFound:
            logger.error(f"Blob not found: {blob_name}")
            raise
        except GoogleCloudError as e:
            logger.error(f"Failed to generate signed URL for {blob_name}: {e}")
            raise
    
    def upload_file(
        self,
        source_path: Path | str,
        destination_blob_name: str,
        content_type: Optional[str] = None,
        metadata: Optional[Dict[str, str]] = None,
    ) -> storage.Blob:
        """
        Upload a file to GCS.
        
        Args:
            source_path: Local file path to upload
            destination_blob_name: Destination path in GCS bucket
            content_type: MIME type of the file
            metadata: Custom metadata key-value pairs
        
        Returns:
            Uploaded blob object
        
        Raises:
            FileNotFoundError: If source file doesn't exist
            GoogleCloudError: If upload fails
        """
        source_path = Path(source_path)
        
        if not source_path.exists():
            raise FileNotFoundError(f"Source file not found: {source_path}")
        
        try:
            blob = self.bucket.blob(destination_blob_name)
            
            # Set metadata if provided
            if metadata:
                blob.metadata = metadata
            
            # Upload file
            blob.upload_from_filename(
                str(source_path),
                content_type=content_type,
            )
            
            logger.info(
                f"Uploaded file: {source_path} -> gs://{self.bucket_name}/{destination_blob_name}"
            )
            
            return blob
            
        except GoogleCloudError as e:
            logger.error(f"Failed to upload file {source_path}: {e}")
            raise
    
    def delete_file(self, blob_name: str) -> bool:
        """
        Delete a file from GCS.
        
        Args:
            blob_name: Name/path of the blob to delete
        
        Returns:
            True if deleted, False if blob didn't exist
        
        Raises:
            GoogleCloudError: If deletion fails
        """
        try:
            blob = self.bucket.blob(blob_name)
            blob.delete()
            
            logger.info(f"Deleted blob: {blob_name}")
            return True
            
        except NotFound:
            logger.warning(f"Blob not found for deletion: {blob_name}")
            return False
        except GoogleCloudError as e:
            logger.error(f"Failed to delete blob {blob_name}: {e}")
            raise
    
    def get_file_metadata(self, blob_name: str) -> Dict[str, Any]:
        """
        Get metadata for a file in GCS.
        
        Args:
            blob_name: Name/path of the blob
        
        Returns:
            Dictionary containing blob metadata
        
        Raises:
            NotFound: If blob doesn't exist
            GoogleCloudError: If metadata retrieval fails
        """
        try:
            blob = self.bucket.blob(blob_name)
            blob.reload()
            
            metadata = {
                "name": blob.name,
                "size": blob.size,
                "content_type": blob.content_type,
                "created": blob.time_created.isoformat() if blob.time_created else None,
                "updated": blob.updated.isoformat() if blob.updated else None,
                "md5_hash": blob.md5_hash,
                "crc32c": blob.crc32c,
                "generation": blob.generation,
                "metageneration": blob.metageneration,
                "custom_metadata": blob.metadata or {},
            }
            
            logger.debug(f"Retrieved metadata for blob: {blob_name}")
            return metadata
            
        except NotFound:
            logger.error(f"Blob not found: {blob_name}")
            raise
        except GoogleCloudError as e:
            logger.error(f"Failed to get metadata for {blob_name}: {e}")
            raise
    
    def list_files(
        self,
        prefix: Optional[str] = None,
        delimiter: Optional[str] = None,
        max_results: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """
        List files in the bucket.
        
        Args:
            prefix: Filter to files with this prefix (e.g., "audio/")
            delimiter: Directory delimiter (e.g., "/" for directory-like listing)
            max_results: Maximum number of results to return
        
        Returns:
            List of blob metadata dictionaries
        """
        try:
            blobs = self.client.list_blobs(
                self.bucket_name,
                prefix=prefix,
                delimiter=delimiter,
                max_results=max_results,
            )
            
            results = []
            for blob in blobs:
                results.append({
                    "name": blob.name,
                    "size": blob.size,
                    "content_type": blob.content_type,
                    "created": blob.time_created.isoformat() if blob.time_created else None,
                    "updated": blob.updated.isoformat() if blob.updated else None,
                })
            
            logger.info(f"Listed {len(results)} files with prefix: {prefix or 'None'}")
            return results
            
        except GoogleCloudError as e:
            logger.error(f"Failed to list files: {e}")
            raise
    
    def file_exists(self, blob_name: str) -> bool:
        """
        Check if a file exists in GCS.
        
        Args:
            blob_name: Name/path of the blob
        
        Returns:
            True if exists, False otherwise
        """
        try:
            blob = self.bucket.blob(blob_name)
            return blob.exists()
        except GoogleCloudError as e:
            logger.error(f"Failed to check existence of {blob_name}: {e}")
            return False


# Convenience functions for backward compatibility and ease of use

def create_gcs_client(
    bucket_name: Optional[str] = None,
    project_id: Optional[str] = None,
) -> GCSClient:
    """
    Create a GCS client instance.
    
    Args:
        bucket_name: GCS bucket name
        project_id: GCP project ID
    
    Returns:
        GCSClient instance
    """
    return GCSClient(bucket_name=bucket_name, project_id=project_id)


def generate_signed_url(
    blob_name: str,
    bucket_name: Optional[str] = None,
    expiration_minutes: int = 15,
    method: str = "GET",
) -> str:
    """
    Generate a signed URL for a blob.
    
    Args:
        blob_name: Name/path of the blob
        bucket_name: GCS bucket name (defaults to env var)
        expiration_minutes: URL expiration in minutes
        method: HTTP method
    
    Returns:
        Signed URL string
    """
    client = create_gcs_client(bucket_name=bucket_name)
    return client.generate_signed_url(
        blob_name=blob_name,
        expiration_minutes=expiration_minutes,
        method=method,
    )


def upload_audio_file(
    source_path: Path | str,
    destination_blob_name: str,
    bucket_name: Optional[str] = None,
    metadata: Optional[Dict[str, str]] = None,
) -> storage.Blob:
    """
    Upload an audio file to GCS.
    
    Args:
        source_path: Local file path
        destination_blob_name: Destination path in GCS
        bucket_name: GCS bucket name
        metadata: Custom metadata
    
    Returns:
        Uploaded blob object
    """
    client = create_gcs_client(bucket_name=bucket_name)
    
    # Determine content type for audio files
    content_type = "audio/mpeg"  # Default
    if isinstance(source_path, str):
        source_path = Path(source_path)
    
    suffix = source_path.suffix.lower()
    audio_types = {
        ".mp3": "audio/mpeg",
        ".wav": "audio/wav",
        ".flac": "audio/flac",
        ".ogg": "audio/ogg",
        ".m4a": "audio/mp4",
        ".aac": "audio/aac",
    }
    content_type = audio_types.get(suffix, "audio/mpeg")
    
    return client.upload_file(
        source_path=source_path,
        destination_blob_name=destination_blob_name,
        content_type=content_type,
        metadata=metadata,
    )


def delete_file(blob_name: str, bucket_name: Optional[str] = None) -> bool:
    """
    Delete a file from GCS.
    
    Args:
        blob_name: Name/path of the blob
        bucket_name: GCS bucket name
    
    Returns:
        True if deleted, False if not found
    """
    client = create_gcs_client(bucket_name=bucket_name)
    return client.delete_file(blob_name)


def list_audio_files(
    prefix: str = "audio/",
    bucket_name: Optional[str] = None,
    max_results: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """
    List audio files in GCS.
    
    Args:
        prefix: Path prefix (default: "audio/")
        bucket_name: GCS bucket name
        max_results: Maximum results
    
    Returns:
        List of file metadata
    """
    client = create_gcs_client(bucket_name=bucket_name)
    return client.list_files(prefix=prefix, max_results=max_results)


def get_file_metadata(
    blob_name: str,
    bucket_name: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Get metadata for a file.
    
    Args:
        blob_name: Name/path of the blob
        bucket_name: GCS bucket name
    
    Returns:
        Metadata dictionary
    """
    client = create_gcs_client(bucket_name=bucket_name)
    return client.get_file_metadata(blob_name)


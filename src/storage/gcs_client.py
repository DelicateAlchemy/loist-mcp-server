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
from google.auth.transport.requests import Request
from google.auth import default, iam
import os
import requests

# Try to import config, but make it optional for backward compatibility
try:
    from src.config import config as app_config
    HAS_APP_CONFIG = True
except ImportError:
    HAS_APP_CONFIG = False

logger = logging.getLogger(__name__)


def _resolve_service_account_email() -> Optional[str]:
    """
    Resolve the service account email for GCS signed URL generation.

    Priority order:
    1. GCP_SERVICE_ACCOUNT_EMAIL env var
    2. Metadata server (for Cloud Run/Compute Engine)
    3. From credentials object (if available)

    Returns:
        Service account email or None if not found
    """
    logger.info("[SIGNED_URL_DEBUG] Resolving service account email")
    
    # Check environment variable first
    email = os.getenv("GCP_SERVICE_ACCOUNT_EMAIL")
    if email:
        logger.info(f"[SIGNED_URL_DEBUG] Using service account email from env: {email}")
        return email
    else:
        logger.info("[SIGNED_URL_DEBUG] GCP_SERVICE_ACCOUNT_EMAIL env var not set")

    # Try metadata server (Cloud Run/Compute Engine)
    logger.info("[SIGNED_URL_DEBUG] Attempting to get service account email from metadata server")
    try:
        metadata_url = "http://metadata.google.internal/computeMetadata/v1/instance/service-accounts/default/email"
        logger.info(f"[SIGNED_URL_DEBUG] Metadata URL: {metadata_url}")
        response = requests.get(metadata_url, headers={"Metadata-Flavor": "Google"}, timeout=1)
        logger.info(f"[SIGNED_URL_DEBUG] Metadata server response status: {response.status_code}")
        if response.status_code == 200:
            email = response.text.strip()
            logger.info(f"[SIGNED_URL_DEBUG] Using service account email from metadata: {email}")
            return email
        else:
            logger.warning(f"[SIGNED_URL_DEBUG] Metadata server returned status {response.status_code}: {response.text}")
    except Exception as e:
        logger.warning(f"[SIGNED_URL_DEBUG] Could not get email from metadata server: {type(e).__name__}: {e}")

    # Try to get from credentials
    logger.info("[SIGNED_URL_DEBUG] Attempting to get service account email from credentials")
    try:
        credentials, project_id = default(scopes=["https://www.googleapis.com/auth/cloud-platform"])
        logger.info(f"[SIGNED_URL_DEBUG] Credentials type: {type(credentials).__name__}")
        logger.info(f"[SIGNED_URL_DEBUG] Credentials has service_account_email attr: {hasattr(credentials, 'service_account_email')}")
        if hasattr(credentials, 'service_account_email'):
            email = credentials.service_account_email
            logger.info(f"[SIGNED_URL_DEBUG] Using service account email from credentials: {email}")
            return email
        else:
            logger.warning("[SIGNED_URL_DEBUG] Credentials object does not have service_account_email attribute")
    except Exception as e:
        logger.warning(f"[SIGNED_URL_DEBUG] Could not get email from credentials: {type(e).__name__}: {e}")

    logger.error("[SIGNED_URL_DEBUG] Could not resolve service account email for IAM SignBlob")
    return None


class GCSClient:
    """Client for interacting with Google Cloud Storage."""
    
    def __init__(
        self,
        bucket_name: Optional[str] = None,
        project_id: Optional[str] = None,
        credentials_path: Optional[str] = None,
    ):
        """
        Initialize GCS client.
        
        Args:
            bucket_name: Name of the GCS bucket (defaults to config or env var GCS_BUCKET_NAME)
            project_id: GCP project ID (defaults to config or env var GCS_PROJECT_ID)
            credentials_path: Path to service account key (defaults to config or env var GOOGLE_APPLICATION_CREDENTIALS)
        """
        # Try to get values from config first, then env vars, then parameters
        if HAS_APP_CONFIG:
            self.bucket_name = bucket_name or app_config.gcs_bucket_name or os.getenv("GCS_BUCKET_NAME")
            self.project_id = project_id or app_config.gcs_project_id or os.getenv("GCS_PROJECT_ID")
            self.credentials_path = credentials_path or app_config.gcs_credentials_path
        else:
            self.bucket_name = bucket_name or os.getenv("GCS_BUCKET_NAME")
            self.project_id = project_id or os.getenv("GCS_PROJECT_ID")
            self.credentials_path = credentials_path or os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
        
        if not self.bucket_name:
            raise ValueError("Bucket name must be provided via parameter, config, or GCS_BUCKET_NAME env var")
        
        # Set credentials in environment if provided and file exists
        if self.credentials_path and os.path.exists(self.credentials_path):
            os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = self.credentials_path
            logger.info(f"Using credentials from: {self.credentials_path}")
        elif self.credentials_path:
            logger.warning(f"Credentials path provided but file not found: {self.credentials_path}")

        # For Cloud Run with service account, don't override GOOGLE_APPLICATION_CREDENTIALS
        # Let ADC use the attached service account automatically
        gcp_indicators = [
            os.getenv("K_SERVICE"),  # Cloud Run
            os.getenv("GAE_SERVICE"),  # App Engine
            os.getenv("GCE_METADATA_HOST"),  # Compute Engine
        ]
        if any(gcp_indicators) and not self.credentials_path:
            logger.info("Running on GCP with service account - using ADC")
            # Don't set GOOGLE_APPLICATION_CREDENTIALS, let ADC work automatically

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

        Uses IAM SignBlob API when running on GCP (Cloud Run/Compute Engine),
        falls back to keyfile signing for local development.

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
        logger.info(f"[SIGNED_URL_DEBUG] generate_signed_url called: blob_name={blob_name}, bucket={self.bucket_name}, expiration={expiration_minutes}min, method={method}")
        try:
            # Step 1: Get blob reference
            logger.info(f"[SIGNED_URL_DEBUG] Step 1: Getting blob reference for {blob_name}")
            blob = self.bucket.blob(blob_name)
            logger.info(f"[SIGNED_URL_DEBUG] Blob reference created: {blob.name}")

            # Step 2: Verify blob exists (for GET requests)
            if method == "GET":
                logger.info(f"[SIGNED_URL_DEBUG] Step 2: Checking blob existence for GET request")
                blob_exists = blob.exists()
                logger.info(f"[SIGNED_URL_DEBUG] Blob exists: {blob_exists}")
                if not blob_exists:
                    logger.error(f"[SIGNED_URL_DEBUG] Blob not found: {blob_name}")
                    raise NotFound(f"Blob not found: {blob_name}")

            # Step 3: Determine signing method
            logger.info("[SIGNED_URL_DEBUG] Step 3: Determining signing method")
            use_iam_signblob = self._should_use_iam_signblob()
            logger.info(f"[SIGNED_URL_DEBUG] Using IAM SignBlob: {use_iam_signblob}")

            # Step 4: Generate signed URL
            if use_iam_signblob:
                logger.info(f"[SIGNED_URL_DEBUG] Step 4: Using IAM SignBlob for signed URL generation: {blob_name}")
                url = self._generate_signed_url_iam(blob, expiration_minutes, method, content_type, response_disposition)
            else:
                logger.info(f"[SIGNED_URL_DEBUG] Step 4: Using keyfile signing for signed URL generation: {blob_name}")
                url = self._generate_signed_url_keyfile(blob, expiration_minutes, method, content_type, response_disposition)

            logger.info(
                f"[SIGNED_URL_DEBUG] Generated signed URL for blob: {blob_name}, "
                f"expires in {expiration_minutes} minutes, "
                f"method: {'IAM SignBlob' if use_iam_signblob else 'keyfile'}"
            )

            return url

        except NotFound as e:
            logger.error(f"[SIGNED_URL_DEBUG] Blob not found: {blob_name} - {e}")
            raise
        except GoogleCloudError as e:
            logger.error(f"[SIGNED_URL_DEBUG] Failed to generate signed URL for {blob_name}: {type(e).__name__}: {e}")
            import traceback
            logger.error(f"[SIGNED_URL_DEBUG] Full traceback: {traceback.format_exc()}")
            raise
        except Exception as e:
            logger.error(f"[SIGNED_URL_DEBUG] Unexpected error generating signed URL for {blob_name}: {type(e).__name__}: {e}")
            import traceback
            logger.error(f"[SIGNED_URL_DEBUG] Full traceback: {traceback.format_exc()}")
            raise GoogleCloudError(f"Unexpected error generating signed URL: {e}")

    def _should_use_iam_signblob(self) -> bool:
        """Determine if we should use IAM SignBlob based on config, environment and credentials."""

        # Check explicit config setting first
        if HAS_APP_CONFIG:
            mode = app_config.gcs_signer_mode.lower()
            if mode == "iam":
                logger.debug("GCS signer mode explicitly set to IAM")
                return True
            elif mode == "keyfile":
                logger.debug("GCS signer mode explicitly set to keyfile")
                return False
            # mode == "auto", continue with auto-detection

        # Auto-detection logic
        # Check if GOOGLE_APPLICATION_CREDENTIALS points to a keyfile
        credentials_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
        if credentials_path and os.path.exists(credentials_path):
            try:
                import json
                with open(credentials_path, 'r') as f:
                    creds_data = json.load(f)
                # If it's a service account keyfile with private_key, use keyfile signing
                if "private_key" in creds_data and "client_email" in creds_data:
                    logger.debug("Detected service account keyfile, using keyfile signing")
                    return False
            except Exception:
                pass

        # Check if we're running on GCP (Cloud Run/Compute Engine)
        # Look for GCP-specific environment variables or metadata
        gcp_indicators = [
            os.getenv("K_SERVICE"),  # Cloud Run
            os.getenv("GAE_SERVICE"),  # App Engine
            os.getenv("GCE_METADATA_HOST"),  # Compute Engine
            "/computeMetadata" in os.getenv("GCE_METADATA_HOST", ""),
        ]

        if any(gcp_indicators):
            logger.debug("Detected GCP environment, will use IAM SignBlob")
            return True

        # Default to keyfile if credentials path exists
        if credentials_path:
            logger.debug("Credentials path exists but not GCP detected, using keyfile")
            return False

        # Last resort: try IAM SignBlob if no explicit keyfile
        logger.debug("No explicit credentials, attempting IAM SignBlob")
        return True

    def _generate_signed_url_iam(
        self,
        blob: storage.Blob,
        expiration_minutes: int,
        method: str,
        content_type: Optional[str],
        response_disposition: Optional[str],
    ) -> str:
        """Generate signed URL using IAM SignBlob API."""
        from google.cloud.storage._signing import generate_signed_url_v4
        
        logger.info(f"[SIGNED_URL_DEBUG] Starting IAM SignBlob signed URL generation")
        logger.info(f"[SIGNED_URL_DEBUG] Blob: {blob.name}, Bucket: {blob.bucket.name}")
        logger.info(f"[SIGNED_URL_DEBUG] Expiration: {expiration_minutes} minutes, Method: {method}")
        
        # Step 1: Resolve service account email
        logger.info("[SIGNED_URL_DEBUG] Step 1: Resolving service account email")
        service_account_email = _resolve_service_account_email()
        if not service_account_email:
            logger.error("[SIGNED_URL_DEBUG] Failed to resolve service account email")
            raise GoogleCloudError("Could not resolve service account email for IAM SignBlob")
        logger.info(f"[SIGNED_URL_DEBUG] Service account email resolved: {service_account_email}")

        try:
            # Step 2: Get ADC credentials
            logger.info("[SIGNED_URL_DEBUG] Step 2: Getting Application Default Credentials")
            credentials, project_id = default(scopes=["https://www.googleapis.com/auth/cloud-platform"])
            logger.info(f"[SIGNED_URL_DEBUG] Project ID: {project_id}")
            logger.info(f"[SIGNED_URL_DEBUG] Credentials type: {type(credentials).__name__}")
            logger.info(f"[SIGNED_URL_DEBUG] Credentials has service_account_email attr: {hasattr(credentials, 'service_account_email')}")
            if hasattr(credentials, 'service_account_email'):
                logger.info(f"[SIGNED_URL_DEBUG] Credentials service_account_email: {getattr(credentials, 'service_account_email', 'N/A')}")
            
            # Step 3: Create request object
            logger.info("[SIGNED_URL_DEBUG] Step 3: Creating Request object")
            request = Request()

            # Step 4: Create IAM signer
            logger.info("[SIGNED_URL_DEBUG] Step 4: Creating IAM Signer")
            logger.info(f"[SIGNED_URL_DEBUG] IAM Signer params: service_account={service_account_email}, project={project_id}")
            signer = iam.Signer(request, credentials, service_account_email)
            logger.info("[SIGNED_URL_DEBUG] IAM Signer created successfully")

            # Step 5: Build expiration datetime
            logger.info("[SIGNED_URL_DEBUG] Step 5: Building expiration datetime")
            expiration = datetime.datetime.utcnow() + datetime.timedelta(minutes=expiration_minutes)
            logger.info(f"[SIGNED_URL_DEBUG] Expiration datetime: {expiration.isoformat()}")
            
            # Step 6: Generate signed URL
            logger.info("[SIGNED_URL_DEBUG] Step 6: Calling generate_signed_url_v4")
            logger.info(f"[SIGNED_URL_DEBUG] generate_signed_url_v4 params: bucket={blob.bucket.name}, blob_name={blob.name}, expiration={expiration.isoformat()}, method={method}")
            signed_url = generate_signed_url_v4(
                bucket=blob.bucket,
                blob_name=blob.name,
                expiration=expiration,
                method=method,
                service_account_email=service_account_email,
                signer=signer.sign,
                content_type=content_type,
                response_disposition=response_disposition,
            )
            logger.info("[SIGNED_URL_DEBUG] Signed URL generated successfully")
            logger.debug(f"[SIGNED_URL_DEBUG] Signed URL (first 100 chars): {signed_url[:100]}...")
            return signed_url

        except Exception as e:
            logger.error(f"[SIGNED_URL_DEBUG] IAM SignBlob failed: {type(e).__name__}: {e}")
            logger.error(f"[SIGNED_URL_DEBUG] Exception details: {str(e)}")
            import traceback
            logger.error(f"[SIGNED_URL_DEBUG] Full traceback: {traceback.format_exc()}")
            raise GoogleCloudError(f"IAM SignBlob signing failed: {e}")

    def _generate_signed_url_keyfile(
        self,
        blob: storage.Blob,
        expiration_minutes: int,
        method: str,
        content_type: Optional[str],
        response_disposition: Optional[str],
    ) -> str:
        """Generate signed URL using traditional keyfile signing."""
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

        return blob.generate_signed_url(**url_params)
    
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
    credentials_path: Optional[str] = None,
) -> GCSClient:
    """
    Create a GCS client instance.

    Args:
        bucket_name: GCS bucket name
        project_id: GCP project ID
        credentials_path: Path to service account key file

    Returns:
        GCSClient instance
    """
    # If no credentials path provided, check for GOOGLE_APPLICATION_CREDENTIALS
    if credentials_path is None:
        credentials_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")

    return GCSClient(
        bucket_name=bucket_name,
        project_id=project_id,
        credentials_path=credentials_path
    )


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


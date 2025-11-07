#!/usr/bin/env python3
"""
Debug script for testing signed URL generation.

This script tests the signed URL generation process step-by-step to isolate failures.
It simulates what happens in the embed endpoint when generating signed URLs.

Usage:
    python scripts/debug_signed_url_generation.py <audio_id>
    
Example:
    python scripts/debug_signed_url_generation.py 1a4daa58-1759-4f10-af32-648ab76e9e8d
"""

import os
import sys
import logging
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s'
)
logger = logging.getLogger(__name__)

def main():
    """Main debugging function."""
    if len(sys.argv) < 2:
        print("Usage: python scripts/debug_signed_url_generation.py <audio_id>")
        print("Example: python scripts/debug_signed_url_generation.py 1a4daa58-1759-4f10-af32-648ab76e9e8d")
        sys.exit(1)
    
    audio_id = sys.argv[1]
    logger.info(f"🔍 Debugging signed URL generation for audio ID: {audio_id}")
    logger.info("=" * 80)
    
    try:
        # Step 1: Get metadata from database
        logger.info("Step 1: Retrieving metadata from database")
        from database import get_audio_metadata_by_id
        
        metadata = get_audio_metadata_by_id(audio_id)
        if not metadata:
            logger.error(f"❌ Audio track not found: {audio_id}")
            sys.exit(1)
        
        logger.info(f"✅ Metadata retrieved: {metadata.get('title', 'Unknown')} by {metadata.get('artist', 'Unknown')}")
        logger.info(f"   Audio GCS path: {metadata.get('audio_gcs_path')}")
        logger.info(f"   Thumbnail GCS path: {metadata.get('thumbnail_gcs_path')}")
        
        # Step 2: Get audio GCS path
        audio_path = metadata.get("audio_gcs_path")
        if not audio_path:
            logger.error("❌ No audio_gcs_path in metadata")
            sys.exit(1)
        
        logger.info(f"✅ Audio path: {audio_path}")
        
        # Step 3: Apply path correction (if needed)
        logger.info("Step 2: Checking for path correction")
        if audio_path and 'loist-music-library-staging-audio' in audio_path:
            corrected_path = audio_path.replace('loist-music-library-staging-audio', 'loist-music-library-bucket-staging')
            logger.warning(f"⚠️  Correcting audio path from {audio_path} to {corrected_path}")
            audio_path = corrected_path
        else:
            logger.info(f"✅ Audio path does not need correction: {audio_path}")
        
        # Step 4: Parse GCS path
        logger.info("Step 3: Parsing GCS path")
        if not audio_path.startswith("gs://"):
            logger.error(f"❌ Invalid GCS path format (missing gs:// prefix): {audio_path}")
            sys.exit(1)
        
        path_without_prefix = audio_path[5:]  # Remove "gs://"
        parts = path_without_prefix.split("/", 1)
        
        if len(parts) != 2:
            logger.error(f"❌ Invalid GCS path format (cannot split bucket/blob): {audio_path}")
            sys.exit(1)
        
        bucket_name, blob_name = parts
        logger.info(f"✅ Parsed bucket: {bucket_name}")
        logger.info(f"✅ Parsed blob: {blob_name}")
        
        # Step 5: Check environment configuration
        logger.info("Step 4: Checking environment configuration")
        logger.info(f"   GCS_BUCKET_NAME: {os.getenv('GCS_BUCKET_NAME', 'NOT SET')}")
        logger.info(f"   GCS_PROJECT_ID: {os.getenv('GCS_PROJECT_ID', 'NOT SET')}")
        logger.info(f"   GCP_SERVICE_ACCOUNT_EMAIL: {os.getenv('GCP_SERVICE_ACCOUNT_EMAIL', 'NOT SET')}")
        logger.info(f"   GOOGLE_APPLICATION_CREDENTIALS: {os.getenv('GOOGLE_APPLICATION_CREDENTIALS', 'NOT SET')}")
        logger.info(f"   K_SERVICE: {os.getenv('K_SERVICE', 'NOT SET')} (Cloud Run indicator)")
        
        # Step 6: Create GCS client
        logger.info("Step 5: Creating GCS client")
        from src.storage import create_gcs_client
        
        try:
            gcs_client = create_gcs_client(bucket_name=bucket_name)
            logger.info(f"✅ GCS client created for bucket: {gcs_client.bucket_name}")
        except Exception as e:
            logger.error(f"❌ Failed to create GCS client: {type(e).__name__}: {e}")
            import traceback
            logger.error(traceback.format_exc())
            sys.exit(1)
        
        # Step 7: Check blob existence
        logger.info("Step 6: Checking blob existence")
        try:
            blob_exists = gcs_client.file_exists(blob_name)
            if blob_exists:
                logger.info(f"✅ Blob exists: {blob_name}")
            else:
                logger.warning(f"⚠️  Blob does not exist: {blob_name}")
                logger.warning("   This may cause signed URL generation to fail")
        except Exception as e:
            logger.warning(f"⚠️  Could not check blob existence: {type(e).__name__}: {e}")
        
        # Step 8: Determine signing method
        logger.info("Step 7: Determining signing method")
        use_iam = gcs_client._should_use_iam_signblob()
        logger.info(f"   Will use IAM SignBlob: {use_iam}")
        
        # Step 9: Generate signed URL
        logger.info("Step 8: Generating signed URL")
        logger.info(f"   Method: {'IAM SignBlob' if use_iam else 'Keyfile'}")
        logger.info(f"   Expiration: 15 minutes")
        
        try:
            signed_url = gcs_client.generate_signed_url(
                blob_name=blob_name,
                expiration_minutes=15,
                method="GET"
            )
            logger.info("✅ Signed URL generated successfully!")
            logger.info(f"   URL (first 100 chars): {signed_url[:100]}...")
            logger.info(f"   Full URL length: {len(signed_url)} characters")
            
            # Step 10: Test URL (optional)
            logger.info("Step 9: Testing signed URL")
            import requests
            try:
                response = requests.head(signed_url, timeout=5)
                logger.info(f"   HTTP Status: {response.status_code}")
                if response.status_code == 200:
                    logger.info("✅ Signed URL is accessible!")
                    logger.info(f"   Content-Type: {response.headers.get('Content-Type', 'N/A')}")
                    logger.info(f"   Content-Length: {response.headers.get('Content-Length', 'N/A')} bytes")
                else:
                    logger.warning(f"⚠️  Signed URL returned status {response.status_code}")
            except Exception as e:
                logger.warning(f"⚠️  Could not test signed URL: {type(e).__name__}: {e}")
            
            print("\n" + "=" * 80)
            print("✅ SUCCESS: Signed URL generation completed successfully!")
            print("=" * 80)
            
        except Exception as e:
            logger.error("❌ Failed to generate signed URL")
            logger.error(f"   Exception type: {type(e).__name__}")
            logger.error(f"   Exception message: {str(e)}")
            import traceback
            logger.error("   Full traceback:")
            logger.error(traceback.format_exc())
            
            print("\n" + "=" * 80)
            print("❌ FAILURE: Signed URL generation failed")
            print("=" * 80)
            print("\nTroubleshooting steps:")
            print("1. Check IAM permissions (service account needs roles/iam.securityAdmin on itself)")
            print("2. Verify service account email resolution")
            print("3. Check GCS bucket permissions")
            print("4. Verify blob exists in GCS bucket")
            print("5. Check Cloud Run logs for detailed error messages")
            sys.exit(1)
    
    except Exception as e:
        logger.error(f"❌ Unexpected error: {type(e).__name__}: {e}")
        import traceback
        logger.error(traceback.format_exc())
        sys.exit(1)

if __name__ == "__main__":
    main()


#!/usr/bin/env python3
"""
Configure CORS for Google Cloud Storage bucket to allow browser access to waveform SVGs.

This script configures CORS on the GCS bucket to allow cross-origin requests
from web browsers for waveform SVG files and other resources.
"""

import sys
import json
from pathlib import Path

# Setup paths
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "src"))

from google.cloud import storage
from google.api_core import exceptions


def configure_cors_for_bucket(bucket_name: str):
    """
    Configure CORS for a GCS bucket to allow browser access.
    
    Args:
        bucket_name: Name of the GCS bucket
    """
    try:
        # Create storage client
        client = storage.Client()
        bucket = client.bucket(bucket_name)
        
        # Check if bucket exists
        if not bucket.exists():
            print(f"Error: Bucket 'gs://{bucket_name}' does not exist")
            return False
        
        # CORS configuration
        cors_config = [
            {
                "origin": ["*"],
                "method": ["GET", "HEAD", "OPTIONS"],
                "responseHeader": [
                    "Content-Type",
                    "Content-Length",
                    "Content-Range",
                    "Accept-Ranges",
                    "Range",
                    "Cache-Control",
                    "Access-Control-Allow-Origin",
                    "Access-Control-Allow-Methods",
                    "Access-Control-Allow-Headers"
                ],
                "maxAgeSeconds": 3600
            }
        ]
        
        print(f"Configuring CORS for bucket: gs://{bucket_name}")
        print(f"CORS configuration: {json.dumps(cors_config, indent=2)}")
        
        # Get current CORS configuration
        try:
            current_cors = bucket.cors
            if current_cors:
                print(f"Current CORS configuration: {json.dumps(current_cors, indent=2)}")
        except Exception as e:
            print(f"Note: Could not retrieve current CORS configuration: {e}")
        
        # Set CORS configuration
        bucket.cors = cors_config
        bucket.patch()
        
        print(f"✅ CORS configuration applied successfully to gs://{bucket_name}")
        print(f"   Waveform SVGs should now be accessible from browsers")
        
        # Verify CORS configuration
        try:
            updated_cors = bucket.cors
            print(f"\n✅ Verified CORS configuration:")
            print(f"   {json.dumps(updated_cors, indent=2)}")
        except Exception as e:
            print(f"⚠️  Warning: Could not verify CORS configuration: {e}")
        
        return True
        
    except exceptions.GoogleAPIError as e:
        print(f"❌ Error configuring CORS: {e}")
        print(f"   Make sure you have the 'storage.buckets.update' permission")
        return False
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    import os
    
    # Get bucket name from environment or use default
    bucket_name = os.getenv("GCS_BUCKET_NAME", "loist-mvp-audio-files")
    
    if len(sys.argv) > 1:
        bucket_name = sys.argv[1]
    
    print(f"Configuring CORS for bucket: {bucket_name}")
    print("=" * 60)
    
    success = configure_cors_for_bucket(bucket_name)
    
    if success:
        print("\n" + "=" * 60)
        print("✅ CORS configuration complete!")
        print(f"   Bucket: gs://{bucket_name}")
        print(f"   Waveform SVGs should now be accessible from browsers")
        sys.exit(0)
    else:
        print("\n" + "=" * 60)
        print("❌ Failed to configure CORS")
        sys.exit(1)

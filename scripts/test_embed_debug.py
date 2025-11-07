#!/usr/bin/env python3
"""
Test script to debug embed endpoint GCS bucket configuration.

This script tests the embed endpoint and shows what GCS bucket configuration
is being used in the staging environment.
"""

import requests
import json
import sys
from typing import Dict, Any

def test_embed_endpoint(audio_id: str, base_url: str = "https://staging.loist.io") -> Dict[str, Any]:
    """
    Test the embed endpoint and return debug information.

    Args:
        audio_id: The audio ID to test
        base_url: Base URL for the embed endpoint

    Returns:
        Dict containing test results and debug info
    """
    url = f"{base_url}/embed/{audio_id}"

    print(f"Testing embed endpoint: {url}")
    print("=" * 50)

    try:
        # Make the request
        response = requests.get(url, timeout=30)

        result = {
            "url": url,
            "status_code": response.status_code,
            "response_time": response.elapsed.total_seconds(),
            "content_length": len(response.content),
            "content_type": response.headers.get('content-type', 'unknown'),
        }

        print(f"Status Code: {response.status_code}")
        print(f"Response Time: {response.elapsed.total_seconds():.2f}s")
        print(f"Content Type: {response.headers.get('content-type', 'unknown')}")
        print(f"Content Length: {len(response.content)} bytes")

        if response.status_code == 500:
            print("\n❌ 500 Internal Server Error detected!")
            print("\nResponse content:")
            print("-" * 30)
            print(response.text[:1000])  # First 1000 chars
            if len(response.text) > 1000:
                print("... (truncated)")
            print("-" * 30)

        elif response.status_code == 200:
            print("\n✅ 200 OK - Embed page loaded successfully!")
            # Check if it contains expected content
            content = response.text.lower()
            if "audio" in content and ("play" in content or "stream" in content):
                print("✅ Response appears to contain audio player")
            else:
                print("⚠️  Response may not contain expected audio player")

        else:
            print(f"\n⚠️  Unexpected status code: {response.status_code}")
            print(f"Response: {response.text[:500]}")

        return result

    except requests.exceptions.RequestException as e:
        print(f"❌ Request failed: {e}")
        return {
            "url": url,
            "error": str(e),
            "status_code": None
        }

def check_cloud_run_env_vars():
    """
    Check if we can access Cloud Run environment variables.
    This will likely fail due to permissions, but worth trying.
    """
    print("\n" + "=" * 50)
    print("Checking Cloud Run Environment Variables")
    print("=" * 50)

    # This will likely fail due to permissions
    try:
        import subprocess
        result = subprocess.run([
            "gcloud", "run", "services", "describe", "music-library-mcp-staging",
            "--region=us-central1", "--format=value(spec.template.spec.containers[0].env)"
        ], capture_output=True, text=True, timeout=10)

        if result.returncode == 0:
            print("✅ Successfully retrieved environment variables:")
            print(result.stdout)
        else:
            print("❌ Failed to retrieve environment variables:")
            print(result.stderr)

    except Exception as e:
        print(f"❌ Error checking environment variables: {e}")

def main():
    if len(sys.argv) != 2:
        print("Usage: python test_embed_debug.py <audio_id>")
        print("Example: python test_embed_debug.py ba8c6d62-0779-4af2-bef4-022138928b3c")
        sys.exit(1)

    audio_id = sys.argv[1]

    print("🔍 Loist Music Library - Embed Endpoint Debug Test")
    print("=" * 60)

    # Test the embed endpoint
    result = test_embed_endpoint(audio_id)

    # Try to check Cloud Run env vars (will likely fail)
    check_cloud_run_env_vars()

    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)

    if result.get("status_code") == 500:
        print("❌ ISSUE CONFIRMED: Embed endpoint returning 500 Internal Server Error")
        print("   This indicates a server-side error, likely GCS bucket configuration")
        print("\n🔧 POSSIBLE FIXES:")
        print("   1. Check if Cloud Run deployment used the updated GCS bucket secret")
        print("   2. Verify the secret 'gcs-bucket-name-staging' contains 'loist-music-library-bucket-staging'")
        print("   3. Check Cloud Run logs for '[EMBED_DEBUG]' messages")
        print("   4. Ensure staging database contains correct audio_gcs_path values")

    elif result.get("status_code") == 200:
        print("✅ Embed endpoint working correctly")

    elif result.get("error"):
        print(f"❌ Request failed: {result['error']}")

    else:
        print(f"⚠️  Unexpected status code: {result.get('status_code')}")

if __name__ == "__main__":
    main()

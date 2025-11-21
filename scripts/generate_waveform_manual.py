#!/usr/bin/env python3
"""
Manual waveform generation script for local development.

This script generates a waveform for an audio file synchronously,
bypassing the Cloud Tasks queue for local testing.
"""

import sys
import asyncio
import logging
from pathlib import Path

# Setup paths
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "src"))

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def generate_waveform_for_audio(audio_id: str):
    """
    Generate waveform for an audio file manually.
    
    Args:
        audio_id: UUID of the audio track
    """
    try:
        # Import required modules
        from database.operations import get_audio_metadata_by_id
        from src.tasks.handler import handle_waveform_task, _calculate_file_hash
        from src.storage.gcs_client import create_gcs_client
        from pathlib import Path
        import tempfile
        
        logger.info(f"Generating waveform for audio_id: {audio_id}")
        
        # Get audio metadata
        metadata = get_audio_metadata_by_id(audio_id)
        if not metadata:
            logger.error(f"Audio metadata not found for audio_id: {audio_id}")
            return
        
        audio_gcs_path = metadata.get("audio_gcs_path")
        if not audio_gcs_path:
            logger.error(f"Audio GCS path not found for audio_id: {audio_id}")
            return
        
        logger.info(f"Audio GCS path: {audio_gcs_path}")
        
        # Download audio file from GCS to calculate hash
        logger.info("Downloading audio file from GCS...")
        gcs_client = create_gcs_client()
        
        # Extract blob name from GCS path (gs://bucket/path -> path)
        if audio_gcs_path.startswith("gs://"):
            path_part = audio_gcs_path[5:]  # Remove 'gs://'
            slash_index = path_part.find('/')
            if slash_index == -1:
                raise ValueError(f"Invalid GCS path format: {audio_gcs_path}")
            blob_name = path_part[slash_index + 1:]  # Everything after bucket/
        else:
            blob_name = audio_gcs_path
        
        logger.info(f"Blob name: {blob_name}")
        
        # Download to temporary file
        with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as temp_file:
            temp_path = Path(temp_file.name)
            logger.info(f"Downloading to temporary file: {temp_path}")
            
            # Download from GCS
            blob = gcs_client.bucket.blob(blob_name)
            blob.download_to_filename(str(temp_path))
            logger.info("Audio file downloaded successfully")
            
            # Calculate SHA-256 hash using the handler's function
            logger.info("Calculating source hash...")
            source_hash_str = _calculate_file_hash(temp_path)
            logger.info(f"Source hash: {source_hash_str[:16]}...")
        
        # Prepare payload
        payload = {
            "audioId": audio_id,
            "audioGcsPath": audio_gcs_path,
            "sourceHash": source_hash_str
        }
        
        logger.info("Starting waveform generation...")
        
        # Call waveform handler
        result = await handle_waveform_task(payload)
        
        logger.info(f"Waveform generation completed: {result}")
        
        # Cleanup temporary file
        if temp_path.exists():
            temp_path.unlink()
            logger.info("Temporary file cleaned up")
        
        return result
        
    except Exception as e:
        logger.error(f"Error generating waveform: {e}")
        import traceback
        traceback.print_exc()
        raise


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python scripts/generate_waveform_manual.py <audio_id>")
        print("Example: python scripts/generate_waveform_manual.py 02ceadb6-ed7c-45d8-976a-a2bfc9222d45")
        sys.exit(1)
    
    audio_id = sys.argv[1]
    asyncio.run(generate_waveform_for_audio(audio_id))

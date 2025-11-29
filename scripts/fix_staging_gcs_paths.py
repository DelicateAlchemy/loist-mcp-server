#!/usr/bin/env python3
"""
Fix GCS paths in staging database.

This script updates the audio_gcs_path and thumbnail_gcs_path fields
in the staging database to use the correct bucket name.
"""

import os
import sys
import argparse
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

def fix_gcs_paths(database_url: str, dry_run: bool = True):
    """
    Update GCS paths in the database to use the correct bucket.

    Args:
        database_url: PostgreSQL connection URL for staging database
        dry_run: If True, only show what would be changed
    """
    print("🔧 Fixing GCS Paths in Staging Database")
    print("=" * 50)
    print(f"Database URL: {database_url}")
    print(f"Dry Run: {dry_run}")
    print()

    # Set environment to use the provided database URL
    os.environ['DATABASE_URL'] = database_url

    try:
        # Import database operations
        from database.operations import get_audio_metadata_by_id
        from database.pool import get_connection

        # First, let's see what audio tracks exist
        print("Checking existing audio tracks...")

        with get_connection() as conn:
            with conn.cursor() as cur:
                # Get all audio tracks
                cur.execute("""
                    SELECT id, audio_gcs_path, thumbnail_gcs_path, title
                    FROM audio_tracks
                    WHERE audio_gcs_path IS NOT NULL
                    LIMIT 10
                """)
                tracks = cur.fetchall()

        print(f"Found {len(tracks)} audio tracks")
        print()

        # Check which ones need updating
        tracks_to_update = []
        for track_id, audio_path, thumbnail_path, title in tracks:
            needs_update = False

            if audio_path and 'loist-music-library-staging-audio' in audio_path:
                needs_update = True
                print(f"❌ {track_id}: {title}")
                print(f"   Audio path needs update: {audio_path}")

            if thumbnail_path and 'loist-music-library-staging-audio' in thumbnail_path:
                needs_update = True
                print(f"   Thumbnail path needs update: {thumbnail_path}")

            if needs_update:
                tracks_to_update.append((track_id, audio_path, thumbnail_path))
            else:
                print(f"✅ {track_id}: {title} - OK")

        print()
        print(f"Tracks needing update: {len(tracks_to_update)}")

        if not tracks_to_update:
            print("✅ No tracks need updating!")
            return True

        if dry_run:
            print("\n📋 DRY RUN - Would update the following:")
            for track_id, audio_path, thumbnail_path in tracks_to_update:
                new_audio = audio_path.replace('loist-music-library-staging-audio', 'loist-music-library-bucket-staging') if audio_path else None
                new_thumb = thumbnail_path.replace('loist-music-library-staging-audio', 'loist-music-library-bucket-staging') if thumbnail_path else None
                print(f"  {track_id}:")
                if new_audio != audio_path:
                    print(f"    Audio: {audio_path} → {new_audio}")
                if new_thumb != thumbnail_path:
                    print(f"    Thumb: {thumbnail_path} → {new_thumb}")
            print("\n💡 Run with --no-dry-run to apply changes")
            return True

        # Apply updates
        print("\n🔄 Applying updates...")
        updated_count = 0

        with get_connection() as conn:
            with conn.cursor() as cur:
                for track_id, audio_path, thumbnail_path in tracks_to_update:
                    new_audio = audio_path.replace('loist-music-library-staging-audio', 'loist-music-library-bucket-staging') if audio_path else None
                    new_thumb = thumbnail_path.replace('loist-music-library-staging-audio', 'loist-music-library-bucket-staging') if thumbnail_path else None

                    cur.execute("""
                        UPDATE audio_tracks
                        SET audio_gcs_path = %s, thumbnail_gcs_path = %s, updated_at = NOW()
                        WHERE id = %s
                    """, (new_audio, new_thumb, track_id))

                    updated_count += 1
                    print(f"✅ Updated {track_id}")

            conn.commit()

        print(f"\n✅ Successfully updated {updated_count} tracks!")
        return True

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    parser = argparse.ArgumentParser(
        description="Fix GCS paths in staging database",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        '--database-url',
        required=True,
        help='PostgreSQL connection URL for staging database'
    )
    parser.add_argument(
        '--no-dry-run',
        action='store_true',
        help='Actually apply the changes (default is dry run)'
    )

    args = parser.parse_args()

    dry_run = not args.no_dry_run

    success = fix_gcs_paths(args.database_url, dry_run)

    if success and not dry_run:
        print("\n🎉 GCS paths fixed! The embed endpoint should now work.")
        print("Test the embed URL again:")
        print("https://staging.loist.io/embed/ba8c6d62-0779-4af2-bef4-022138928b3c")
    elif success and dry_run:
        print("\n📋 This was a dry run. Run with --no-dry-run to apply changes.")

    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()

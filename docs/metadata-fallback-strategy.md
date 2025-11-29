# Metadata Fallback Strategy for Missing Audio Metadata

## Current Situation Analysis

### What Happened
The `process_audio_complete` operation failed with a 403 Forbidden error due to URL expiration. However, the user expects files with missing metadata to fail, indicating we need to improve handling of audio files that download successfully but have no embedded metadata (ID3 tags, etc.).

### Current System Behavior

#### Metadata Extraction Flow
1. **Download Phase**: Audio file downloads successfully
2. **Metadata Extraction Phase**:
   - Calls `extract_metadata_with_fallback()` from `src/metadata/extractor.py`
   - Uses Mutagen to extract ID3 tags, Vorbis comments, or MP4 tags
   - Attempts XMP metadata enhancement for WAV and AIF/AIFF files
   - Falls back to intelligent filename parsing if metadata incomplete
   - Uses filename as title only as final fallback
3. **Quality Validation Phase**:
   - If `validate_quality=True` (default), assesses metadata quality
   - Essential fields: `artist`, `title`, `album`
   - Optional fields: `genre`, `year`, `duration`, `channels`, `sample_rate`
   - Quality score calculation:
     - Missing essential field: -0.3 per field
     - Missing optional field: -0.1 per field
     - Default threshold: 0.3 (30%)
4. **Failure Modes**:
   - `MetadataQualityError`: Raised if quality score < threshold
   - `MetadataExtractionError`: Raised if extraction completely fails
   - Both are caught and converted to `ProcessAudioException` with `ErrorCode.EXTRACTION_FAILED`

#### Current Fallback Mechanisms
- ✅ **Filename as Title**: If no title found, uses `file_path.stem` as title
- ✅ **Filename Parsing**: Extracts artist/title from filename patterns ("Artist - Title.mp3")
- ✅ **XMP Metadata Enhancement**: For WAV, AIF/AIFF files with incomplete metadata
  - XMP chunks in AIF files (custom 'XMP ', 'iXML' chunks)
  - BWF metadata in WAV files
  - iXML session data from DAWs (Logic Pro, Pro Tools, etc.)
- ✅ **extract_with_fallback()**: Now USED in `process_audio.py` with XMP enhancement
- ❌ **External API lookup**: No MusicBrainz, Last.fm, or other metadata services (MVP scope)
- ❌ **Audio fingerprinting**: No acoustic fingerprint matching (MVP scope)

### Problem Statement

**Current Issues:**
1. Files with missing metadata fail with `EXTRACTION_FAILED` error
2. The `extract_with_fallback()` function exists but isn't used in the main processing pipeline
3. No intelligent filename parsing (e.g., "Artist - Title.mp3" → artist="Artist", title="Title")
4. No external metadata lookup services
5. Quality validation is too strict for files that legitimately have no metadata

**User Expectation:**
- Files with missing metadata should be handled gracefully
- System should attempt fallback strategies before failing
- Should still process the file even if metadata is incomplete

## Research Findings

### Best Practices for Missing Metadata

#### 1. Filename Parsing Strategies
**Common Patterns:**
- `Artist - Title.mp3`
- `Artist - Title (Album).mp3`
- `Artist - Album - Title.mp3`
- `Title.mp3` (no artist)
- `Track01.mp3` (minimal info)

**Python Libraries:**
- `mutagen` (already used): Can extract technical metadata even without tags
- `tinytag`: Lightweight alternative, good for basic extraction
- Custom regex parsing: Most flexible for pattern matching

#### 2. External Metadata Services

**MusicBrainz API:**
- Free, open-source music database
- Requires audio fingerprinting (AcoustID) for best results
- Can search by artist/title if available
- Rate limits: 1 request/second

**Last.fm API:**
- Good for artist/album metadata
- Requires API key
- Rate limits apply

**AcoustID (Audio Fingerprinting):**
- Generates acoustic fingerprints from audio
- Can match against MusicBrainz database
- Requires `chromaprint` library and `fpcalc` binary
- Most accurate but requires processing time

#### 3. Graceful Degradation Strategy

**Tiered Approach:**
1. **Tier 1**: Extract embedded metadata (current)
2. **Tier 2**: Parse filename for artist/title patterns
3. **Tier 3**: Use technical metadata (duration, format, etc.) + filename
4. **Tier 4**: External API lookup (optional, async)
5. **Tier 5**: Accept minimal metadata and continue processing

**Quality Thresholds:**
- **High Quality**: Score ≥ 0.7 (most fields present)
- **Medium Quality**: Score ≥ 0.4 (essential fields present)
- **Low Quality**: Score ≥ 0.2 (minimal metadata, but processable)
- **Unprocessable**: Score < 0.2 (reject)

## Proposed Solution

### Phase 1: Immediate Improvements (No External Dependencies)

#### 1.1 Use `extract_with_fallback()` in Processing Pipeline

**Current Code (process_audio.py:318):**
```python
metadata_dict = extract_metadata(pipeline.temp_audio_path)
```

**Proposed Change:**
```python
from src.metadata import extract_metadata_with_fallback

# Use fallback extraction that handles quality issues gracefully
metadata_dict, was_repaired = extract_metadata_with_fallback(pipeline.temp_audio_path)
if was_repaired:
    logger.info(f"Metadata was repaired for {pipeline.audio_id}")
```

**Benefits:**
- Already implemented, just needs to be used
- Handles `MetadataQualityError` gracefully
- Attempts repair before failing

#### 1.2 Implement Filename Parsing

**Implemented Functions:**

**`parse_filename_metadata()` - Main parsing function**
- **Location:** `src/metadata/extractor.py`
- **Purpose:** Parse metadata from filename patterns with preprocessing
- **Features:**
  - Removes leading track numbers (01., 1-, (01), [01])
  - Handles multiple parsing strategies (most specific first)
  - Only fills missing metadata fields (doesn't overwrite existing)
  - Supports artist/title, artist/title/album, and title-only patterns

**`parse_filename_metadata()` Implementation:**

```python
def parse_filename_metadata(file_path: Path | str, existing_metadata: Dict[str, Any]) -> Dict[str, Any]:
    """
    Parse metadata from filename patterns.

    Handles common filename patterns and preprocesses to handle inconsistent formats:
    - Removes leading track numbers (01., 1-, etc.)
    - Handles year patterns (YYYY, (YYYY))
    - Multiple parsing attempts for complex patterns

    Common patterns after preprocessing:
    - "Artist - Title.mp3"
    - "Artist - Title (Album).mp3"
    - "Artist - Album - Title.mp3"
    - "Title.mp3" (no artist)
    - "Track01.mp3" (minimal info)
    """
    file_path = Path(file_path)
    filename = file_path.stem  # Without extension
    parsed = {}

    # Preprocessing: Clean up common prefixes and patterns
    cleaned_filename = _preprocess_filename(filename)

    # Try multiple parsing strategies in order of specificity (most specific first)
    strategies = [
        _parse_artist_album_title_pattern,  # 3 parts: Artist - Album - Title
        _parse_artist_title_pattern,        # 2 parts: Artist - Title
        _parse_title_only_pattern           # 1 part: Title only
    ]

    for strategy in strategies:
        result = strategy(cleaned_filename)
        if result:
            parsed.update(result)
            break  # Take first successful parse

    # Only fill in missing fields (don't overwrite existing metadata)
    result = {}
    for key, value in parsed.items():
        if not existing_metadata.get(key) and value:
            result[key] = value

    if result:
        logger.debug(f"Parsed metadata from filename '{filename}': {result}")

    return result
```

**`_preprocess_filename()` - Filename cleaning function**
```python
def _preprocess_filename(filename: str) -> str:
    """
    Preprocess filename to remove common prefixes and normalize patterns.

    Handles:
    - Leading track numbers: "01. ", "1-", "(01) "
    - Year patterns: " (2020)", " - 2020"
    - Extra spaces and separators
    """
    # Remove leading track numbers (with various separators)
    patterns = [
        r'^\d+\.\s*',  # "01. "
        r'^\d+-\s*',   # "01-"
        r'^\(\d+\)\s*', # "(01) "
        r'^\[\d+\]\s*', # "[01] "
        r'^\d+\s*-\s*', # "01 - "
    ]

    cleaned = filename
    for pattern in patterns:
        cleaned = re.sub(pattern, '', cleaned, flags=re.IGNORECASE)

    return cleaned.strip()
```

**Parsing Strategy Functions:**

**`_parse_artist_title_pattern()` - Handles "Artist - Title" patterns**
```python
def _parse_artist_title_pattern(filename: str) -> Optional[Dict[str, str]]:
    """
    Parse patterns like "Artist - Title" or "Artist - Title (Album)".
    """
    # Pattern: "Artist - Title (Album)" - handle album in parentheses first
    match = re.match(r'^(.+?)\s*-\s*(.+?)\s*\(([^)]+)\)$', filename)
    if match:
        artist = match.group(1).strip()
        title = match.group(2).strip()
        album = match.group(3).strip()

        # Check if album looks like a year (4 digits)
        if re.match(r'^\d{4}$', album):
            return {
                'artist': artist,
                'title': title,
                'year': album
            }
        else:
            return {
                'artist': artist,
                'title': title,
                'album': album
            }

    # Pattern: "Artist - Title"
    match = re.match(r'^(.+?)\s*-\s*(.+)$', filename)
    if match:
        artist = match.group(1).strip()
        title = match.group(2).strip()

        # Skip if title is just a track number or very short
        if re.match(r'^\d{1,3}$', title) or len(title) < 2:
            return None

        return {
            'artist': artist,
            'title': title
        }

    return None
```

**`_parse_artist_album_title_pattern()` - Handles "Artist - Album - Title" patterns**
```python
def _parse_artist_album_title_pattern(filename: str) -> Optional[Dict[str, str]]:
    """
    Parse patterns like "Artist - Album - Title".
    """
    match = re.match(r'^(.+?)\s*-\s*(.+?)\s*-\s*(.+)$', filename)
    if match:
        artist = match.group(1).strip()
        album = match.group(2).strip()
        title = match.group(3).strip()

        # Check if album looks like a year (4 digits)
        if re.match(r'^\d{4}$', album):
            return {
                'artist': artist,
                'title': title,
                'year': album
            }
        else:
            return {
                'artist': artist,
                'album': album,
                'title': title
            }

    return None
```

**`_parse_title_only_pattern()` - Handles title-only patterns**
```python
def _parse_title_only_pattern(filename: str) -> Optional[Dict[str, str]]:
    """
    Parse patterns that are just titles, possibly with years.
    """
    # Check if it's a reasonable title (not just numbers/symbols)
    if len(filename) < 2 or re.match(r'^[\d\s\-\(\)\[\]]+$', filename):
        return None

    # Pattern: "Title (Year)"
    match = re.match(r'^(.+?)\s*\((\d{4})\)$', filename)
    if match:
        title = match.group(1).strip()
        year = match.group(2).strip()
        return {
            'title': title,
            'year': year
        }

    # Pattern: "Title - Year"
    match = re.match(r'^(.+?)\s*-\s*(\d{4})$', filename)
    if match:
        title = match.group(1).strip()
        year = match.group(2).strip()
        return {
            'title': title,
            'year': year
        }

    # Just title
    return {
        'title': filename
    }
```

**Supported Filename Patterns:**
- ✅ `"The Beatles - Hey Jude.mp3"` → `{'artist': 'The Beatles', 'title': 'Hey Jude'}`
- ✅ `"Queen - Bohemian Rhapsody (A Night At The Opera).mp3"` → `{'artist': 'Queen', 'title': 'Bohemian Rhapsody', 'album': 'A Night At The Opera'}`
- ✅ `"Pink Floyd - The Wall - Comfortably Numb.mp3"` → `{'artist': 'Pink Floyd', 'album': 'The Wall', 'title': 'Comfortably Numb'}`
- ✅ `"01. The Beatles - Hey Jude.mp3"` → Track numbers removed, same result
- ✅ `"Song Title (2020).mp3"` → `{'title': 'Song Title', 'year': '2020'}`
- ✅ `"Untitled Track.mp3"` → `{'title': 'Untitled Track'}`

**Integration Point:**
Filename parsing is called after metadata extraction in `process_audio_complete()`:
```python
# Parse filename for missing metadata fields
filename_metadata = parse_filename_metadata(pipeline.temp_audio_path, metadata_dict)
if filename_metadata:
    metadata_dict.update(filename_metadata)
    logger.info(f"Enhanced metadata from filename: {filename_metadata}")
```

### Phase 2: Enhanced Fallback (Optional External Services)

#### 2.1 Adjust Quality Threshold for Missing Metadata

**Current Behavior:**
- Default threshold: 0.3 (30%)
- Missing artist + title + album = score 0.1 (fails)

**Proposed Behavior:**
- Use adaptive threshold based on extraction method
- If filename parsing provides artist/title: threshold 0.2
- If only technical metadata: threshold 0.1 (accept minimal)
- Always allow processing if we have at least filename as title

**Implementation:**
```python
# Calculate quality threshold dynamically
if metadata_dict.get('artist') and metadata_dict.get('title'):
    quality_threshold = 0.3  # Standard threshold
elif metadata_dict.get('title'):
    quality_threshold = 0.2  # Lower threshold for title-only
else:
    quality_threshold = 0.1  # Minimal threshold (filename fallback)
```

### Phase 2: Enhanced Fallback (Optional External Services)

#### 2.1 Audio Fingerprinting with AcoustID

**Requirements:**
- Install `chromaprint` library
- Install `fpcalc` binary (AcoustID fingerprint calculator)
- MusicBrainz API key (optional, for lookup)

**Implementation:**
```python
import subprocess
import requests

def generate_acoustid_fingerprint(audio_path: Path) -> Optional[str]:
    """Generate AcoustID fingerprint for audio file."""
    try:
        result = subprocess.run(
            ['fpcalc', '-json', str(audio_path)],
            capture_output=True,
            text=True,
            timeout=30
        )
        if result.returncode == 0:
            import json
            data = json.loads(result.stdout)
            return data.get('fingerprint')
    except (subprocess.TimeoutExpired, FileNotFoundError, json.JSONDecodeError):
        pass
    return None

def lookup_metadata_by_fingerprint(fingerprint: str) -> Optional[Dict[str, Any]]:
    """Lookup metadata using AcoustID and MusicBrainz."""
    # Implementation would query AcoustID API, then MusicBrainz
    # This is async and optional - don't block processing
    pass
```

**Note:** This is Phase 2 - implement only if needed for production.

#### 2.2 External API Lookup (Async, Non-Blocking)

**Strategy:**
- Process file with available metadata immediately
- Trigger async background task for external lookup
- Update database if better metadata found later

**Implementation:**
```python
# In process_audio.py, after successful processing:
if metadata_dict.get('_quality_report', {}).get('quality_score', 1.0) < 0.5:
    # Low quality metadata - trigger async lookup
    enqueue_metadata_lookup_task(
        audio_id=pipeline.audio_id,
        audio_path=pipeline.gcs_audio_path,
        current_metadata=metadata_dict
    )
```

## Implementation Plan

### Step 1: Use Existing Fallback Function
**File:** `src/tools/process_audio.py`
**Change:** Replace `extract_metadata()` with `extract_metadata_with_fallback()`
**Effort:** 5 minutes
**Risk:** Low (function already tested)

### Step 2: Add Filename Parsing
**File:** `src/metadata/extractor.py` (new function)
**Change:** Add `parse_filename_metadata()` function
**Effort:** 1-2 hours
**Risk:** Low (pure function, easy to test)

### Step 3: Integrate Filename Parsing
**File:** `src/tools/process_audio.py`
**Change:** Call filename parsing after metadata extraction
**Effort:** 15 minutes
**Risk:** Low

### Step 4: Adjust Quality Thresholds
**File:** `src/tools/process_audio.py`
**Change:** Use adaptive quality threshold based on available metadata
**Effort:** 30 minutes
**Risk:** Medium (need to test edge cases)

### Step 5: Add Tests
**Files:** `tests/test_metadata_extraction.py`, `tests/test_process_audio.py`
**Change:** Add tests for missing metadata scenarios
**Effort:** 2-3 hours
**Risk:** Low

### Step 6: Documentation
**File:** `docs/metadata-fallback-strategy.md` (this file)
**Change:** Update with implementation details
**Effort:** 30 minutes
**Risk:** None

## Testing Strategy

### Test Cases

1. **File with no metadata tags**
   - Filename: "The Beatles - I'm Only Sleeping.mp3"
   - Expected: Parses artist="The Beatles", title="I'm Only Sleeping"
   - Should process successfully

2. **File with partial metadata**
   - Has title in tags, no artist
   - Filename: "Artist Name - Title.mp3"
   - Expected: Uses title from tags, artist from filename
   - Should process successfully

3. **File with minimal filename**
   - Filename: "track01.mp3"
   - Expected: title="track01", no artist
   - Should process with low quality score but succeed

4. **File with no metadata and bad filename**
   - Filename: "asdfghjkl.mp3"
   - Expected: title="asdfghjkl", no artist
   - Should process with very low quality score but succeed

5. **File with complete metadata**
   - Has all tags
   - Expected: No filename parsing needed
   - Should process with high quality score

## Success Criteria

✅ Files with missing metadata process successfully (don't fail with EXTRACTION_FAILED)
✅ Filename patterns are intelligently parsed for artist/title
✅ Quality scores reflect actual metadata completeness
✅ System gracefully degrades from high-quality to minimal metadata
✅ No breaking changes to existing functionality
✅ All tests pass

## Future Enhancements (Post-MVP)

- Audio fingerprinting with AcoustID
- MusicBrainz API integration
- Last.fm API integration
- User-provided metadata override
- Batch metadata enrichment job
- Machine learning-based metadata prediction

## References

- [Mutagen Documentation](https://mutagen.readthedocs.io/)
- [AcoustID Documentation](https://acoustid.org/)
- [MusicBrainz API](https://musicbrainz.org/doc/MusicBrainz_API)
- [Best Practices for Audio Metadata](https://www.loc.gov/preservation/digital/formats/fdd/fdd000105.shtml)

## Implementation Results

### ✅ **Phase 1 Successfully Deployed**

**Test Results (2025-11-18):**

**Before Fix:**
```json
{
  "success": true,
  "metadata": {
    "Product": {
      "Artist": "thebeatles",
      "Title": "tmpcxkpy6ok",  // ❌ Temp filename
      "Album": ""
    }
  }
}
```

**After Fix:**
```json
{
  "success": true,
  "metadata": {
    "Product": {
      "Artist": "thebeatles",    // ✅ Correct
      "Title": "imonlysleeping", // ✅ Correct - parsed from filename
      "Album": ""
    }
  }
}
```

**What Works Now:**
- ✅ URL filename extraction: `https://tmpfiles.org/dl/9534084/thebeatles-imonlysleeping.mp3` → `"thebeatles-imonlysleeping.mp3"`
- ✅ Intelligent filename parsing: `"thebeatles-imonlysleeping"` → `{"artist": "thebeatles", "title": "imonlysleeping"}`
- ✅ Temp filename override: `parse_filename_metadata()` now detects and overrides temp filenames (`tmp[a-z0-9]{6,}` patterns)
- ✅ End-to-end processing: Files with missing embedded metadata now process successfully with parsed metadata

**Technical Implementation:**
- Modified `parse_filename_metadata()` to include `_is_temp_filename()` detection
- Added logic to override existing temp filename values with parsed metadata
- Maintained backward compatibility for legitimate existing metadata
- No breaking changes to existing functionality

### 🎯 **Success Criteria Met**

- ✅ Files with missing metadata process successfully (don't fail with EXTRACTION_FAILED)
- ✅ Filename patterns are intelligently parsed for artist/title
- ✅ Quality scores reflect actual metadata completeness
- ✅ System gracefully degrades from high-quality to minimal metadata
- ✅ No breaking changes to existing functionality
- ✅ End-to-end testing confirms working implementation

---

**Last Updated:** 2025-11-18
**Status:** ✅ **FULLY IMPLEMENTED AND TESTED** - Phase 1 Complete
**Phase 1 Features:**
- ✅ `extract_with_fallback()` integration
- ✅ Filename parsing with preprocessing
- ✅ Temp filename override logic
- ✅ Adaptive quality thresholds
- ✅ End-to-end testing confirmed working
- ✅ Production deployment ready

**Phase 2 Features (Future):**
- 🔄 Audio fingerprinting with AcoustID
- 🔄 MusicBrainz API integration
- 🔄 External metadata enrichment


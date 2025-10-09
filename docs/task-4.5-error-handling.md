# Task 4.5: Error Handling for Missing or Corrupt Metadata

## Overview

This document describes the comprehensive error handling implementation for audio metadata extraction, including detection of missing/corrupt metadata, quality assessment, fallback mechanisms, and repair strategies.

## Implementation Summary

### New Classes and Functions

#### 1. `MetadataQualityError`
Custom exception raised when metadata quality issues are detected.

**Attributes:**
- `quality_score` (float): Quality score (0.0-1.0)
- `issues` (List[str]): List of detected issues

**Usage:**
```python
try:
    metadata = extract_metadata("song.mp3", quality_threshold=0.8)
except MetadataQualityError as e:
    print(f"Quality issues: {e.issues}")
    print(f"Quality score: {e.quality_score}")
```

#### 2. `MetadataQualityAssessment`
Assesses metadata quality and completeness, identifying issues and calculating quality scores.

**Quality Assessment Criteria:**
- **Essential fields** (0.3 penalty each if missing): artist, title, album
- **Optional fields** (0.1 penalty each if missing): genre, year, duration, channels, sample_rate
- **Corrupt data** (0.1-0.2 penalty): Invalid years, durations, sample rates, channels
- **Suspicious text** (0.05-0.1 penalty): Empty strings, excessively long fields (>500 chars)

**Quality Levels:**
- **Excellent**: Score ≥ 0.9
- **Good**: Score ≥ 0.7
- **Fair**: Score ≥ 0.5
- **Poor**: Score ≥ 0.3
- **Very Poor**: Score < 0.3

**Usage:**
```python
from src.metadata import assess_metadata_quality

# Assess extracted metadata
report = assess_metadata_quality(metadata, "song.mp3")
print(f"Quality: {report['quality_level']} ({report['quality_score']})")
print(f"Completeness: {report['metadata_completeness']}%")
if report['has_issues']:
    print(f"Issues: {report['issues']}")
```

**Report Structure:**
```python
{
    'file_path': 'song.mp3',
    'quality_score': 0.85,
    'quality_level': 'Good',
    'issues': ['Missing optional fields: genre, year'],
    'has_issues': True,
    'metadata_completeness': 81.8
}
```

### Enhanced Functions

#### 1. `extract_metadata()`
Enhanced with quality validation parameters.

**New Parameters:**
- `validate_quality` (bool): Enable quality validation (default: True)
- `quality_threshold` (float): Minimum acceptable quality score 0.0-1.0 (default: 0.3)

**Behavior:**
- Extracts metadata as before
- Performs quality assessment if `validate_quality=True`
- Raises `MetadataQualityError` if score < threshold
- Adds `_quality_report` to returned metadata dictionary

**Usage:**
```python
from src.metadata import extract_metadata, MetadataQualityError

# Extract with quality validation
try:
    metadata = extract_metadata("song.mp3", quality_threshold=0.7)
    print(f"Quality: {metadata['_quality_report']['quality_level']}")
except MetadataQualityError as e:
    print(f"Quality too low: {e.quality_score}")
    print(f"Issues: {e.issues}")

# Extract without quality validation (lenient mode)
metadata = extract_metadata("song.mp3", validate_quality=False)
```

#### 2. `extract_metadata_with_fallback()`
New function that extracts metadata with automatic repair for corrupt data.

**Features:**
- Attempts normal extraction with quality validation
- On `MetadataQualityError`, attempts repair
- Returns tuple: `(metadata, was_repaired)`

**Usage:**
```python
from src.metadata import extract_metadata_with_fallback

# Extract with automatic repair
metadata, was_repaired = extract_metadata_with_fallback("song.mp3")
if was_repaired:
    print("Metadata was repaired")
    print(f"Quality: {metadata['_quality_report']['quality_level']}")
```

#### 3. `validate_and_repair_metadata()`
Static method to validate and repair corrupted metadata.

**Repair Actions:**
- **Invalid years** (< 1900 or > 2030): Set to None
- **Invalid durations** (≤ 0 or > 86400): Set to None
- **Invalid sample rates** (≤ 0 or > 192000): Set to None
- **Invalid channels** (≤ 0 or > 8): Set to None
- **Empty text fields**: Set to None
- **Excessively long text** (> 500 chars): Truncate to 500 chars

**Usage:**
```python
from src.metadata import MetadataExtractor

# Repair corrupt metadata
repaired = MetadataExtractor.validate_and_repair_metadata(
    corrupt_metadata, 
    Path("song.mp3")
)
```

## Error Handling Patterns

### Pattern 1: Graceful Degradation
Files with missing metadata don't fail extraction; they return None values.

```python
# File with no ID3 tags still extracts successfully
metadata = extract_metadata("no_tags.mp3", validate_quality=False)
# Returns: {'artist': None, 'title': 'no_tags', ...}
```

### Pattern 2: Quality Thresholds
Set minimum quality requirements based on use case.

```python
# Strict quality for production
try:
    metadata = extract_metadata("song.mp3", quality_threshold=0.8)
except MetadataQualityError:
    # Reject file or request re-upload

# Lenient for user libraries
metadata = extract_metadata("song.mp3", quality_threshold=0.3)
```

### Pattern 3: Automatic Repair
Use fallback extraction for user-uploaded content.

```python
# Accept files but repair issues
metadata, was_repaired = extract_metadata_with_fallback("song.mp3")
if was_repaired:
    log_warning(f"Repaired metadata issues in {filename}")
```

### Pattern 4: Logging and Monitoring
Track metadata quality for analytics.

```python
metadata = extract_metadata("song.mp3")
report = metadata['_quality_report']

# Log quality metrics
log_metadata_quality(
    file=filename,
    score=report['quality_score'],
    level=report['quality_level'],
    completeness=report['metadata_completeness'],
    issues=report['issues']
)
```

## Logging Behavior

The error handling implementation provides comprehensive logging:

### Info Level
- Successful extractions with quality scores
- Metadata repairs with before/after quality

### Warning Level
- Missing ID3 tags
- No artwork found
- Quality issues detected
- Individual field repairs

### Error Level
- Failed extractions
- Failed repairs

**Example Log Output:**
```
INFO: Metadata quality assessment for song.mp3: Score=0.85, Level=Good, Completeness=81.8%
WARNING: Metadata quality issues in song.mp3: ['Missing optional fields: genre, year']
WARNING: Repairing invalid year 1800 in corrupt.mp3
INFO: Metadata repaired for corrupt.mp3: Score=0.65, Level=Fair
```

## Testing

Comprehensive test suite in `tests/test_metadata_extraction.py`:

### Test Classes
1. **TestMetadataQualityAssessment**: Quality scoring and detection
2. **TestMetadataQualityError**: Exception handling
3. **TestMetadataRepair**: Repair functionality
4. **TestConvenienceFunctions**: Wrapper functions

### Test Coverage
- ✅ Excellent metadata (score ≥ 0.9)
- ✅ Missing essential fields
- ✅ Missing optional fields
- ✅ Corrupt data (invalid years, durations, etc.)
- ✅ Suspicious text (empty, too long)
- ✅ Quality threshold enforcement
- ✅ Metadata repair
- ✅ Fallback extraction
- ✅ Convenience functions

## Integration Examples

### Example 1: File Upload API
```python
@app.post("/upload")
async def upload_audio(file: UploadFile):
    try:
        # Strict validation for uploads
        metadata = extract_metadata(
            file.path, 
            quality_threshold=0.7
        )
        return {"status": "success", "metadata": metadata}
    except MetadataQualityError as e:
        return {
            "status": "quality_error",
            "score": e.quality_score,
            "issues": e.issues
        }
```

### Example 2: Library Import
```python
def import_library(directory):
    for audio_file in directory.glob("*.mp3"):
        # Lenient with automatic repair
        metadata, was_repaired = extract_metadata_with_fallback(audio_file)
        
        if was_repaired:
            logger.warning(f"Repaired metadata in {audio_file.name}")
        
        # Store metadata
        db.store_metadata(audio_file, metadata)
```

### Example 3: Quality Monitoring
```python
def analyze_library_quality(directory):
    quality_stats = []
    
    for audio_file in directory.glob("*.mp3"):
        metadata = extract_metadata(audio_file, validate_quality=False)
        report = metadata['_quality_report']
        
        quality_stats.append({
            'file': audio_file.name,
            'score': report['quality_score'],
            'level': report['quality_level'],
            'completeness': report['metadata_completeness']
        })
    
    # Generate report
    avg_score = sum(s['score'] for s in quality_stats) / len(quality_stats)
    print(f"Average quality score: {avg_score:.2f}")
```

## Best Practices

### 1. Choose Appropriate Quality Thresholds
- **Production uploads**: 0.7-0.9 (Good to Excellent)
- **User libraries**: 0.3-0.5 (Poor to Fair)
- **Testing**: 0.0 or `validate_quality=False`

### 2. Use Fallback Extraction for User Content
When users upload their own files, use `extract_metadata_with_fallback()` to be forgiving of quality issues.

### 3. Log Quality Issues
Always log quality issues for monitoring and debugging.

### 4. Don't Fail Silently
Use the `_quality_report` to inform users about metadata quality.

### 5. Consider Context
Essential fields vary by use case:
- Music player: artist, title
- Library management: artist, title, album
- Podcast app: title, duration

## API Reference

### Classes

#### `MetadataQualityError(message, quality_score, issues)`
Exception for metadata quality issues.

#### `MetadataQualityAssessment(metadata, file_path)`
Assesses metadata quality.

**Methods:**
- `get_quality_report()` → Dict[str, Any]

### Functions

#### `extract_metadata(file_path, validate_quality=True, quality_threshold=0.3)`
Extract metadata with quality validation.

#### `extract_metadata_with_fallback(file_path)`
Extract metadata with automatic repair.

#### `assess_metadata_quality(metadata, file_path)`
Assess metadata quality independently.

#### `MetadataExtractor.validate_and_repair_metadata(metadata, file_path)`
Repair corrupted metadata.

## Validation Ranges

### Numeric Fields
- **Year**: 1900-2030
- **Duration**: 0-86400 seconds (24 hours)
- **Sample Rate**: 0-192000 Hz
- **Channels**: 1-8
- **Bitrate**: > 0 kbps

### Text Fields
- **Maximum length**: 500 characters
- **Empty strings**: Detected and set to None

## Future Enhancements

Potential improvements for future versions:

1. **Configurable validation rules**: Allow custom thresholds per field
2. **Machine learning**: Learn quality patterns from user feedback
3. **Format-specific rules**: Different validation for MP3 vs. FLAC
4. **Automatic tag lookup**: Use online databases to fill missing fields
5. **Batch quality analysis**: Analyze entire libraries efficiently

## Conclusion

The error handling implementation provides:
- ✅ Comprehensive quality assessment
- ✅ Flexible validation thresholds
- ✅ Automatic repair mechanisms
- ✅ Detailed logging and reporting
- ✅ Production-ready error handling
- ✅ Extensive test coverage

This ensures robust metadata extraction that gracefully handles missing or corrupt data while providing detailed feedback for monitoring and debugging.


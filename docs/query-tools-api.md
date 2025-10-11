# Query Tools API Documentation

## Overview

The Loist Music Library MCP Server provides two query tools for retrieving and searching processed audio:

1. **get_audio_metadata** - Retrieve metadata for a specific audio track by ID
2. **search_library** - Search across all audio tracks with advanced filtering

Both tools are read-only operations that query the PostgreSQL database.

---

## Tool 1: get_audio_metadata

### Purpose

Retrieve complete metadata for a previously processed audio track using its unique ID.

### Input Schema

```typescript
{
  audioId: string  // UUID format (36 characters)
}
```

#### Validation Rules

- **audioId**: Must be a valid UUID format (lowercase)
  - Pattern: `^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$`
  - Length: Exactly 36 characters
  - Example: `"550e8400-e29b-41d4-a716-446655440000"`

### Output Schema

#### Success Response

```json
{
  "success": true,
  "audioId": "550e8400-e29b-41d4-a716-446655440000",
  "metadata": {
    "Product": {
      "Artist": "The Beatles",
      "Title": "Hey Jude",
      "Album": "Hey Jude",
      "MBID": null,
      "Genre": ["Rock"],
      "Year": 1968
    },
    "Format": {
      "Duration": 431.0,
      "Channels": 2,
      "Sample rate": 44100,
      "Bitrate": 320000,
      "Format": "MP3"
    },
    "urlEmbedLink": "https://loist.io/embed/550e8400-e29b-41d4-a716-446655440000"
  },
  "resources": {
    "audio": "music-library://audio/550e8400-e29b-41d4-a716-446655440000/stream",
    "thumbnail": "music-library://audio/550e8400-e29b-41d4-a716-446655440000/thumbnail",
    "waveform": null
  }
}
```

#### Error Response

```json
{
  "success": false,
  "error": "RESOURCE_NOT_FOUND",
  "message": "Audio track with ID '550e8400-e29b-41d4-a716-446655440000' was not found",
  "details": {
    "audioId": "550e8400-e29b-41d4-a716-446655440000"
  }
}
```

### Error Codes

| Error Code | Description | When It Occurs |
|-----------|-------------|----------------|
| `RESOURCE_NOT_FOUND` | Audio track not found | Invalid or non-existent audioId |
| `INVALID_QUERY` | Invalid input | Malformed UUID or missing audioId |
| `DATABASE_ERROR` | Database query failed | Connection or query execution error |

### Usage Examples

#### Python (Async)

```python
from src.tools import get_audio_metadata

# Get metadata by ID
result = await get_audio_metadata({
    "audioId": "550e8400-e29b-41d4-a716-446655440000"
})

if result["success"]:
    print(f"Title: {result['metadata']['Product']['Title']}")
    print(f"Artist: {result['metadata']['Product']['Artist']}")
    print(f"Stream: {result['resources']['audio']}")
else:
    print(f"Error: {result['error']} - {result['message']}")
```

#### MCP Protocol (JSON-RPC)

```json
{
  "jsonrpc": "2.0",
  "method": "tools/call",
  "params": {
    "name": "get_audio_metadata",
    "arguments": {
      "audioId": "550e8400-e29b-41d4-a716-446655440000"
    }
  },
  "id": 1
}
```

### Performance

- **Average response time**: <50ms
- **Database query**: Single SELECT by primary key (O(1) lookup)
- **Caching**: Response can be cached indefinitely (metadata doesn't change)

---

## Tool 2: search_library

### Purpose

Search across all processed audio tracks using full-text search with optional advanced filters.

### Input Schema

```typescript
{
  query: string,              // Required: search query (1-500 chars)
  filters?: {                 // Optional filters
    genre?: string[],         // List of genres (OR logic)
    year?: {                  // Year range
      min?: number,           // Minimum year (1900-2100)
      max?: number            // Maximum year (1900-2100)
    },
    duration?: {              // Duration range in seconds
      min?: number,           // Minimum duration (>=0)
      max?: number            // Maximum duration (>=0)
    },
    format?: string[],        // Audio formats (MP3, FLAC, etc.)
    artist?: string,          // Artist name (partial match)
    album?: string            // Album name (partial match)
  },
  limit?: number,             // Results per page (1-100, default: 20)
  offset?: number,            // Results to skip (0-10000, default: 0)
  sortBy?: string,            // Sort field (default: "relevance")
  sortOrder?: string          // Sort order (asc/desc, default: "desc")
}
```

#### Validation Rules

- **query**: 
  - Required, 1-500 characters
  - Sanitized to remove control characters
  - Stripped of leading/trailing whitespace
  
- **limit**: 1-100 (prevents excessive result sets)
- **offset**: 0-10000 (prevents deep pagination performance issues)
- **year.min / year.max**: 1900-2100
- **duration.min / duration.max**: >=0
- **sortBy**: One of: `relevance`, `title`, `artist`, `year`, `duration`, `created_at`
- **sortOrder**: `asc` or `desc`

### Output Schema

#### Success Response

```json
{
  "success": true,
  "results": [
    {
      "audioId": "550e8400-e29b-41d4-a716-446655440000",
      "metadata": {
        "Product": {
          "Artist": "The Beatles",
          "Title": "Hey Jude",
          "Album": "Hey Jude",
          "MBID": null,
          "Genre": ["Rock"],
          "Year": 1968
        },
        "Format": {
          "Duration": 431.0,
          "Channels": 2,
          "Sample rate": 44100,
          "Bitrate": 320000,
          "Format": "MP3"
        },
        "urlEmbedLink": "https://loist.io/embed/550e8400-e29b-41d4-a716-446655440000"
      },
      "score": 0.95
    }
  ],
  "total": 150,
  "limit": 20,
  "offset": 0,
  "hasMore": true
}
```

#### Error Response

```json
{
  "success": false,
  "error": "INVALID_QUERY",
  "message": "Invalid search input: query too long",
  "details": {
    "validation_errors": "Field query: max_length=500"
  }
}
```

### Error Codes

| Error Code | Description | When It Occurs |
|-----------|-------------|----------------|
| `INVALID_QUERY` | Invalid search parameters | Validation failure, query too long, etc. |
| `INVALID_FILTER` | Invalid filter parameters | Malformed filter values |
| `PAGINATION_ERROR` | Invalid pagination | Offset too large |
| `DATABASE_ERROR` | Database query failed | Search execution error |

### Usage Examples

#### Simple Search

```python
from src.tools import search_library

# Basic search
result = await search_library({
    "query": "beatles",
    "limit": 20
})

if result["success"]:
    for track in result["results"]:
        print(f"{track['metadata']['Product']['Title']} - {track['score']}")
    print(f"\nTotal: {result['total']}, More: {result['hasMore']}")
```

#### Advanced Search with Filters

```python
# Search with multiple filters
result = await search_library({
    "query": "rock music",
    "filters": {
        "genre": ["Rock", "Classic Rock"],
        "year": {"min": 1960, "max": 1980},
        "duration": {"min": 180, "max": 360},
        "format": ["MP3", "FLAC"]
    },
    "limit": 50,
    "offset": 0,
    "sortBy": "year",
    "sortOrder": "desc"
})
```

#### Pagination Example

```python
# Page 1
page1 = await search_library({
    "query": "beatles",
    "limit": 20,
    "offset": 0
})

# Page 2 (if hasMore is true)
if page1["hasMore"]:
    page2 = await search_library({
        "query": "beatles",
        "limit": 20,
        "offset": 20
    })
```

#### Artist-Specific Search

```python
# Search for specific artist
result = await search_library({
    "query": "jude",
    "filters": {
        "artist": "Beatles"  # Partial match, case-insensitive
    },
    "limit": 10
})
```

### Search Features

#### Full-Text Search

- **Searches across**: Title, Artist, Album, Genre
- **Search type**: PostgreSQL full-text search with GIN index
- **Query processing**: Automatic tokenization and stemming
- **Relevance scoring**: ts_rank() for result ordering

#### Filter Logic

All filters use **AND logic** (all conditions must match):
- Genre filter uses **OR logic** within the list (match any genre)
- Format filter uses **OR logic** within the list (match any format)
- Year/Duration use range matching (inclusive)
- Artist/Album use case-insensitive partial matching

#### Sort Options

| Field | Description | Performance |
|-------|-------------|-------------|
| `relevance` | Full-text search score (default) | Fast (indexed) |
| `title` | Alphabetical by title | Fast (indexed) |
| `artist` | Alphabetical by artist | Fast (indexed) |
| `year` | By release year | Fast (indexed) |
| `duration` | By track length | Medium |
| `created_at` | By processing time | Fast (indexed) |

### Performance

#### Response Times

- **Simple search**: <100ms
- **Search with filters**: <200ms
- **Large result sets** (50-100): <300ms

#### Optimization Tips

1. **Use specific filters** to narrow results before full-text search
2. **Limit result size** to what you need (default: 20 is optimal)
3. **Avoid deep pagination** (offset >1000 slows down)
4. **Cache common searches** at application level
5. **Use relevance sorting** (fastest) when possible

#### Performance Limits

- **Max limit**: 100 results per request
- **Max offset**: 10,000 (prevents deep pagination issues)
- **Query timeout**: 30 seconds
- **Concurrent requests**: Limited by database pool (10 connections)

### Pagination Best Practices

#### Offset-Based (Current Implementation)

```python
# Good: First few pages
for page in range(5):
    result = await search_library({
        "query": "beatles",
        "limit": 20,
        "offset": page * 20
    })
```

#### Deep Pagination Warning

```python
# ⚠️ Avoid: Deep pagination is slow
result = await search_library({
    "query": "music",
    "limit": 20,
    "offset": 5000  # Slow! Consider alternative approach
})
```

**Alternative for deep pagination:**
- Use more specific search queries
- Apply filters to narrow results
- Implement cursor-based pagination (future enhancement)

### Filter Examples

#### Genre Filter

```python
# Find Rock or Jazz tracks
result = await search_library({
    "query": "music",
    "filters": {
        "genre": ["Rock", "Jazz"]  # OR logic
    }
})
```

#### Year Range Filter

```python
# Find tracks from the 1960s
result = await search_library({
    "query": "classic",
    "filters": {
        "year": {
            "min": 1960,
            "max": 1969
        }
    }
})
```

#### Duration Filter

```python
# Find tracks between 3-6 minutes
result = await search_library({
    "query": "song",
    "filters": {
        "duration": {
            "min": 180,  # 3 minutes
            "max": 360   // 6 minutes
        }
    }
})
```

#### Format Filter

```python
# Find only lossless formats
result = await search_library({
    "query": "audio",
    "filters": {
        "format": ["FLAC", "WAV"]
    }
})
```

#### Combined Filters

```python
# Complex query with multiple filters
result = await search_library({
    "query": "rock",
    "filters": {
        "genre": ["Rock", "Hard Rock"],
        "year": {"min": 1970, "max": 1980"},
        "duration": {"min": 240, "max": 480},
        "format": ["MP3", "FLAC"],
        "artist": "Zeppelin"  # Partial match: "Led Zeppelin"
    },
    "limit": 30,
    "sortBy": "year",
    "sortOrder": "asc"
})
```

---

## Security

### Query Sanitization

Both tools implement automatic query sanitization:

- ✅ Remove null bytes and control characters
- ✅ Strip leading/trailing whitespace
- ✅ Parameterized queries (SQL injection prevention)
- ✅ UUID format validation
- ✅ Input length limits

### Safe Search Practices

```python
# ✅ Safe: Queries are automatically sanitized
result = await search_library({
    "query": "test'; DROP TABLE--"  # Will be sanitized
})

# ✅ Safe: Filters use parameterized queries
result = await search_library({
    "query": "music",
    "filters": {
        "artist": "'; DELETE FROM"  # Will be parameterized
    }
})
```

---

## Error Handling

### Common Errors

#### Audio Not Found

```python
result = await get_audio_metadata({
    "audioId": "00000000-0000-0000-0000-000000000000"
})

# Response:
{
    "success": false,
    "error": "RESOURCE_NOT_FOUND",
    "message": "Audio track with ID '...' was not found",
    "details": {"audioId": "00000000-0000-0000-0000-000000000000"}
}
```

#### Invalid UUID Format

```python
result = await get_audio_metadata({
    "audioId": "not-a-uuid"
})

# Response:
{
    "success": false,
    "error": "INVALID_QUERY",
    "message": "Invalid input: audioId must be a valid UUID format",
    "details": {"validation_errors": "..."}
}
```

#### Query Too Long

```python
result = await search_library({
    "query": "a" * 501  # Exceeds 500 char limit
})

# Response:
{
    "success": false,
    "error": "INVALID_QUERY",
    "message": "Invalid search input: query too long",
    "details": {"validation_errors": "max_length=500"}
}
```

### Error Recovery

```python
# Robust error handling pattern
result = await search_library(input_data)

if not result["success"]:
    error_code = result["error"]
    
    if error_code == "INVALID_QUERY":
        # User input error - show validation message
        print(f"Invalid input: {result['message']}")
    elif error_code == "DATABASE_ERROR":
        # System error - retry or show generic message
        print("Search temporarily unavailable, please try again")
    else:
        # Unknown error
        logger.error(f"Unexpected error: {result}")
```

---

## Best Practices

### 1. Always Check Success Flag

```python
result = await get_audio_metadata({"audioId": audio_id})

if result["success"]:
    # Process successful response
    metadata = result["metadata"]
else:
    # Handle error
    print(f"Error: {result['message']}")
```

### 2. Use Pagination for Large Result Sets

```python
# Good: Reasonable page size
result = await search_library({
    "query": "music",
    "limit": 20
})

# Bad: Requesting too many results
result = await search_library({
    "query": "music",
    "limit": 100  # Use only when necessary
})
```

### 3. Combine Filters for Precision

```python
# More specific = better performance
result = await search_library({
    "query": "rock",
    "filters": {
        "genre": ["Rock"],      # Narrow by genre
        "year": {"min": 1970}   # Narrow by decade
    }
})
```

### 4. Handle Empty Results Gracefully

```python
result = await search_library({"query": "nonexistent"})

if result["success"] and len(result["results"]) == 0:
    print("No results found. Try a different query or remove filters.")
```

### 5. Validate UUIDs Before Calling

```python
import re

def is_valid_uuid(uuid_string):
    pattern = r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'
    return bool(re.match(pattern, uuid_string, re.IGNORECASE))

# Validate before calling
if is_valid_uuid(audio_id):
    result = await get_audio_metadata({"audioId": audio_id})
else:
    print("Invalid audio ID format")
```

---

## Use Cases

### Use Case 1: Display Track Details

```python
async def display_track(audio_id: str):
    """Display complete information for a track"""
    result = await get_audio_metadata({"audioId": audio_id})
    
    if not result["success"]:
        print(f"Track not found: {result['message']}")
        return
    
    meta = result["metadata"]
    print(f"Title: {meta['Product']['Title']}")
    print(f"Artist: {meta['Product']['Artist']}")
    print(f"Album: {meta['Product']['Album']}")
    print(f"Year: {meta['Product']['Year']}")
    print(f"Duration: {meta['Format']['Duration']}s")
    print(f"Stream URL: {result['resources']['audio']}")
```

### Use Case 2: Search by Artist

```python
async def search_artist(artist_name: str):
    """Find all tracks by an artist"""
    result = await search_library({
        "query": artist_name,
        "filters": {
            "artist": artist_name
        },
        "sortBy": "year",
        "sortOrder": "asc",
        "limit": 50
    })
    
    if result["success"]:
        print(f"Found {result['total']} tracks by {artist_name}")
        for track in result["results"]:
            meta = track["metadata"]["Product"]
            print(f"  - {meta['Title']} ({meta['Year']})")
```

### Use Case 3: Build a Music Playlist

```python
async def create_rock_playlist(min_duration=180, max_duration=360):
    """Create a playlist of rock songs within duration range"""
    result = await search_library({
        "query": "rock",
        "filters": {
            "genre": ["Rock", "Classic Rock", "Hard Rock"],
            "duration": {"min": min_duration, "max": max_duration}
        },
        "sortBy": "relevance",
        "limit": 50
    })
    
    if result["success"]:
        playlist = [
            {
                "id": track["audioId"],
                "title": track["metadata"]["Product"]["Title"],
                "artist": track["metadata"]["Product"]["Artist"],
                "stream_url": f"music-library://audio/{track['audioId']}/stream"
            }
            for track in result["results"]
        ]
        return playlist
```

### Use Case 4: Pagination UI

```python
async def paginated_search(query: str, page: int, page_size: int = 20):
    """Implement paginated search for UI"""
    offset = (page - 1) * page_size
    
    result = await search_library({
        "query": query,
        "limit": page_size,
        "offset": offset
    })
    
    return {
        "tracks": result["results"] if result["success"] else [],
        "current_page": page,
        "total_results": result.get("total", 0),
        "has_next_page": result.get("hasMore", False),
        "has_prev_page": page > 1
    }
```

---

## Comparison Table

| Feature | get_audio_metadata | search_library |
|---------|-------------------|----------------|
| **Purpose** | Get single track | Search multiple tracks |
| **Input** | UUID only | Query + filters |
| **Output** | Single metadata | Array of results |
| **Performance** | Very fast (<50ms) | Fast (<200ms) |
| **Caching** | Recommended | Recommended for common queries |
| **Use when** | You have track ID | You need to find tracks |

---

## Integration Examples

### REST API Wrapper

```python
from fastapi import FastAPI, HTTPException

app = FastAPI()

@app.get("/api/tracks/{audio_id}")
async def get_track(audio_id: str):
    """REST endpoint for getting track metadata"""
    result = await get_audio_metadata({"audioId": audio_id})
    
    if not result["success"]:
        raise HTTPException(status_code=404, detail=result["message"])
    
    return result

@app.get("/api/search")
async def search_tracks(
    q: str,
    genre: str = None,
    limit: int = 20,
    offset: int = 0
):
    """REST endpoint for searching tracks"""
    filters = {}
    if genre:
        filters["genre"] = [genre]
    
    result = await search_library({
        "query": q,
        "filters": filters if filters else None,
        "limit": limit,
        "offset": offset
    })
    
    if not result["success"]:
        raise HTTPException(status_code=500, detail=result["message"])
    
    return result
```

---

## Testing

### Unit Tests

```bash
# Run query tool tests
pytest tests/test_query_tools.py -v

# Run specific test
pytest tests/test_query_tools.py::test_get_audio_metadata_success -v

# Run with coverage
pytest tests/test_query_tools.py --cov=src/tools/query_tools
```

### Integration Tests

```python
# Test against real database (requires DB setup)
@pytest.mark.integration
async def test_real_search():
    result = await search_library({
        "query": "test",
        "limit": 5
    })
    assert result["success"] is True
```

---

## Related Documentation

- [process_audio_complete API](./process-audio-complete-api.md) - Audio ingestion tool
- [Database Operations](./database-operations.md) - Database layer documentation
- [API Contract](./api-contract.md) - Complete API specification

---

## Support

For issues or questions:
1. Check error messages for specific guidance
2. Verify input format matches schema
3. Review logs for detailed error context
4. Open an issue with reproducible example

---

**Last Updated:** 2025-10-11  
**Version:** 1.0  
**Status:** Production Ready


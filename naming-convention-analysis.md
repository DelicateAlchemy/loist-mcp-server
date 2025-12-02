# Naming Convention Analysis: camelCase vs snake_case

## Problem Statement

During API migration and MCP refactoring, inconsistent naming conventions (camelCase vs snake_case) have emerged, causing issues with Postman tests and API contracts. This document analyzes the current state and provides recommendations.

## Current State Analysis

### Python Backend (Source of Truth)

**All Pydantic models use snake_case:**

1. **PlayerConfig** (`src/tools/schemas.py:327-339`):
   - `audio_id` (not `audioId`)
   - `waveform_available` (not `waveformAvailable`)
   - `duration_seconds` (not `durationSeconds`)

2. **ProcessAudioOutput** (`src/tools/schemas.py:207-224`):
   - `audio_id` (not `audioId`)
   - `processing_time` (not `processingTime`)

3. **PlayerConfigUrls** (`src/tools/schemas.py:311-316`):
   - `embed`, `waveform`, `artwork`, `waveform_svg` (all snake_case)

4. **PlayerConfigMetadata** (`src/tools/schemas.py:319-324`):
   - `duration_seconds` (not `durationSeconds`)

**Serialization**: Uses `model_dump()` which preserves field names as-is (snake_case).

### API Responses (What Actually Gets Returned)

**`get_embed_url` response** (`src/server.py:1694-1697`):
```python
return {
    "success": True,
    **player_config.model_dump()  # Returns snake_case fields
}
```

**Result**: All responses use snake_case (`audio_id`, `waveform_available`, etc.)

### Postman Collection (Test Expectations)

**Evidence of confusion** (`loist-music-library-local.postman_collection.json:644-656`):
```javascript
pm.test('Process audio result has audio_id', function () {
    // API returns audioId (camelCase), not audio_id
    const hasAudioId = toolResult.hasOwnProperty('audioId') || toolResult.hasOwnProperty('audio_id');
    pm.expect(hasAudioId).to.be.true;
});

// Chain: Store audio_id for subsequent requests (handle both naming conventions)
const audioIdValue = toolResult.audioId || toolResult.audio_id;
```

**Key observation**: Postman tests handle BOTH conventions, suggesting:
1. Previous API versions may have used camelCase
2. Current API uses snake_case
3. Tests are defensive to handle both

### Documentation Inconsistency

**Frontend API Integration** (`docs/frontend-api-integration.md:585`):
- **Request** shows: `"audioId": "..."` (camelCase)
- **Response** shows: `"audio_id": "..."` (snake_case)

This mismatch suggests documentation may be aspirational or outdated.

## Root Cause Analysis

### Why This Happened

1. **Python convention**: Python/Pydantic naturally uses snake_case
2. **JavaScript convention**: Frontend/TypeScript typically uses camelCase
3. **No serialization layer**: No conversion between conventions
4. **Migration confusion**: During API refactoring, naming wasn't standardized

### The Specific Issue with `get_embed_url`

When `get_embed_url` was moved into `PlayerConfig`:
- **Before**: May have returned camelCase (or mixed)
- **After**: Returns snake_case (via Pydantic `model_dump()`)
- **Postman tests**: Expect camelCase but handle both
- **Result**: Tests pass but with defensive code, masking the inconsistency

## Evidence from Codebase

### Consistent snake_case Usage

```python
# src/server.py:1674-1691
player_config = PlayerConfig(
    audio_id=audio_id,              # snake_case
    waveform_available=waveform_available,  # snake_case
    urls=PlayerConfigUrls(
        embed=embed_url,            # snake_case
        waveform_svg=waveform_svg_url  # snake_case
    ),
    metadata=PlayerConfigMetadata(
        duration_seconds=metadata.get("duration", 0)  # snake_case
    )
)
```

### Postman Test Handling Both

```javascript
// loist-music-library-local.postman_collection.json:1401
pm.expect(toolResult).to.have.property('audio_id');  // Expects snake_case

// But also handles camelCase:
const audioIdValue = toolResult.audioId || toolResult.audio_id;
```

## Recommendations

### Option 1: Standardize on snake_case (Recommended)

**Rationale**:
- Python backend is the source of truth
- JSON-RPC/MCP doesn't mandate camelCase
- Less code changes needed
- Consistent with Python ecosystem

**Actions**:
1. ✅ Keep all Python models as snake_case (already done)
2. ✅ Update Postman tests to expect only snake_case
3. ✅ Update documentation to show snake_case consistently
4. ✅ Remove defensive camelCase handling from Postman

**Files to update**:
- `loist-music-library-local.postman_collection.json` - Remove camelCase fallbacks
- `docs/frontend-api-integration.md` - Update request examples to snake_case
- Any frontend TypeScript types (if they exist)

### Option 2: Standardize on camelCase

**Rationale**:
- JavaScript/TypeScript convention
- Better frontend integration
- Common in REST APIs

**Actions**:
1. Add Pydantic field aliases to convert snake_case → camelCase
2. Use `model_dump(by_alias=True)` in all responses
3. Update all Python models with aliases
4. Update Postman tests to expect only camelCase

**Implementation example**:
```python
class PlayerConfig(BaseModel):
    audio_id: str = Field(alias="audioId")
    waveform_available: bool = Field(alias="waveformAvailable")
    
    model_config = ConfigDict(populate_by_name=True)  # Allow both in input

# Then use:
return player_config.model_dump(by_alias=True)  # Returns camelCase
```

**Files to update**:
- `src/tools/schemas.py` - Add aliases to all models
- `src/server.py` - Use `by_alias=True` in all `model_dump()` calls
- `src/tools/process_audio.py` - Same
- `src/tools/query_tools.py` - Same
- All other tool response serialization

### Option 3: Hybrid (Accept Both)

**Rationale**:
- Maximum compatibility
- No breaking changes

**Actions**:
1. Keep snake_case as primary
2. Add camelCase aliases for backward compatibility
3. Update documentation to show both
4. Keep Postman defensive handling

**Implementation**: Same as Option 2 but accept both in input AND output.

## Decision Matrix

| Factor | snake_case (Option 1) | camelCase (Option 2) | Hybrid (Option 3) |
|--------|----------------------|---------------------|-------------------|
| **Code changes** | Minimal (docs/tests) | Moderate (all models) | Moderate (all models) |
| **Breaking changes** | Yes (if frontend expects camelCase) | Yes (if tests expect snake_case) | No |
| **Python convention** | ✅ Native | ❌ Requires aliases | ⚠️ Requires aliases |
| **JS convention** | ❌ Requires conversion | ✅ Native | ✅ Native |
| **Maintenance** | ✅ Simple | ⚠️ Aliases to maintain | ❌ Complex |
| **Clarity** | ✅ Clear | ✅ Clear | ❌ Ambiguous |

## Recommended Path Forward

**Recommendation: Option 1 (snake_case)**

**Reasoning**:
1. Python backend is source of truth - snake_case is natural
2. JSON-RPC/MCP doesn't enforce naming conventions
3. Frontend can easily convert if needed (common pattern)
4. Less code complexity (no aliases to maintain)
5. Consistent with Python ecosystem

**Implementation Steps**:
1. Audit all API responses to confirm snake_case
2. Update Postman collection to expect only snake_case
3. Update documentation to show snake_case consistently
4. Add a note in docs about frontend conversion if needed
5. Remove all camelCase fallback handling

## Files Requiring Updates (Option 1)

1. **Postman Collection**:
   - Remove `toolResult.audioId || toolResult.audio_id` patterns
   - Update all tests to expect `audio_id` only
   - Update comments that say "API returns audioId"

2. **Documentation**:
   - `docs/frontend-api-integration.md` - Update request examples
   - `template-system-analysis.md` - Already uses snake_case ✅
   - Any other API docs

3. **Frontend (if exists)**:
   - TypeScript types/interfaces
   - API client code

## Research Findings (January 2025)

### JSON-RPC 2.0 Conventions
- **No naming mandate**: JSON-RPC 2.0 only specifies *which* fields must exist (`jsonrpc`, `id`, `method`, `params`, `result`, `error`), not how application-level fields are cased
- **Stack-agnostic**: JSON-RPC treats JSON as an abstract data format and does not define naming conventions for keys
- **Practice**: Python servers often use snake_case; Java/JS-heavy stacks often use camelCase
- **Conclusion**: Choosing snake_case for `audio_id`, `waveform_available`, etc. is fully compliant

### MCP / FastMCP Ecosystem Patterns
- **Protocol-level keys**: Fixed by spec (tool envelope fields)
- **Tool-specific payloads**: Left to server authors
- **Python-based MCP servers**: Typically use snake_case (reflecting Pydantic/PEP 8 norms)
- **JS/TS-based implementations**: Skew camelCase
- **FastMCP**: Does not impose naming conventions; passes through whatever models serialize
- **Conclusion**: No MCP-wide rule requiring camelCase in tool responses

### Pydantic Behavior
- **Default**: Uses Python attribute name as JSON key (snake_case → snake_case)
- **Aliases**: Supported via `Field(alias="audioId")` and `ConfigDict(populate_by_name=True)`
- **Serialization**: `model_dump(by_alias=True)` emits camelCase while keeping internal snake_case
- **Performance**: Aliases add negligible overhead; main cost is cognitive/maintenance complexity

### Best Practice for Python ↔ JS Interop
- **Idiomatic approach**: Expose snake_case over the wire, let JS/TS clients map to camelCase at boundary
- **If camelCase required**: Use Pydantic aliases + `by_alias=True` (e.g., for public TS SDK)
- **Migration**: Supporting both in inputs is reasonable during migration; supporting both in outputs long-term creates ambiguity

### Decision Confirmation
✅ **Option 1 (snake_case) is confirmed as the correct choice**:
- Aligns with Python/Pydantic conventions
- No spec pressure to use camelCase
- Least risky and clearest decision
- Avoids sprinkling aliases everywhere
- Keeps protocol layer Python-native

---

**Analysis Date**: January 2025
**Research Date**: January 2025
**Status**: ✅ Decision confirmed - Implementing Option 1 (snake_case)


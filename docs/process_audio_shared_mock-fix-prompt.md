# Fix process_audio_shared Mock Target in A2A Tests

## Copy this entire section for a new LLM coding agent:

---

## Problem Description

A2A message streaming tests are failing with:
```
AttributeError: <module 'src.a2a_server.handler' from '/app/src/a2a_server/handler.py'> does not have the attribute 'process_audio_shared'
```

The test is trying to mock `src.a2a_server.handler.process_audio_shared`, but this function doesn't exist in that location.

## Root Cause Analysis

**Where the function actually is:**
- `process_audio_shared` is defined in `src/business/audio_processor.py`
- It's exported from `src/business/__init__.py`
- It's imported locally inside handler methods, not at module level

**Where the test is trying to mock:**
- Test is using: `patch('src.a2a_server.handler.process_audio_shared', ...)`
- But `src.a2a_server.handler.process_audio_shared` doesn't exist

**Handler import pattern:**
```python
# Inside handler methods (not at module level)
from src.business import (
    process_audio_shared,
    AudioProcessingRequest,
    SharedAudioProcessingError,
)
```

## Current Test Code (Broken)

**File:** `tests/a2a/test_message_stream.py`

```python
@pytest.fixture
async def a2a_app(mock_task_store, mock_audio_processing_result):
    """Create A2A FastAPI app with mocked dependencies."""
    if not A2A_AVAILABLE:
        pytest.skip("A2A SDK not available")

    # Create agent card
    agent_card = create_agent_card()

    # Create handler with mock task store
    handler = LoistRequestHandler(task_store=mock_task_store)

    # Create A2A app
    a2a_app = A2AFastAPIApplication(
        agent_card=agent_card,
        http_handler=handler
    )

    # Build FastAPI app
    app = a2a_app.build()
    app.state.mock_task_store = mock_task_store

    # Mock the audio processing  <-- THIS IS THE BROKEN LINE
    with patch('src.a2a_server.handler.process_audio_shared', return_value=mock_audio_processing_result):
        yield app
```

## What the Test Should Mock Instead

**Option 1: Mock at the business module level**
```python
with patch('src.business.process_audio_shared', return_value=mock_audio_processing_result):
```

**Option 2: Mock at the import location**
```python
with patch('src.a2a_server.handler.LoistRequestHandler.on_message_send_stream') as mock_method:
    # Configure the mock to call your mock_audio_processing_result
    mock_instance = AsyncMock()
    mock_instance.on_message_send_stream.return_value = mock_stream
    mock_method.return_value = mock_instance
```

**Option 3: Mock the entire business import**
```python
with patch('src.business') as mock_business:
    mock_business.process_audio_shared.return_value = mock_audio_processing_result
    mock_business.AudioProcessingRequest = AudioProcessingRequest  # Keep real class
    mock_business.SharedAudioProcessingError = SharedAudioProcessingError  # Keep real class
```

## Test Context

- The test is testing the `on_message_send_stream` method of `LoistRequestHandler`
- This method calls `process_audio_shared` internally
- The test needs to control what `process_audio_shared` returns
- The mock should return `mock_audio_processing_result` (which is an `AudioProcessingResult`)

## Related Files

1. **Handler:** `src/a2a_server/handler.py` (lines ~165-179, ~447-458)
2. **Business logic:** `src/business/audio_processor.py` (line 253: `async def process_audio_shared(...)`)
3. **Business exports:** `src/business/__init__.py` (exports `process_audio_shared`)
4. **Test fixture:** `tests/a2a/test_message_stream.py` (line 129: broken patch)

## Verification Steps

After fixing the mock target, run:
```bash
docker-compose exec mcp-server python -m pytest tests/a2a/test_message_stream.py -v
```

Expected result:
- Tests should run without the AttributeError
- `process_audio_shared` should be properly mocked
- Tests should pass (or fail on other issues, not import/mocking)

## Key Points for the Fix

1. **Don't mock at the handler module level** - `process_audio_shared` is not there
2. **Mock at the business module level** - that's where the function lives
3. **Preserve other imports** - `AudioProcessingRequest` and `SharedAudioProcessingError` are also imported from business
4. **Use the correct mock target** - `src.business.process_audio_shared` is the right path

---

**End of prompt**





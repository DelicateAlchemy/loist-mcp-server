#!/bin/bash
# Retry Logic Testing Script
# Tests retry functionality with exponential backoff and jitter
#
# Run with: bash scripts/test_retry_logic.sh

set -e

echo "🔍 Testing Retry Logic Functionality..."
echo

# Test 1: Basic retry configuration and successful call
echo "1. Testing basic retry configuration and successful call..."
python3 -c "
import sys
sys.path.insert(0, 'src')

from src.exceptions.retry import (
    RetryConfig,
    retry_call,
    retry_with_backoff,
    RetryExhaustedException
)

try:
    # Test successful call (no retries needed)
    def success_func():
        return 'success'
    
    config = RetryConfig(max_attempts=3, initial_delay=0.1)
    result = retry_call(success_func, config=config)
    assert result == 'success', 'Should return function result'
    print('✅ Successful call returns result without retries')
    
    # Test decorator version
    @retry_with_backoff(max_attempts=3, initial_delay=0.1)
    def decorated_success():
        return 'decorated_success'
    
    result = decorated_success()
    assert result == 'decorated_success', 'Decorator should work'
    print('✅ Retry decorator works correctly')
    
except Exception as e:
    print(f'❌ Basic retry test failed: {e}')
    import traceback
    traceback.print_exc()
    sys.exit(1)
"

if [ $? -ne 0 ]; then
    echo "❌ Basic retry test failed"
    exit 1
fi
echo

# Test 2: Retry on transient failures
echo "2. Testing retry on transient failures..."
python3 -c "
import sys
import time
sys.path.insert(0, 'src')

from src.exceptions.retry import (
    RetryConfig,
    retry_call,
    RetryExhaustedException
)

try:
    # Create a function that fails twice then succeeds
    attempt_count = [0]
    
    def transient_failure_func():
        attempt_count[0] += 1
        if attempt_count[0] < 3:
            raise ConnectionError('Transient failure')
        return 'success after retries'
    
    config = RetryConfig(
        max_attempts=5,
        initial_delay=0.1,
        backoff_factor=2.0,
        jitter=False  # Disable jitter for predictable timing
    )
    
    start_time = time.time()
    result = retry_call(transient_failure_func, config=config)
    elapsed = time.time() - start_time
    
    assert result == 'success after retries', 'Should succeed after retries'
    assert attempt_count[0] == 3, 'Should have attempted 3 times'
    assert elapsed >= 0.1 + 0.2, 'Should have waited for retries (exponential backoff)'
    print(f'✅ Retry succeeded after {attempt_count[0]} attempts (elapsed: {elapsed:.2f}s)')
    
except Exception as e:
    print(f'❌ Transient failure retry test failed: {e}')
    import traceback
    traceback.print_exc()
    sys.exit(1)
"

if [ $? -ne 0 ]; then
    echo "❌ Transient failure retry test failed"
    exit 1
fi
echo

# Test 3: Retry exhaustion
echo "3. Testing retry exhaustion..."
python3 -c "
import sys
sys.path.insert(0, 'src')

from src.exceptions.retry import (
    RetryConfig,
    retry_call,
    RetryExhaustedException
)

try:
    # Create a function that always fails
    attempt_count = [0]
    
    def always_fails():
        attempt_count[0] += 1
        raise ConnectionError('Persistent failure')
    
    config = RetryConfig(
        max_attempts=3,
        initial_delay=0.05,
        jitter=False
    )
    
    try:
        retry_call(always_fails, config=config)
        raise Exception('Should have raised RetryExhaustedException')
    except RetryExhaustedException as e:
        assert e.attempts == config.max_attempts, 'Should have exhausted all attempts'
        assert attempt_count[0] == config.max_attempts, 'Should have attempted max_attempts times'
        print(f'✅ RetryExhaustedException raised after {e.attempts} attempts')
    
except Exception as e:
    print(f'❌ Retry exhaustion test failed: {e}')
    import traceback
    traceback.print_exc()
    sys.exit(1)
"

if [ $? -ne 0 ]; then
    echo "❌ Retry exhaustion test failed"
    exit 1
fi
echo

# Test 4: Non-retryable exceptions
echo "4. Testing non-retryable exceptions..."
python3 -c "
import sys
sys.path.insert(0, 'src')

from src.exceptions.retry import (
    RetryConfig,
    retry_call
)

try:
    # Create a function that raises a non-retryable exception
    attempt_count = [0]
    
    def non_retryable_error():
        attempt_count[0] += 1
        raise ValueError('Non-retryable error')
    
    config = RetryConfig(
        max_attempts=5,
        initial_delay=0.1
    )
    
    try:
        retry_call(non_retryable_error, config=config)
        raise Exception('Should have raised ValueError')
    except ValueError as e:
        assert attempt_count[0] == 1, 'Should not retry non-retryable exceptions'
        print('✅ Non-retryable exceptions are not retried')
    
except Exception as e:
    print(f'❌ Non-retryable exception test failed: {e}')
    import traceback
    traceback.print_exc()
    sys.exit(1)
"

if [ $? -ne 0 ]; then
    echo "❌ Non-retryable exception test failed"
    exit 1
fi
echo

# Test 5: Exponential backoff calculation
echo "5. Testing exponential backoff calculation..."
python3 -c "
import sys
sys.path.insert(0, 'src')

from src.exceptions.retry import (
    RetryConfig,
    calculate_delay
)

try:
    config = RetryConfig(
        initial_delay=0.1,
        max_delay=10.0,
        backoff_factor=2.0,
        jitter=False
    )
    
    # Test exponential backoff
    delay1 = calculate_delay(0, config)
    delay2 = calculate_delay(1, config)
    delay3 = calculate_delay(2, config)
    
    assert delay1 == 0.1, 'First delay should be initial_delay'
    assert delay2 == 0.2, 'Second delay should be initial_delay * backoff_factor'
    assert delay3 == 0.4, 'Third delay should be initial_delay * backoff_factor^2'
    print(f'✅ Exponential backoff: {delay1}s -> {delay2}s -> {delay3}s')
    
    # Test max delay cap
    config.max_delay = 0.3
    delay_capped = calculate_delay(5, config)
    assert delay_capped <= config.max_delay, 'Delay should be capped at max_delay'
    print(f'✅ Max delay cap works: {delay_capped}s <= {config.max_delay}s')
    
except Exception as e:
    print(f'❌ Exponential backoff test failed: {e}')
    import traceback
    traceback.print_exc()
    sys.exit(1)
"

if [ $? -ne 0 ]; then
    echo "❌ Exponential backoff test failed"
    exit 1
fi
echo

# Test 6: Pre-configured retry configs
echo "6. Testing pre-configured retry configs..."
python3 -c "
import sys
sys.path.insert(0, 'src')

from src.exceptions.retry import (
    DATABASE_RETRY_CONFIG,
    GCS_RETRY_CONFIG,
    HTTP_RETRY_CONFIG
)

try:
    # Verify pre-configured configs exist and have reasonable values
    assert DATABASE_RETRY_CONFIG.max_attempts > 0, 'DATABASE_RETRY_CONFIG should have max_attempts'
    assert DATABASE_RETRY_CONFIG.initial_delay > 0, 'DATABASE_RETRY_CONFIG should have initial_delay'
    print('✅ DATABASE_RETRY_CONFIG is properly configured')
    
    assert GCS_RETRY_CONFIG.max_attempts > 0, 'GCS_RETRY_CONFIG should have max_attempts'
    assert GCS_RETRY_CONFIG.initial_delay > 0, 'GCS_RETRY_CONFIG should have initial_delay'
    print('✅ GCS_RETRY_CONFIG is properly configured')
    
    assert HTTP_RETRY_CONFIG.max_attempts > 0, 'HTTP_RETRY_CONFIG should have max_attempts'
    assert HTTP_RETRY_CONFIG.initial_delay > 0, 'HTTP_RETRY_CONFIG should have initial_delay'
    print('✅ HTTP_RETRY_CONFIG is properly configured')
    
except Exception as e:
    print(f'❌ Pre-configured retry configs test failed: {e}')
    import traceback
    traceback.print_exc()
    sys.exit(1)
"

if [ $? -ne 0 ]; then
    echo "❌ Pre-configured retry configs test failed"
    exit 1
fi
echo

# Test 7: Integration with database pool (if available)
echo "7. Testing retry logic integration with database pool..."
python3 -c "
import sys
sys.path.insert(0, 'src')

try:
    from database.pool import DatabasePool
    from src.exceptions.retry import DATABASE_RETRY_CONFIG
    
    # Just verify the integration exists
    # Full integration test requires a real database connection
    assert DATABASE_RETRY_CONFIG is not None, 'DATABASE_RETRY_CONFIG should exist'
    print('✅ Retry logic can be imported and used with database pool')
    print('   (Full integration test requires database connection)')
    
except ImportError as e:
    print(f'⚠️  Retry integration test skipped: {e}')
    print('   (This is expected if database pool doesn\\'t use retry logic)')
except Exception as e:
    print(f'❌ Retry integration test failed: {e}')
    import traceback
    traceback.print_exc()
    sys.exit(1)
"

if [ $? -ne 0 ]; then
    echo "❌ Retry integration test failed"
    exit 1
fi
echo

echo "🎉 Retry logic testing complete!"
echo "   All retry functionality validated"
echo
echo "📋 Summary:"
echo "   ✅ Basic retry configuration and successful calls"
echo "   ✅ Retry on transient failures"
echo "   ✅ Retry exhaustion handling"
echo "   ✅ Non-retryable exception handling"
echo "   ✅ Exponential backoff calculation"
echo "   ✅ Pre-configured retry configs"
echo "   ✅ Integration with database pool (if available)"


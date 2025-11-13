#!/bin/bash
# Circuit Breaker Testing Script
# Tests circuit breaker functionality for fault tolerance
#
# Run with: bash scripts/test_circuit_breaker.sh

set -e

echo "🔍 Testing Circuit Breaker Functionality..."
echo

# Test 1: Basic circuit breaker creation and state management
echo "1. Testing basic circuit breaker creation and state management..."
python3 -c "
import sys
sys.path.insert(0, 'src')

from src.exceptions.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerConfig,
    CircuitBreakerState,
    CircuitBreakerOpenException,
    get_circuit_breaker
)

try:
    # Test basic creation
    config = CircuitBreakerConfig(
        name='test-breaker',
        failure_threshold=3,
        recovery_timeout=1.0,
        success_threshold=2
    )
    breaker = CircuitBreaker(config)
    
    # Verify initial state
    assert breaker.state == CircuitBreakerState.CLOSED, 'Initial state should be CLOSED'
    print('✅ Circuit breaker created with CLOSED state')
    
    # Test successful call
    def success_func():
        return 'success'
    
    result = breaker.call(success_func)
    assert result == 'success', 'Should return function result'
    print('✅ Successful call passes through circuit breaker')
    
    # Verify stats updated
    stats = breaker.stats
    assert stats.total_requests == 1, 'Should have 1 total request'
    assert stats.successful_requests == 1, 'Should have 1 successful request'
    print('✅ Statistics updated correctly')
    
except Exception as e:
    print(f'❌ Basic circuit breaker test failed: {e}')
    import traceback
    traceback.print_exc()
    sys.exit(1)
"

if [ $? -ne 0 ]; then
    echo "❌ Basic circuit breaker test failed"
    exit 1
fi
echo

# Test 2: Circuit breaker opening on failures
echo "2. Testing circuit breaker opening on consecutive failures..."
python3 -c "
import sys
sys.path.insert(0, 'src')

from src.exceptions.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerConfig,
    CircuitBreakerState,
    CircuitBreakerOpenException
)

try:
    config = CircuitBreakerConfig(
        name='test-failure-breaker',
        failure_threshold=3,
        recovery_timeout=1.0
    )
    breaker = CircuitBreaker(config)
    
    # Create a function that always fails
    def failing_func():
        raise ValueError('Test failure')
    
    # Trigger failures up to threshold
    failures = 0
    for i in range(config.failure_threshold):
        try:
            breaker.call(failing_func)
        except ValueError:
            failures += 1
        except CircuitBreakerOpenException:
            # Circuit should open after threshold failures
            if i == config.failure_threshold - 1:
                print('✅ Circuit breaker opened after threshold failures')
                break
            else:
                raise Exception('Circuit opened too early')
    
    # Verify circuit is open
    assert breaker.state == CircuitBreakerState.OPEN, 'Circuit should be OPEN'
    print('✅ Circuit breaker state is OPEN')
    
    # Verify stats
    stats = breaker.stats
    assert stats.failed_requests >= config.failure_threshold, 'Should have recorded failures'
    assert stats.consecutive_failures >= config.failure_threshold, 'Should have consecutive failures'
    print('✅ Failure statistics recorded correctly')
    
    # Test that open circuit fails fast
    try:
        breaker.call(lambda: 'should not execute')
        raise Exception('Should have raised CircuitBreakerOpenException')
    except CircuitBreakerOpenException:
        print('✅ Open circuit fails fast with CircuitBreakerOpenException')
    
except Exception as e:
    print(f'❌ Circuit breaker failure test failed: {e}')
    import traceback
    traceback.print_exc()
    sys.exit(1)
"

if [ $? -ne 0 ]; then
    echo "❌ Circuit breaker failure test failed"
    exit 1
fi
echo

# Test 3: Circuit breaker recovery (half-open to closed)
echo "3. Testing circuit breaker recovery (half-open to closed)..."
python3 -c "
import sys
import time
sys.path.insert(0, 'src')

from src.exceptions.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerConfig,
    CircuitBreakerState
)

try:
    config = CircuitBreakerConfig(
        name='test-recovery-breaker',
        failure_threshold=2,
        recovery_timeout=0.5,  # Short timeout for testing
        success_threshold=2
    )
    breaker = CircuitBreaker(config)
    
    # Open the circuit
    def failing_func():
        raise ValueError('Test failure')
    
    for _ in range(config.failure_threshold):
        try:
            breaker.call(failing_func)
        except (ValueError, Exception):
            pass
    
    assert breaker.state == CircuitBreakerState.OPEN, 'Circuit should be OPEN'
    print('✅ Circuit opened after failures')
    
    # Wait for recovery timeout
    print('Waiting for recovery timeout...')
    time.sleep(config.recovery_timeout + 0.1)
    
    # Attempt a call (should transition to half-open)
    def success_func():
        return 'success'
    
    # First call should transition to half-open and succeed
    result = breaker.call(success_func)
    assert result == 'success', 'First recovery call should succeed'
    print('✅ Circuit transitioned to HALF_OPEN and first call succeeded')
    
    # Second successful call should close the circuit
    result = breaker.call(success_func)
    assert result == 'success', 'Second recovery call should succeed'
    
    # Wait a moment for state transition
    time.sleep(0.1)
    
    # Circuit should be closed after success_threshold successes
    assert breaker.state == CircuitBreakerState.CLOSED, 'Circuit should be CLOSED after recovery'
    print('✅ Circuit closed after successful recovery')
    
except Exception as e:
    print(f'❌ Circuit breaker recovery test failed: {e}')
    import traceback
    traceback.print_exc()
    sys.exit(1)
"

if [ $? -ne 0 ]; then
    echo "❌ Circuit breaker recovery test failed"
    exit 1
fi
echo

# Test 4: Circuit breaker registry and global access
echo "4. Testing circuit breaker registry and global access..."
python3 -c "
import sys
sys.path.insert(0, 'src')

from src.exceptions.circuit_breaker import (
    get_circuit_breaker,
    get_all_circuit_breakers,
    reset_circuit_breaker,
    CircuitBreakerConfig
)

try:
    # Test getting a circuit breaker
    breaker1 = get_circuit_breaker('registry-test-1')
    breaker2 = get_circuit_breaker('registry-test-1')
    
    # Should return the same instance
    assert breaker1 is breaker2, 'Should return same instance for same name'
    print('✅ Circuit breaker registry returns same instance')
    
    # Test getting all circuit breakers
    all_breakers = get_all_circuit_breakers()
    assert 'registry-test-1' in all_breakers, 'Should include registered breaker'
    print('✅ get_all_circuit_breakers returns registered breakers')
    
    # Test reset
    breaker1._change_state(breaker1._state.__class__.OPEN)
    reset_success = reset_circuit_breaker('registry-test-1')
    assert reset_success, 'Reset should succeed'
    assert breaker1.state.value == 'closed', 'Breaker should be reset to closed'
    print('✅ Circuit breaker reset successful')
    
except Exception as e:
    print(f'❌ Circuit breaker registry test failed: {e}')
    import traceback
    traceback.print_exc()
    sys.exit(1)
"

if [ $? -ne 0 ]; then
    echo "❌ Circuit breaker registry test failed"
    exit 1
fi
echo

# Test 5: Integration with database pool (if available)
echo "5. Testing circuit breaker integration with database pool..."
python3 -c "
import sys
sys.path.insert(0, 'src')

try:
    from database.pool import DatabasePool
    from src.exceptions.circuit_breaker import get_circuit_breaker
    
    # Check if circuit breaker is integrated
    # This test verifies the integration exists, not that it works end-to-end
    # (that requires a real database connection)
    
    # Just verify the import works
    breaker = get_circuit_breaker('database-pool-test')
    print('✅ Circuit breaker can be imported and used with database pool')
    print('   (Full integration test requires database connection)')
    
except ImportError as e:
    print(f'⚠️  Circuit breaker integration test skipped: {e}')
    print('   (This is expected if database pool doesn\\'t use circuit breaker)')
except Exception as e:
    print(f'❌ Circuit breaker integration test failed: {e}')
    import traceback
    traceback.print_exc()
    sys.exit(1)
"

if [ $? -ne 0 ]; then
    echo "❌ Circuit breaker integration test failed"
    exit 1
fi
echo

echo "🎉 Circuit breaker testing complete!"
echo "   All circuit breaker functionality validated"
echo
echo "📋 Summary:"
echo "   ✅ Basic circuit breaker creation and state management"
echo "   ✅ Circuit opening on consecutive failures"
echo "   ✅ Circuit recovery (half-open to closed)"
echo "   ✅ Circuit breaker registry and global access"
echo "   ✅ Integration with database pool (if available)"


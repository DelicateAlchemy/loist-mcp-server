#!/bin/bash
# Waveform Generation Validation Script
# Validates that waveform generation works correctly
#
# Run with: bash scripts/validate_waveform_generation.sh

set -e

echo "🔍 Validating waveform generation..."
echo

# Check FFmpeg is installed
echo "1. Checking FFmpeg installation..."
if ! command -v ffmpeg &> /dev/null; then
    echo "❌ FFmpeg not found"
    echo "   Please install FFmpeg: apk add ffmpeg (Alpine) or apt install ffmpeg (Ubuntu)"
    exit 1
fi

FFMPEG_VERSION=$(ffmpeg -version | head -1)
echo "✅ FFmpeg found: $FFMPEG_VERSION"
echo

# Create test audio file if it doesn't exist
TEST_AUDIO="/tmp/test_audio.wav"
if [ ! -f "$TEST_AUDIO" ]; then
    echo "2. Creating test audio file..."
    # Generate a simple test tone using FFmpeg
    ffmpeg -f lavfi -i "sine=frequency=440:duration=3" -acodec pcm_s16le -ar 44100 "$TEST_AUDIO" -y &> /dev/null
    if [ $? -ne 0 ]; then
        echo "❌ Failed to create test audio file"
        exit 1
    fi
    echo "✅ Created test audio file: $TEST_AUDIO"
else
    echo "2. Using existing test audio file: $TEST_AUDIO"
fi
echo

# Test waveform generation
echo "3. Testing waveform generation..."
OUTPUT_SVG="/tmp/test_waveform.svg"

# Use Python to test the waveform generation
python3 -c "
import sys
sys.path.insert(0, 'src')

from waveform.generator import generate_waveform_svg
from pathlib import Path
import time

try:
    start_time = time.time()
    result = generate_waveform_svg(
        audio_path=Path('$TEST_AUDIO'),
        output_path=Path('$OUTPUT_SVG'),
        width=2000,
        height=200
    )
    end_time = time.time()
    
    print(f'✅ Waveform generation successful')
    print(f'   Processing time: {result[\"processing_time_seconds\"]:.2f}s')
    print(f'   File size: {result[\"file_size_bytes\"]} bytes')
    print(f'   Sample count: {result[\"sample_count\"]}')
    print(f'   Output: $OUTPUT_SVG')
    
    # Validate SVG file
    if not Path('$OUTPUT_SVG').exists():
        print('❌ SVG file was not created')
        sys.exit(1)
        
    # Check SVG content
    with open('$OUTPUT_SVG', 'r') as f:
        svg_content = f.read()
        
    if '<svg' not in svg_content:
        print('❌ SVG file does not contain SVG element')
        sys.exit(1)
        
    if 'viewBox=' not in svg_content:
        print('❌ SVG file does not have viewBox attribute')
        sys.exit(1)
        
    if '<path' not in svg_content:
        print('❌ SVG file does not contain path element')
        sys.exit(1)
        
    print('✅ SVG file validation passed')
    
except Exception as e:
    print(f'❌ Waveform generation failed: {e}')
    import traceback
    traceback.print_exc()
    sys.exit(1)
"

if [ $? -ne 0 ]; then
    echo "❌ Waveform generation test failed"
    exit 1
fi

echo
echo "🎉 Waveform generation validation passed!"
echo "   Test audio: $TEST_AUDIO"
echo "   Generated SVG: $OUTPUT_SVG"

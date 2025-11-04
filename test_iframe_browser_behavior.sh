#!/bin/bash

# Test script to demonstrate iframe embedding behavior across different scenarios
# This script tests the hypothesis that file:// protocol blocks iframe loading

echo "=== Iframe Embedding Behavior Test ==="
echo ""

# Test 1: Direct access to embed endpoint
echo "1. Testing direct access to embed endpoint:"
echo "   URL: https://857daa7fb123.ngrok-free.app/embed/324a6ab1-1b56-4ad5-adde-a7349df56472"
curl -s -o /dev/null -w "   HTTP Status: %{http_code}\n" https://857daa7fb123.ngrok-free.app/embed/324a6ab1-1b56-4ad5-adde-a7349df56472

# Test 2: Check iframe-related headers
echo ""
echo "2. Checking iframe security headers:"
curl -s -I https://857daa7fb123.ngrok-free.app/embed/324a6ab1-1b56-4ad5-adde-a7349df56472 | grep -E "(x-frame-options|content-security-policy)" | sed 's/^/   /'

# Test 3: Test local web server approach
echo ""
echo "3. Testing local web server approach (localhost:8080):"
echo "   URL: http://localhost:8080/embed/324a6ab1-1b56-4ad5-adde-a7349df56472"
curl -s -o /dev/null -w "   HTTP Status: %{http_code}\n" http://localhost:8080/embed/324a6ab1-1b56-4ad5-adde-a7349df56472

echo ""
echo "4. Local web server iframe headers:"
curl -s -I http://localhost:8080/embed/324a6ab1-1b56-4ad5-adde-a7349df56472 | grep -E "(x-frame-options|content-security-policy)" | sed 's/^/   /'

echo ""
echo "=== Analysis ==="
echo ""
echo "The issue is that browsers block iframe loading from file:// protocol for security reasons."
echo "This is a Same-Origin Policy restriction that cannot be bypassed with CORS headers."
echo ""
echo "Solutions:"
echo "1. Use a local web server instead of file:// protocol"
echo "2. Host test files on localhost and load iframes from there"
echo "3. Use browser flags to disable web security (not recommended for production)"
echo ""
echo "To test iframe embedding properly:"
echo "1. Start a local web server (python -m http.server 8000)"
echo "2. Place test_iframe.html in the web root"
echo "3. Access via http://localhost:8000/test_iframe.html"
echo "4. Iframes should load successfully"

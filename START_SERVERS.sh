#!/bin/bash

# Authentication System - Local Test Script

echo "=========================================="
echo "LLM App Authentication System"
echo "Starting local servers..."
echo "=========================================="

# Check if servers are already running
if lsof -Pi :8000 -sTCP:LISTEN -t >/dev/null 2>&1 ; then
    echo "⚠ Port 8000 is already in use"
    echo "  Stop existing server: pkill -f 'uvicorn api.main:app'"
else
    echo "Starting API server on port 8000..."
    cd "$(dirname "$0")"
    PYTHONPATH=. python3 -m uvicorn api.main:app --port 8000 --reload > /tmp/api_server.log 2>&1 &
    API_PID=$!
    echo "  API Server PID: $API_PID"
fi

if lsof -Pi :3000 -sTCP:LISTEN -t >/dev/null 2>&1 ; then
    echo "⚠ Port 3000 is already in use"
    echo "  Stop existing server: pkill -f 'http.server 3000'"
else
    echo "Starting Frontend server on port 3000..."
    cd frontend
    python3 -m http.server 3000 > /tmp/frontend_server.log 2>&1 &
    FRONTEND_PID=$!
    cd ..
    echo "  Frontend Server PID: $FRONTEND_PID"
fi

# Wait for servers to start
echo ""
echo "Waiting for servers to start..."
sleep 3

# Check if servers are running
API_STATUS=$(curl -s http://localhost:8000/health 2>/dev/null | grep -o "healthy" || echo "not running")
FRONTEND_STATUS=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:3000/ 2>/dev/null)

echo ""
echo "=========================================="
echo "Server Status"
echo "=========================================="

if [ "$API_STATUS" = "healthy" ]; then
    echo "✓ API Server: Running"
    echo "  URL: http://localhost:8000"
    echo "  Health: http://localhost:8000/health"
    echo "  API Docs: http://localhost:8000/docs"
    echo "  ReDoc: http://localhost:8000/redoc"
else
    echo "✗ API Server: Not Running"
    echo "  Check logs: tail -f /tmp/api_server.log"
fi

if [ "$FRONTEND_STATUS" = "200" ]; then
    echo ""
    echo "✓ Frontend Server: Running"
    echo "  URL: http://localhost:3000"
    echo "  Login: http://localhost:3000/login.html"
    echo "  Dashboard: http://localhost:3000/dashboard.html"
else
    echo ""
    echo "✗ Frontend Server: Not Running"
    echo "  Check logs: tail -f /tmp/frontend_server.log"
fi

echo ""
echo "=========================================="
echo "Quick Test"
echo "=========================================="
echo ""
echo "1. Test User Registration:"
echo "   curl -X POST http://localhost:8000/auth/register \\"
echo "     -H 'Content-Type: application/json' \\"
echo "     -d '{\"email\":\"test@example.com\",\"password\":\"Test123\",\"tenant_id\":\"tenant1\"}'"
echo ""
echo "2. Open in Browser:"
echo "   open http://localhost:3000/login.html"
echo ""
echo "3. Run Integration Tests:"
echo "   python3 test_integration.py"
echo ""
echo "=========================================="
echo "To Stop Servers:"
echo "=========================================="
echo "  pkill -f 'uvicorn api.main:app'"
echo "  pkill -f 'http.server 3000'"
echo ""

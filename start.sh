#!/bin/bash
echo ""
echo " Collapse Monitor"
echo " ----------------"
pip3 install -r requirements.txt -q
python3 server.py &
SERVER_PID=$!
echo " Server running (PID: $SERVER_PID)"
sleep 2
if command -v open &>/dev/null; then
    open http://localhost:5000
elif command -v xdg-open &>/dev/null; then
    xdg-open http://localhost:5000
fi
echo " Open: http://localhost:5000"
echo " Press Ctrl+C to stop."
echo ""
wait $SERVER_PID

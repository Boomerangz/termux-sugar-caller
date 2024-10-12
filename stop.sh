#! /bin/bash

kill -9 $(pgrep -f "form.py" | grep -v $$)
kill -9 $(pgrep -f "stop_basal.py" | grep -v $$)
termux-wake-unlock
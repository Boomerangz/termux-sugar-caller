#! /bin/bash

kill -9 $(pgrep -f "form.py" | grep -v $$)
termux-wake-unlock
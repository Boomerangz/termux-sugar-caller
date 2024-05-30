#! /bin/bash

kill -9 $(pgrep -f "main.py" | grep -v $$)

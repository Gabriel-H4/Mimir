#!/bin/sh
gunicorn --chdir /mimir mimir:mimir -w 2 --threads 2 -b 0.0.0.0:80
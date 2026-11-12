#!/bin/sh
# Live tables of the four v14 retold questions, refreshed every 10 s (read-only).
cd "$(dirname "$0")"
while true; do
  out=$(for q in normative self typical-ai typical-employee; do python3 -I watch.py --once --runs runs-v14-$q --n 10; echo; done)
  printf '\033[2J\033[H%s\n' "$out"
  sleep 10
done

import json
import sys

lines = []
for line in sys.stdin.readlines():
    j = json.loads(line)
    print j['id'], "\t", line


import json
import sys

lines = []
for line in sys.stdin:
    j = json.loads(line)
    print j['id'], "\t", line,


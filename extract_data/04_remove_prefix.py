import sys

for line in sys.stdin:
    parts = line.split("\t", 1)
    print parts[1],


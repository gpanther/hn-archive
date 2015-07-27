import sys

for line in sys.stdin.readlines():
    print line.split("\t", 1)[1]


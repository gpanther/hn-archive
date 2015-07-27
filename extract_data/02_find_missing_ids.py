import bitarray
import json
import sys

min_id, max_id = int(sys.argv[1]), int(sys.argv[2])

bits = bitarray.bitarray(max_id - min_id + 2)
bits.setall(False)
for line in sys.stdin.readlines():
    d = json.loads(line)
    bits[d['id']] = True

for i in xrange(min_id, max_id+1):
    if bits[i]: continue
    print "Missing: %d" % i


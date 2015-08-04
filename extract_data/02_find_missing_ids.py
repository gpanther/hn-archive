import bitarray
import json
import sys

min_id, max_id = int(sys.argv[1]), int(sys.argv[2])

bit_count = max_id - min_id + 1
bits = bitarray.bitarray(bit_count)
bits.setall(False)
for line in sys.stdin.readlines():
    d = json.loads(line)
    bits[d['id'] - min_id] = True

for i in xrange(0, bit_count):
    if bits[i]: continue
    print "Missing: %d" % (min_id + i)


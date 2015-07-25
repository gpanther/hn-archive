# based on http://gbayer.com/big-data/app-engine-datastore-how-to-efficiently-export-your-data/

import bz2
import glob
import urllib2
import time
import json
import zlib

# Make sure App Engine APK is available
import sys
sys.path.append('/usr/local/google_appengine')

from google.appengine.api.files import records
from google.appengine.datastore import entity_pb
from google.appengine.api import datastore

output = bz2.BZ2File('hn-content.json.bz2', 'wb', compresslevel=9)
entries = {}
min_id, max_id = sys.maxint, 0
for filename in glob.glob(sys.argv[1] + '/*_HNEntry-*'):
    print 'Loading %s' % filename
    raw = open(filename, 'r')
    reader = records.RecordsReader(raw)
    for record in reader:
        entity_proto = entity_pb.EntityProto(contents=record)
        entity = datastore.Entity.FromPb(entity_proto)

        key_id = int(entity.key().id())
        retrieved_at_ts = int(time.mktime(entity['retrieved_at'].timetuple()))
        body = json.loads(json.loads(zlib.decompress(entity['body'])))

        if body is not None:
            assert key_id == int(body['id']), \
                'Key and id from body should match: %d, %d' % (key_id, int(body['id']))
        assert key_id not in entries, 'Backup should not contain duplicates: %d' % key_id
        entries[key_id] = True
        print >>output, json.dumps({'id': key_id, 'retrieved_at_ts': retrieved_at_ts, 'body': body})

        min_id = min(min_id, key_id)
        max_id = max(max_id, key_id)

print 'Min/Max ID: %d, %d' % (min_id, max_id)

for i in xrange(min_id, max_id+1):
    if i in entries:
        continue
    print 'Retrieving missing entry %d' % i
    r = urllib2.urlopen('http://hn.algolia.com/api/v1/items/%d' % i)
    assert r.getcode() == 200
    print >>output, json.dumps({'id': i, 'retrieved_at_ts': int(time.time()), 'body': json.loads(r.read())})

output.close()


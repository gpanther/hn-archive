# based on http://gbayer.com/big-data/app-engine-datastore-how-to-efficiently-export-your-data/

import glob
import json
import sys
import time
import zlib

# Make sure App Engine APK is available
sys.path.append('/usr/local/google_appengine')

from google.appengine.api.files import records
from google.appengine.datastore import entity_pb
from google.appengine.api import datastore

min_id, max_id = sys.maxint, 0
for backup_directory in sys.argv[1:]:
    for filename in glob.glob(backup_directory + '/*_HNEntry-*'):
        print >> sys.stderr, 'Loading %s' % filename
        raw = open(filename, 'r')
        reader = records.RecordsReader(raw)
        for record in reader:
            entity_proto = entity_pb.EntityProto(contents=record)
            entity = datastore.Entity.FromPb(entity_proto)

            key_id = int(entity.key().id())
            retrieved_at_ts = int(time.mktime(entity['retrieved_at'].timetuple()))
            body = json.loads(json.loads(zlib.decompress(entity['body'])))
            if body is None:
                print >> sys.stderr, 'None for %d' % key_id
                continue
            if 'id' not in body:
                print >> sys.stderr, "Missing body id for %d" % key_id
                body['id'] = key_id

            assert key_id == int(body['id']), \
                'Key and id from body should match: %d, %d' % (key_id, int(body['id']))

            output = json.dumps({
                'id': key_id,
                'source': 'firebase',
                'retrieved_at_ts': retrieved_at_ts,
                'body': body,
            })
            assert "\n" not in output
            print output

            min_id = min(min_id, key_id)
            max_id = max(max_id, key_id)
        print >> sys.stderr, 'Min/Max ID: {:,} / {:,}'.format(min_id, max_id)

print >> sys.stderr, "Done!"

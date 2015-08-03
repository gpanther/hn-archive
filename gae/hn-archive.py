import functools
import logging
import os

from google.appengine.api import memcache
from google.appengine.api import taskqueue
from google.appengine.ext import deferred
from google.appengine.ext import ndb
import jinja2
import webapp2
from webapp2_extras import routes

import models

ENABLE_DATASTORE_WRITES = True

IS_LOCAL_DEV_SERVER = os.environ.get('SERVER_SOFTWARE', '').startswith('Dev')

JINJA_ENVIRONMENT = jinja2.Environment(
    loader=jinja2.FileSystemLoader(os.path.join(os.path.dirname(__file__), 'templates')),
    autoescape=True)
JINJA_ENVIRONMENT.filters['add_thousands_separator'] = lambda value: '{0:,}'.format(value)

TASK_RUNNING_KEY = 'fetcher_running'

FETCH_BATCH_SIZE = 10


def guarded_internal_callback(f):
    """
    Checks that the method invocation indeed came from the GAE cron service as described
    in https://cloud.google.com/appengine/docs/python/config/cron#Python_app_yaml_Securing_URLs_for_cron
    """
    @functools.wraps(f)
    def wrapper(self, *args, **kwargs):
        assert self.request.headers['X-Appengine-Cron'] == 'true'
        assert self.request.remote_addr == '0.1.0.1'
        return f(self, *args, **kwargs)
    return wrapper


@ndb.tasklet
def fetch_raw(url):
    result = yield ndb.get_context().urlfetch(
        url,
        headers={
            'User-Agent': "Grey Panther's Hacker News Archiver - https://hn-archive.appspot.com/ "
    })
    assert not result.content_was_truncated
    raise ndb.Return(result)


@ndb.tasklet
def fetch(url):
    result = yield fetch_raw(url)
    assert result.status_code == 200
    raise ndb.Return(result.content)


@ndb.toplevel
def fetch_items_batch():
    memcache.set(TASK_RUNNING_KEY, 1, time=600)
    if not ENABLE_DATASTORE_WRITES:
        logging.info("Datastore writes disabled, sleeping")
        return
    last_retrieved_id, max_item_id = yield [models.LastRetrievedId.get(default=0), models.MaxItemId.get()]

    batch_start_id = last_retrieved_id + 1
    batch_end_id = last_retrieved_id + FETCH_BATCH_SIZE
    batch_end_id = min(batch_end_id, max_item_id)

    if batch_end_id < batch_start_id:
        logging.info("Pausing since all %d items have been retrieved" % max_item_id)
        raise ndb.Return()

    logging.info("Retrieving items %d..%d (inclusive)", batch_start_id, batch_end_id)
    ids_to_retrieve = range(batch_start_id, batch_end_id + 1)
    fetch_results = yield [
        fetch_raw('https://hacker-news.firebaseio.com/v0/item/%d.json' % i)
        for i in ids_to_retrieve
    ]

    inaccessible_entries = len([r for r in fetch_results if r.status_code != 200])
    if inaccessible_entries == FETCH_BATCH_SIZE:
        logging.error("All %d entries returned an error, pausing for a while" % FETCH_BATCH_SIZE)
        raise ndb.Return()

    logging.info("Retrieved items, storing them")
    futures = []
    for i, result in zip(ids_to_retrieve, fetch_results):
        if result.status_code == 200:
            m = models.HNEntry(id=i, body=result.content)
        else:
            m = models.InaccessibleHNEntry(id=i, error_code=result.status_code)
        futures.append(m.put_async())
    yield futures

    logging.info("Updating counters")
    yield [
        models.LastRetrievedId.set(batch_end_id),
        models.InaccessibleEntryCount.increment(inaccessible_entries),
    ]

    deferred.defer(fetch_items_batch, _countdown=2, _queue='fetch')


class FetchMaxItemId(webapp2.RequestHandler):
    @guarded_internal_callback
    @ndb.toplevel
    def get(self):
        if not ENABLE_DATASTORE_WRITES:
            logging.info("Datastore writes disabled, sleeping")
            return
        result = yield fetch('https://hacker-news.firebaseio.com/v0/maxitem.json')
        assert int(result) > 0
        logging.info("MaxItemId: %d" % int(result))
        yield models.MaxItemId.set(int(result))


class FetchItemsKickoff(webapp2.RequestHandler):
    @guarded_internal_callback
    def get(self):
        if not ENABLE_DATASTORE_WRITES:
            logging.info("Datastore writes disabled, sleeping")
            return
        if memcache.get(TASK_RUNNING_KEY) is not None:
            return
        memcache.set(TASK_RUNNING_KEY, 1, time=600)
        deferred.defer(fetch_items_batch, _countdown=1, _queue='fetch')


class Placeholder(webapp2.RequestHandler):
    @ndb.toplevel
    def get(self):
        values = {
            'last_retrieved_id': models.LastRetrievedId.get(),
            'max_item_id': models.MaxItemId.get(),
            'inaccessible_entries': models.InaccessibleEntryCount.get(),
        }

        retrieved_values = yield values.values()
        for k, v in zip(values.keys(), retrieved_values):
            values[k] = v

        template = JINJA_ENVIRONMENT.get_template('index.html')
        self.response.cache_control = 'public'
        self.response.cache_control.max_age = 300
        self.response.headers.add('pragma', 'public')
        self.response.write(template.render(values))


app = webapp2.WSGIApplication([
    ('/', Placeholder),
], debug=IS_LOCAL_DEV_SERVER)


cron_app = webapp2.WSGIApplication([
    routes.PathPrefixRoute('/tasks', [
        webapp2.Route('/fetch_max_item_id', FetchMaxItemId),
        webapp2.Route('/kickoff_fetch_items', FetchItemsKickoff),
    ]),
], debug=IS_LOCAL_DEV_SERVER)


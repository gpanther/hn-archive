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

IS_LOCAL_DEV_SERVER = os.environ.get('SERVER_SOFTWARE', '').startswith('Dev')

JINJA_ENVIRONMENT = jinja2.Environment(
    loader=jinja2.FileSystemLoader(os.path.join(os.path.dirname(__file__), 'templates')),
    autoescape=True)

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
def fetch(url):
    result = yield ndb.get_context().urlfetch(url)
    assert result.status_code == 200
    assert not result.content_was_truncated
    raise ndb.Return(result.content)


@ndb.toplevel
def fetch_items_batch():
    memcache.set(TASK_RUNNING_KEY, 1, time=60)
    last_retrieved_id = yield models.LastRetrievedId.get(0)

    batch_start_id = last_retrieved_id + 1
    batch_end_id = last_retrieved_id + FETCH_BATCH_SIZE
    logging.info("Retrieving items %d..%d", batch_start_id, batch_end_id)
    ids_to_retrieve = range(batch_start_id, batch_end_id + 1)
    jsons = yield [
        fetch('https://hacker-news.firebaseio.com/v0/item/%d.json' % i)
        for i in ids_to_retrieve
    ]

    logging.info("Retrieved items, storing them")
    yield [
        models.HNEntry(id=i, body=json).put_async() for i, json in zip(ids_to_retrieve, jsons)]

    logging.info("Updating last_retrieved_id")
    yield models.LastRetrievedId.set(batch_end_id)

    deferred.defer(fetch_items_batch, _countdown=1)


class FetchMaxItemId(webapp2.RequestHandler):
    @guarded_internal_callback
    @ndb.toplevel
    def get(self):
        result = yield fetch('https://hacker-news.firebaseio.com/v0/maxitem.json')
        assert int(result) > 0
        logging.info("MaxItemId: %d" % int(result))
        yield models.MaxItemId.set(int(result))


class FetchItemsKickoff(webapp2.RequestHandler):
    @guarded_internal_callback
    def get(self):
        if memcache.get(TASK_RUNNING_KEY) is not None:
            return
        deferred.defer(fetch_items_batch, _countdown=1)


class Placeholder(webapp2.RequestHandler):
    @ndb.toplevel
    def get(self):
        values = yield [models.LastRetrievedId.get(), models.MaxItemId.get()]

        template = JINJA_ENVIRONMENT.get_template('index.html')
        self.response.write(template.render({
            'last_retrieved_id': values[0],
            'max_item_id': values[1],
        }))


app = webapp2.WSGIApplication([
    ('/', Placeholder),
], debug=IS_LOCAL_DEV_SERVER)


cron_app = webapp2.WSGIApplication([
    routes.PathPrefixRoute('/tasks', [
        webapp2.Route('/fetch_max_item_id', FetchMaxItemId),
        webapp2.Route('/kickoff_fetch_items', FetchItemsKickoff),
    ]),
], debug=IS_LOCAL_DEV_SERVER)


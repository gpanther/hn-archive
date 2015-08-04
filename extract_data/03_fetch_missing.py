from datetime import date, timedelta
import re
import json
import urllib2
import sys
import time

def fetch_from_algolia(comment_id):
    try:
        r = urllib2.urlopen('http://hn.algolia.com/api/v1/items/%d' % comment_id)
    except urllib2.HTTPError:
        return None
    if r.getcode() != 200:
        return None
    return json.loads(r.read())

def fetch_from_site(comment_id):
    opener = urllib2.build_opener()
    # add your session cookie here to see dead comments
    opener.addheaders.append(('Cookie', ''))
    r = opener.open('https://news.ycombinator.com/item?id=%d' % comment_id)
    if r.getcode() != 200:
        return None

    content = r.read()
    content = re.search(r"<tr class='athing'>(.*?)</table>", content, re.DOTALL)
    if content is None:
        return None
    content = content.group(1)

    result = {}

    parent = re.search(r'<a href="item\?id=(\d+)">parent<', content)
    if parent is not None:
        result['parent'] = int(parent.group(1))

    text = re.search(
        r'<br><span class="comment">(.*?)</span>' + '<div class=\'reply\'>', content, re.DOTALL)
    text2 = re.search(
        r'<td class="title">.*?<a.*?(?:href="(.*?)")?.*?>(.*?)</a>', content, re.DOTALL)
    if text is not None:
        text = text.group(1).strip()
        result['text'] = text
        result['type'] = 'comment'
    elif text2 is not None:
        result['text'] = text2.group(2).strip()
        if '[dead]' in content:
            result['dead'] = True
        result['type'] = 'story'
        if text2.group(1) is not None:
            result['url'] = text2.group(1)

    if 'text' in result:
        g = re.match('^<span class="[a-z0-9]+">(.*)<span>$', result['text'], re.DOTALL)
        if g is not None:
            result['text'] = g.group(1).strip()

    user = re.search(r'<a href="user.*?>(.*?)<', content)
    if user is not None:
        result['by'] = user.group(1)

    comment_time = re.search(r'(\d+) days ago', content)
    if comment_time is None:
        if '[deleted]' in content:
            result['deleted'] = True
            return result
        else:
            return None
    comment_time = date.today() - timedelta(days=int(comment_time.group(1)))
    result['time'] = int(time.mktime(comment_time.timetuple()))

    return result
 

def print_result(i, source, json_dict):
    output = {
        'id': i,
        'source': source,
        'retrieved_at_ts': int(time.time()),
        'body': json_dict,
    }
    print json.dumps(output)

for i in open('missing_ids.txt', 'r'):
    i = int(i)

    output = {
        'id': i,
        'body': {
            'algolia': fetch_from_algolia(i),
            'site': fetch_from_site(i),
        },
        'source': 'mixed',
        'retrieved_at_ts': int(time.time()),
    }
    output = json.dumps(output)
    assert "\n" not in output
    print output


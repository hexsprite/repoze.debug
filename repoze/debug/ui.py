"""GUI for presenting ways to look at the repoze.debug data

"""

import cgi
import mimetypes
import os
import pprint
import time

from webob import exc
from webob import Request
from webob import Response

_HERE = os.path.abspath(os.path.dirname(__file__))
gui_flag = '__repoze.debug'

def is_gui_url(environ):
    return gui_flag in environ.get('PATH_INFO', '')

def get_mimetype(filename):
    type, encoding = mimetypes.guess_type(filename)
    if type is None and filename.endswith(".xul"):
        return 'application/vnd.mozilla.xul+xml'
    return type or 'application/octet-stream'

class DebugGui(object):

    def __init__(self, middleware):
        self.middleware = middleware
        self.static_dir = os.path.join(_HERE, 'static')

    def __call__(self, environ, start_response):
        """Pick apart this debug URL and return the correct response"""

        # Make WebOb versions of request and response
        req = Request(environ)

        try:
            # Process the request
            if req.url.find(gui_flag + "/static/") > -1:
                resp = self.getStatic(req)
            elif req.url.find(gui_flag + "feed.xml"):
                resp = self.getFeed(req)
        except ValueError, e:
            resp = exc.HTTPBadRequest(str(e))
        except exc.HTTPException, e:
            resp = e

        return resp(environ, start_response)

    def getStatic(self, req):

        fn = req.url.split("/")[-1]
        filename = os.path.join(self.static_dir, fn)
        res = Response(content_type=get_mimetype(filename))
        res.body = open(filename, 'rb').read()

        return res

    def _generateFeedTagURI(self, when, pid):
        """ See http//www.taguri.org """
        date = time.strftime('%Y-%m-%d', time.localtime(when))
        pid = self.middleware.pid
        return 'tag:repoze.org,%s:%s' % (date, pid)

    def _generateEntryTagURI(self, entry):
        """ See http//www.taguri.org """
        date = time.strftime('%Y-%m-%d', time.localtime(
            entry['request']['begin']))
        pid = self.middleware.pid
        return 'tag:repoze.org,%s:%s-%s' % (date, entry['id'], pid)

    def getFeed(self, req):
        """Get XML representing information in the middleware"""

        entries_xml = []

        for entry in self.middleware.entries:
            request = entry['request']
            response = entry.get('response')
            begin = time.localtime(request['begin'])
            entry_id = self._generateEntryTagURI(entry)
            entry_title = '%s %s ' % (request['method'], request['url'])

            # Make the <rz:cgi_variable> nodes into a string
            cgivars = ""
            for k,v in request['cgi_variables']:
                newv = cgi.escape(str(v))
                s = cgi_variable_fmt % (k, newv)
                cgivars = cgivars + s

            # Make the <rz:cgi_variable> nodes into a string
            wsgivars = ""
            for k,v in request['wsgi_variables']:
                newv = cgi.escape(str(v))
                s = wsgi_variable_fmt % (k, newv)
                wsgivars = wsgivars + s

            # Make the <rz:request> node
            rzrequest = rzrequest_fmt % {
                'begin': request['begin'],
                'cgi_variables': cgivars,
                'wsgi_variables': wsgivars,
                'method': request['method'],
                'url': request['url'],
                }

            if response is not None:
                # Make the <rz:request> node
                headers = ''
                for k,v in response['headers']:
                    newv = cgi.escape(str(v))
                    s = header_fmt % (k, newv)
                    headers = headers + s

                # If the response is text/xml, then include. If 
                # text/html, cgi.escape and include. Otherwise, skip.
                rh = dict(response['headers'])
                ct = rh.get('content-type')
                if ct is None:
                    # 40x errors don't generate a content type
                    body = ''
                elif ct.startswith("text/xml"):
                    body = response['body']
                elif ct.startswith("text/html"):
                    body = cgi.escape(response['body'])
                else:
                    body = ''
                rzresponse = rzresponse_fmt % {
                    'begin': response['begin'],
                    'end': response['end'],
                    'content-length': response['content-length'],
                    'headers': headers,
                    'status': response['status'],
                    'body': body,
                    }
            else:
                rzresponse = ''


            # Make the atom:entry/atom:content node
            content = contentfmt % {
                'logentry_id': entry_id,
                'rzrequest': rzrequest,
                'rzresponse': rzresponse,
                }

            entry_xml = entryfmt % {
                'entry_id':entry_id,
                'entry_title':cgi.escape(entry_title),
                'updated':time.strftime('%Y-%m-%dT%H:%M:%SZ', begin),
                'summary':cgi.escape(pprint.pformat(entry)),
                'content':content,
                }
            entries_xml.append(entry_xml)

        now = time.time()

        body = feedfmt % {
            'title':'repoze.debug feed for pid %s' % self.middleware.pid,
            'entries':'\n'.join(entries_xml),
            'feed_id':self._generateFeedTagURI(now, self.middleware.pid),
            'updated':time.strftime('%Y-%m-%dT%H:%M:%SZ', time.localtime(now)),
            }

        resp = Response(content_type='application/atom+xml', body=body)
        return resp

feedfmt = """\
<?xml version="1.0" encoding="utf-8"?>
<atom:feed xmlns:atom="http://www.w3.org/2005/Atom">

  <atom:title>%(title)s</atom:title>
  <atom:link href="http://example.org/"/>
  <atom:updated>%(updated)s</atom:updated>
  <atom:author>
    <atom:name></atom:name>
  </atom:author>
  <atom:id>%(feed_id)s</atom:id>
  %(entries)s
</atom:feed>
"""

entryfmt = """\
  <atom:entry>
    <atom:id>%(entry_id)s</atom:id>
    <atom:title>%(entry_title)s</atom:title>
    <atom:link href="http://example.org/2003/12/13/atom03"/>
    <atom:updated>%(updated)s</atom:updated>
    <atom:summary>%(summary)s</atom:summary>
    <atom:content>%(content)s</atom:content>
  </atom:entry>
"""

contentfmt = """\
<rz:logentry id="%(logentry_id)s" xmlns:rz="http://repoze.org/namespace">
  %(rzrequest)s
  %(rzresponse)s
</rz:logentry>
"""

cgi_variable_fmt = """<rz:cgi_variable name="%s">%s</rz:cgi_variable>
"""

wsgi_variable_fmt = """<rz:wsgi_variable name="%s">%s</rz:wsgi_variable>
"""

rzrequest_fmt = """<rz:request>
  <rz:begin>%(begin)s</rz:begin>
  %(cgi_variables)s
  <rz:method>%(method)s</rz:method>
  <rz:url>%(url)s</rz:url>
  %(wsgi_variables)s  
</rz:request>
"""

header_fmt = """<rz:header name="%s">%s</rz:header>
"""

rzresponse_fmt = """<rz:response>
  <rz:begin>%(begin)s</rz:begin>
  <rz:end>%(end)s</rz:end>
  <rz:content-length>%(content-length)s</rz:content-length>
  %(headers)s
  <rz:status>%(status)s</rz:status>
  <rz:body>
%(body)s
  </rz:body>
</rz:response>
"""

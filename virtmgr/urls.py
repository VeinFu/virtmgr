# -*- coding: utf-8 -*-


from virtmgr.api.hello import Hello
from virtmgr.api.server import ServersR, ServerR
from virtmgr import flask_api


resources = {
    '/hello/': Hello,
    '/servers/': ServersR,
    '/servers/<server_id>/': ServerR,
}


for url, viewset in resources.items():
    flask_api.add_resource(viewset, url)

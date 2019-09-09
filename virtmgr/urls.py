# -*- coding: utf-8 -*-


from virtmgr.api.hello import Hello
from virtmgr.api.server import NetPoolsR, ServersR, ServerR
from virtmgr import flask_api


resources = {
    '/hello/': Hello,
    '/servers/': ServersR,
    '/servers/<server_id>/': ServerR,
    '/servers/<server_id>/net_pools/': NetPoolsR,
}


for url, viewset in resources.items():
    flask_api.add_resource(viewset, url)

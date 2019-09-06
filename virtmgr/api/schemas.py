# -*- coding: utf-8 -*-

import flask_marshmallow
from marshmallow import fields

from virtmgr import app, models


ma = flask_marshmallow.Marshmallow(app)


class ServerSchema(ma.ModelSchema):
    class Meta:
        model = models.HostServer
        exclude = ('type', 'ssh_login', 'ssh_password')

    is_alive = fields.Boolean()

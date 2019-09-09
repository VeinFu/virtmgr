# -*- coding: utf-8 -*-

import flask
import flask_restful
import flask_sqlalchemy


from virtmgr.config import DevelopmentConfig


_api_blueprint = flask.Blueprint('api', __name__)
flask_api = flask_restful.Api(_api_blueprint)

app = flask.Flask('virtmgr')
app.register_blueprint(_api_blueprint, url_prefix='/cmpvirtmgr_api')
app.config.from_object(DevelopmentConfig)

db = flask_sqlalchemy.SQLAlchemy(app)


def initdb():
    db.create_all()


from virtmgr.urls import *

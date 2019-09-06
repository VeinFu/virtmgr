# -*- coding: utf-8 -*-

from virtmgr.libs.connection import connection_manager
from virtmgr import db


class BasicModel(db.Model):
    __abstract__ = True

    id = db.Column(db.Integer, primary_key=True)


class HostServer(BasicModel):
    name = db.Column(db.String(20), unique=True, nullable=False)
    hostname = db.Column(db.String(32), unique=True, nullable=False)
    ssh_login = db.Column(db.String(20), unique=True, nullable=False)
    ssh_password = db.Column(db.String(32), unique=True, nullable=False)
    ssh_port = db.Column(db.Integer, default=22)
    type = db.Column(db.Integer, default=1)

    __tablename__ = 'server_host'

    def __str__(self):
        return self.hostname

    @property
    def is_alive(self):
        return True if connection_manager.host_is_up(self.hostname) == 1 else False

# -*- coding: utf-8 -*-

from flask import request
from flask_restful import Resource, abort

from virtmgr import db
from virtmgr.api.schemas import ServerSchema
from virtmgr.models import HostServer


class BaseResource(Resource):
    filterd = {}


class ServersR(BaseResource):

    query = HostServer.query
    session = db.session

    def get(self):
        """ 获取server列表 """
        server_hosts = self.query.all()
        if not server_hosts:
            return {'servers': []}
        return {'servers': ServerSchema().dump(server_hosts, many=True)}

    def post(self):
        """ 添加新的宿主server """
        print(request.get_json())
        name = request.get_json()['name']
        hostname = request.get_json()['hostname']
        ssh_login = request.get_json()['ssh_login']
        ssh_password = request.get_json()['ssh_password']
        server_host = HostServer(name=name, hostname=hostname, ssh_login=ssh_login, ssh_password=ssh_password)
        self.session.add(server_host)
        self.session.commit()
        return ServerSchema().dump(server_host)


class ServerR(BaseResource):
    query = HostServer.query
    session = db.session

    def get(self, server_id):
        """ 获取某个server详情 """
        print(request.args.get('index'))
        server_host = self.query.filter_by(id=server_id).first()
        if not server_host:
            abort(404, message='Server {} Not Exist'.format(server_id))
        return ServerSchema().dump(server_host)

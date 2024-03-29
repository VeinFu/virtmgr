# -*- coding: utf-8 -*-

from flask import request
from flask_restful import Resource, abort
from libvirt import libvirtError

from virtmgr.libs.connection import cvmConnect
from virtmgr import db
from virtmgr.api.schemas import ServerSchema
from virtmgr.models import HostServer


class ServerBaseResource(Resource):
    query = HostServer.query
    session = db.session


class ServersR(ServerBaseResource):

    # query = HostServer.query
    # session = db.session

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


class ServerR(ServerBaseResource):
    # query = HostServer.query
    # session = db.session

    def get(self, server_id):
        """ 获取某个server详情 """
        # print(request.args.get('index'))
        server_host = self.query.filter_by(id=server_id).first_or_404(
            description='Server {} Not Exist'.format(server_id))
        #if not server_host:
        #    abort(404, message='Server {} Not Exist'.format(server_id))
        return ServerSchema().dump(server_host)


class NetPoolsR(ServerBaseResource):

    def get(self, server_id):
        """ 获取网络池列表 """
        server_host = self.query.filter_by(id=server_id).first_or_404(
            description='Server {} Not Exist'.format(server_id))
        try:
            conn = cvmConnect(server_host.hostname, server_host.type)
            net_pools = conn.get_networks()
            conn.close()
        except libvirtError as err:
            abort(500, message=str(err))
        return {'net_pools': net_pools}


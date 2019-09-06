# -*- coding: utf-8 -*-


def _mysql_config(host, name, user, password, port):
    return 'mysql://{user}:{password}@{host}:{port}/{name}?charset=utf8'.format(
        user=user, password=password, host=host, port=port, name=name)


class BasicConfig(object):

    DEBUG = False

    SQLALCHEMY_DATABASE_URI = _mysql_config(
        host='127.0.0.1',
        name='cmpvirtmgr',
        user='cmpvirtmgr',
        password='cmpvirtmgr123',
        port='3306'
    )

    SQLALCHEMY_TRACK_MODIFICATIONS = False
    RESTFUL_JSON = {'ensure_ascii': False}


class DevelopmentConfig(BasicConfig):

    DEBUG = True

    LIBVIRT_KEEPALIVE_INTERVAL = 5
    LIBVIRT_KEEPALIVE_COUNT = 5

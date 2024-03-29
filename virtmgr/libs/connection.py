import libvirt
import threading
import socket

from virtmgr.libs import util

from libvirt import libvirtError

from virtmgr.libs.rwlock import ReadWriteLock
from virtmgr import app


CONN_TCP = 1
TCP_PORT = 16509


class cvmEventLoop(threading.Thread):
    def __init__(self, group=None, target=None, name=None, args=(), kwargs={}):
        # register the default event implementation
        # of libvirt, as we do not have an existing
        # event loop.
        libvirt.virEventRegisterDefaultImpl()

        if name is None:
            name = 'libvirt event loop'

        super(cvmEventLoop, self).__init__(group, target, name, args, kwargs)

        # we run this thread in deamon mode, so it does
        # not block shutdown of the server
        self.daemon = True

    def run(self):
        while True:
            # if this method will fail it raises libvirtError
            # we do not catch the exception here so it will show up
            # in the logs. Not sure when this call will ever fail
            libvirt.virEventRunDefaultImpl()


class cvmConnection(object):
    """
    class representing a single connection stored in the Connection Manager
    # to-do: may also need some locking to ensure to not connect simultaniously in 2 threads
    """

    def __init__(self, host, conn):
        """
        Sets all class attributes and tries to open the connection
        """
        # connection lock is used to lock all changes to the connection state attributes
        # (connection and last_error)
        self.connection_state_lock = threading.Lock()
        self.connection = None
        self.last_error = None

        # credentials
        self.host = host
        self.type = conn

        # connect
        self.connect()

    def connect(self):
        self.connection_state_lock.acquire()
        try:
            # recheck if we have a connection (it may have been
            if not self.connected:
                if self.type == CONN_TCP:
                    self.__connect_tcp()
                else:
                    raise ValueError('"{type}" is not a valid connection type'.format(type=self.type))

                if self.connected:
                    # do some preprocessing of the connection:
                    #     * set keep alive interval
                    #     * set connection close/fail handler
                    try:
                        self.connection.setKeepAlive(
                            connection_manager.keepalive_interval, connection_manager.keepalive_count)
                        try:
                            self.connection.registerCloseCallback(self.__connection_close_callback, None)
                        except:
                            # Temporary fix for libvirt > libvirt-0.10.2-41
                            pass
                    except libvirtError as e:
                        # hypervisor driver does not seem to support persistent connections
                        self.last_error = str(e)
        finally:
            self.connection_state_lock.release()

    @property
    def connected(self):
        try:
            return self.connection is not None and self.connection.isAlive()
        except libvirtError:
            # isAlive failed for some reason
            return False

    def __connection_close_callback(self, connection, reason, opaque=None):
        self.connection_state_lock.acquire()
        try:
            # on server shutdown libvirt module gets freed before the close callbacks are called
            # so we just check here if it is still present
            if libvirt is not None:
                if reason == libvirt.VIR_CONNECT_CLOSE_REASON_ERROR:
                    self.last_error = 'connection closed: Misc I/O error'
                elif reason == libvirt.VIR_CONNECT_CLOSE_REASON_EOF:
                    self.last_error = 'connection closed: End-of-file from server'
                elif reason == libvirt.VIR_CONNECT_CLOSE_REASON_KEEPALIVE:
                    self.last_error = 'connection closed: Keepalive timer triggered'
                elif reason == libvirt.VIR_CONNECT_CLOSE_REASON_CLIENT:
                    self.last_error = 'connection closed: Client requested it'
                else:
                    self.last_error = 'connection closed: Unknown error'

            # prevent other threads from using the connection (in the future)
            self.connection = None
        finally:
            self.connection_state_lock.release()

    def __libvirt_auth_credentials_callback(self, credentials, user_data):
        for credential in credentials:
            if credential[0] == libvirt.VIR_CRED_AUTHNAME:
                credential[4] = 'test'
                if len(credential[4]) == 0:
                    credential[4] = credential[3]
            elif credential[0] == libvirt.VIR_CRED_PASSPHRASE:
                credential[4] = 'r00tme'
            else:
                return -1
        return 0

    def __connect_tcp(self):
        """ 同时支持libvirt远程tcp认证和不认证连接
            （但测试下来tcp认证远程连接有问题，目前还没有明确解决方案，#### todo)
        """
        uri = 'qemu+tcp://%s/system' % self.host

        try:
            self.connection = libvirt.open(uri)
            self.last_error = None

        except libvirtError as e:
            if 'authentication failed' in str(e):
                flags = [libvirt.VIR_CRED_AUTHNAME, libvirt.VIR_CRED_PASSPHRASE]
                auth = [flags, self.__libvirt_auth_credentials_callback, None]
                try:
                    self.connection = libvirt.openAuth(uri, auth, 0)
                    self.last_error = None
                except libvirtError as err:
                    self.last_error = 'Connection Failed: ' + str(err)
                    self.connection = None
            else:
                self.last_error = 'Connection Failed: ' + str(e)
                self.connection = None

    def close(self):
        """
        closes the connection (if it is active)
        """
        self.connection_state_lock.acquire()
        try:
            if self.connected:
                try:
                    # to-do: handle errors?
                    self.connection.close()
                except libvirtError:
                    pass

            self.connection = None
            self.last_error = None
        finally:
            self.connection_state_lock.release()

    def __del__(self):
        if self.connection is not None:
            # unregister callback (as it is no longer valid if this instance gets deleted)
            try:
                self.connection.unregisterCloseCallback()
            except:
                pass

    def __str__(self):
        if self.type == CONN_TCP:
            type_str = 'tcp'
        else:
            type_str = 'invalid_type'

        return 'qemu+{}://{}/system'.format(type_str, self.host)

    def __repr__(self):
        return '<cvmConnection {connection_str}>'.format(connection_str=str(self))


class cvmConnectionManager(object):
    def __init__(self, keepalive_interval=5, keepalive_count=5):
        self.keepalive_interval = keepalive_interval
        self.keepalive_count = keepalive_count

        # connection dict
        # maps hostnames to a list of connection objects for this hostname
        # atm it is possible to create more than one connection per hostname
        # with different logins or auth methods
        # connections are shared between all threads, see:
        #     http://wiki.libvirt.org/page/FAQ#Is_libvirt_thread_safe.3F
        self._connections = dict()
        self._connections_lock = ReadWriteLock()

        # start event loop to handle keepalive requests and other events
        self._event_loop = cvmEventLoop()
        self._event_loop.start()

    def _search_connection(self, host, conn):
        """
        search the connection dict for a connection with the given credentials
        if it does not exist return None
        """
        self._connections_lock.acquireRead()
        try:
            if host in self._connections:
                connections = self._connections[host]

                for connection in connections:
                    if connection.type == conn:
                        return connection
        finally:
            self._connections_lock.release()

        return None

    def get_connection(self, host, conn):
        """
        returns a connection object (as returned by the libvirt.open* methods) for the given host and credentials
        raises libvirtError if (re)connecting fails
        """
        # force all string values to unicode
        host = str(host)

        connection = self._search_connection(host, conn)

        if connection is None:
            self._connections_lock.acquireWrite()
            try:
                # we have to search for the connection again after aquireing the write lock
                # as the thread previously holding the write lock may have already added our connection
                connection = self._search_connection(host, conn)
                if connection is None:
                    # create a new connection if a matching connection does not already exist
                    connection = cvmConnection(host, conn)

                    # add new connection to connection dict
                    if host in self._connections:
                        self._connections[host].append(connection)
                    else:
                        self._connections[host] = [connection]
            finally:
                self._connections_lock.release()

        elif not connection.connected:
            # try to (re-)connect if connection is closed
            connection.connect()

        if connection.connected:
            # return libvirt connection object
            return connection.connection
        else:
            # raise libvirt error
            raise libvirtError(connection.last_error)

    def host_is_up(self, hostname):
        """
        returns True if the given host is up and we are able to establish
        a connection using the given credentials.
        """
        try:
            socket_host = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            socket_host.settimeout(5)
            socket_host.connect((hostname, TCP_PORT))
            socket_host.close()
            return True
        except Exception as err:
            return err


connection_manager = cvmConnectionManager(
    app.config['LIBVIRT_KEEPALIVE_INTERVAL'] if hasattr(app.config, 'LIBVIRT_KEEPALIVE_INTERVAL') else 5,
    app.config['LIBVIRT_KEEPALIVE_COUNT'] if hasattr(app.config, 'LIBVIRT_KEEPALIVE_COUNT') else 5
)


class cvmConnect(object):
    def __init__(self, host, conn):
        self.host = host
        self.conn = conn

        # get connection from connection manager
        self.cvm = connection_manager.get_connection(host, conn)

    def get_cap_xml(self):
        """Return xml capabilities"""
        return self.cvm.getCapabilities()

    def is_kvm_supported(self):
        """Return KVM capabilities."""
        return util.is_kvm_available(self.get_cap_xml())

    def get_storages(self):
        storages = []
        for pool in self.cvm.listStoragePools():
            storages.append(pool)
        for pool in self.cvm.listDefinedStoragePools():
            storages.append(pool)
        return storages

    def get_networks(self):
        virtnet = []
        for net in self.cvm.listNetworks():
            virtnet.append(net)
        for net in self.cvm.listDefinedNetworks():
            virtnet.append(net)
        return virtnet

    def get_ifaces(self):
        interface = []
        for inface in self.cvm.listInterfaces():
            interface.append(inface)
        for inface in self.cvm.listDefinedInterfaces():
            interface.append(inface)
        return interface

    def get_iface(self, name):
        return self.cvm.interfaceLookupByName(name)

    def get_secrets(self):
        return self.cvm.listSecrets()

    def get_secret(self, uuid):
        return self.cvm.secretLookupByUUIDString(uuid)

    def get_storage(self, name):
        return self.cvm.storagePoolLookupByName(name)

    def get_volume_by_path(self, path):
        return self.cvm.storageVolLookupByPath(path)

    def get_network(self, net):
        return self.cvm.networkLookupByName(net)

    def get_instance(self, name):
        return self.cvm.lookupByName(name)

    def get_instances(self):
        instances = []
        for inst_id in self.cvm.listDomainsID():
            dom = self.cvm.lookupByID(int(inst_id))
            instances.append(dom.name())
        for name in self.cvm.listDefinedDomains():
            instances.append(name)
        return instances

    def get_snapshots(self):
        instance = []
        for snap_id in self.cvm.listDomainsID():
            dom = self.cvm.lookupByID(int(snap_id))
            if dom.snapshotNum(0) != 0:
                instance.append(dom.name())
        for name in self.cvm.listDefinedDomains():
            dom = self.cvm.lookupByName(name)
            if dom.snapshotNum(0) != 0:
                instance.append(dom.name())
        return instance

    def get_net_device(self):
        netdevice = []
        for dev in self.cvm.listAllDevices(0):
            xml = dev.XMLDesc(0)
            dev_type = util.get_xml_path(xml, '/device/capability/@type')
            if dev_type == 'net':
                netdevice.append(util.get_xml_path(xml, '/device/capability/interface'))
        return netdevice

    def get_host_instances(self):
        vname = {}
        memory = self.cvm.getInfo()[1] * 1048576
        for name in self.get_instances():
            dom = self.get_instance(name)
            mem = util.get_xml_path(dom.XMLDesc(0), "/domain/currentMemory")
            mem = int(mem) * 1024
            mem_usage = (mem * 100) / memory
            cur_vcpu = util.get_xml_path(dom.XMLDesc(0), "/domain/vcpu/@current")
            if cur_vcpu:
                vcpu = cur_vcpu
            else:
                vcpu = util.get_xml_path(dom.XMLDesc(0), "/domain/vcpu")
            vname[dom.name()] = (dom.info()[0], vcpu, mem, mem_usage)
        return vname

    def close(self):
        """Close connection"""
        # to-do: do not close connection ;)
        self.cvm.close()

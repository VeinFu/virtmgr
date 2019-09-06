import random
import libxml2
import libvirt
import paramiko
from flask_restful import reqparse
from functools import wraps

# from rest_framework import serializers


def is_kvm_available(xml):
    kvm_domains = get_xml_path(xml, "//domain/@type='kvm'")
    if kvm_domains > 0:
        return True
    else:
        return False


def randomMAC():
    """Generate a random MAC address."""
    # qemu MAC
    oui = [0x52, 0x54, 0x00]

    mac = oui + [random.randint(0x00, 0xff),
                 random.randint(0x00, 0xff),
                 random.randint(0x00, 0xff)]
    return ':'.join(map(lambda x: "%02x" % x, mac))


def randomUUID():
    """Generate a random UUID."""

    u = [random.randint(0, 255) for dummy in range(0, 16)]
    return "-".join(["%02x" * 4, "%02x" * 2, "%02x" * 2, "%02x" * 2, "%02x" * 6]) % tuple(u)


def get_max_vcpus(conn, type=None):
    """@param conn: libvirt connection to poll for max possible vcpus
       @type type: optional guest type (kvm, etc.)"""
    if type is None:
        type = conn.getType()
    try:
        m = conn.getMaxVcpus(type.lower())
    except libvirt.libvirtError:
        m = 32
    return m


def xml_escape(str):
    """Replaces chars ' " < > & with xml safe counterparts"""
    if str is None:
        return None

    str = str.replace("&", "&amp;")
    str = str.replace("'", "&apos;")
    str = str.replace("\"", "&quot;")
    str = str.replace("<", "&lt;")
    str = str.replace(">", "&gt;")
    return str


def compareMAC(p, q):
    """Compare two MAC addresses"""
    pa = p.split(":")
    qa = q.split(":")

    if len(pa) != len(qa):
        if p > q:
            return 1
        else:
            return -1

    for i in range(len(pa)):
        n = int(pa[i], 0x10) - int(qa[i], 0x10)
        if n > 0:
            return 1
        elif n < 0:
            return -1
    return 0


def get_xml_path(xml, path=None, func=None):
    """
    Return the content from the passed xml xpath, or return the result
    of a passed function (receives xpathContext as its only arg)
    """
    doc = None
    ctx = None
    result = None

    try:
        doc = libxml2.parseDoc(xml)
        ctx = doc.xpathNewContext()

        if path:
            ret = ctx.xpathEval(path)
            if ret is not None:
                if type(ret) == list:
                    if len(ret) >= 1:
                        result = ret[0].content
                else:
                    result = ret

        elif func:
            result = func(ctx)

        else:
            raise ValueError("'path' or 'func' is required.")
    finally:
        if doc:
            doc.freeDoc()
        if ctx:
            ctx.xpathFreeContext()
    return result


def pretty_mem(val):
    val = int(val)
    if val > (10 * 1024 * 1024):
        return "%2.2f GB" % (val / (1024.0 * 1024.0))
    else:
        return "%2.0f MB" % (val / 1024.0)


def pretty_bytes(val):
    val = int(val)
    if val > (1024 * 1024 * 1024):
        return "%2.2f GB" % (val / (1024.0 * 1024.0 * 1024.0))
    else:
        return "%2.2f MB" % (val / (1024.0 * 1024.0))


#def get_validation_error(message, data=None, code=None):
#    if isinstance(message, Exception):
#        message = '{}'.format(message)
#    error = {'error_message': message}
#    if data:
#        error['data'] = data
#    if code:
#        error['code'] = code
#    return serializers.ValidationError(error)


#def check_args(schemas):
#    def deractor(func):
#        @wraps(func)
#        def warpper(view, *args, **kwargs):
#            parser = reqparse.RequestParser()
#            for schema in schemas:
#                parser.add_argument(schema)
#            view.filterd = parser.args
#            return func(view, *args, **kwargs)
#        return warpper
#
#    return deractor


def handle_uploaded_file(server_host, upload_type, path, f_name):
    target = path + '/' + str(f_name)
    if upload_type == 'local':
        destination = open(target, 'wb+')
        for chunk in f_name.chunks():
            destination.write(chunk)
        destination.close()
    else:
        file_abspath = str(f_name.temporary_file_path())
        try:
            t = paramiko.Transport((server_host.hostname, server_host.ssh_port))
            t.connect(username=server_host.ssh_login, password=server_host.ssh_password)
            sftp = paramiko.SFTPClient.from_transport(t)
            sftp.put(file_abspath, target)
            t.close()
        except Exception as err:
            raise get_validation_error(str(err))


def handle_downloaded_file(server_host, f_name, path):
    try:
        t = paramiko.Transport((server_host.hostname, server_host.ssh_port))
        t.connect(username=server_host.ssh_login, password=server_host.ssh_password)
        sftp = paramiko.SFTPClient.from_transport(t)
        sftp.get(f_name, path)
        t.close()
    except Exception as err:
        raise get_validation_error(str(err))

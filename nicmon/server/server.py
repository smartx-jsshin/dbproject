import os
import subprocess
import shlex
from flask import Flask, request
import MySQLdb
import logging
import json
import yaml
import ipaddress


class NICMonServer:
    def __init__(self, __db_ip, __user, __password, __dbname):
        self._db_conn = None
        self._db_cursor = None
        self.logger = None

        self._db_host = __db_ip
        self._db_user = __user
        self._db_passwd = __password
        self._db_name = __dbname

        self.init_logger()

    def init_logger(self):
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(logging.DEBUG)
        fm = logging.Formatter('%(name)-12s: %(levelname)-8s %(message)s')
        ch = logging.StreamHandler()
        ch.setLevel(logging.DEBUG)
        ch.setFormatter(fm)
        self.logger.addHandler(ch)

    def open_db(self):
        self._db_conn = MySQLdb.connect(host=self._db_host,
                                        user=self._db_user,
                                        passwd=self._db_passwd,
                                        db=self._db_name)
        self._db_cursor = self._db_conn.cursor(MySQLdb.cursors.DictCursor)
        self._db_conn.autocommit(True)

    def close_db(self):
        self._db_conn.close()

    def update_info(self, __server_id, __nic_info):
        self.open_db()
        try:
            nic_info = json.loads(__nic_info)
        except ValueError, e:
            self.logger.error(e.message)
            return "Json Format is not Valid: (" + e.message + ")"

        self.logger.debug("Received Information ==> ")
        self.logger.debug(nic_info)

        for nic in nic_info:
            self.update_nic_info(__server_id, nic)

        self.close_db()
        return "Updated Successfully"

    def update_nic_info(self, __server_id, __nic_info):
        # Server should update follow information
        # in "network" table
        # interface_id(auto_increment), server_id, nic_id(FK), net_id(FK), interface_name, ip_address, mac_address

        interface_id = None
        server_id = __server_id
        nic_id = self.get_nic_spec_id(__nic_info['model'], __nic_info['vendor'])
        interface_name = __nic_info['name']
        ip_address = __nic_info['inet']['ipaddr']
        mac_address = __nic_info['ether']['macaddr']
        net_id = self.get_net_id(ip_address)

        # Check the constraint and replace None value in to 'NULL' string
        if not interface_id or not server_id or not interface_name:
            self.logger.error("in update_nic_info(), Required information is empty!!")

        cmd = "select * from interface where server_id = " + server_id + \
              ' and interface_name = \"' + interface_name + '\"'
        self.logger.debug("in update_nic_info(), DB Query: " + cmd)
        self._db_cursor.execute(cmd)
        out = self._db_cursor.fetchallDict()
        self.logger.debug("in update_nic_info(), retrieve tuples from the DB: " + out.__str__())

        if len(out) is 1:
            # Interface is already exists
            # if exists, then find changed values, update them.
            # if not exists, then add new interface
            changed = False
            cmd = "UPDATE interface set"

            if out['nic_id'] != nic_id:
                cmd += " nic_id = " + nic_id
                changed = True
            if out['net_id'] != net_id:
                cmd += " net_id = " + net_id
                changed = True
            if out['interface_name'] != interface_name:
                cmd += " interface_name = " + interface_name
                changed = True
            if out['ip_address'] != ip_address:
                cmd += " ip_address = " + ip_address
                changed = True
            if out['mac_address'] != mac_address:
                cmd += " mac_address = " + mac_address
                changed = True

            if changed:
                self.logger.debug("in update_nic_info(), Update Query: " + cmd)
                self._db_cursor.execute(cmd)
            else:
                self.logger.debug("in update_nic_info(), No Update for NIC information from Server "+ server_id)

        elif len(out) is 0:
            # Interfaces is new
            self.logger.debug("in update_nic_info(), Input new tuple into interface table:  %s %s %s %s %s %s"
                              % (server_id, nic_id, net_id, interface_name, ip_address, mac_address))

            cmd = "Insert into " \
                  "interface (server_id, nic_id, net_id, interface_name, ip_address, mac_address) " \
                  "VALUES " \
                  + "(\""+str(server_id)+"\", \""+str(nic_id)+"\", \""+str(net_id)+"\", \""\
                        +str(interface_id)+"\", \""+ip_address+"\", \""+mac_address + "\")"

            self.logger.debug("in update_nic_info(), Input Query: " + cmd)
            self._db_cursor.execute(cmd)

            cmd = 'select * from interface'
            self.logger.debug("in update_nic_info(), DB Query to list all interface: " + cmd)
            self._db_cursor.execute(cmd)
            out = self._db_cursor.fetchallDict()
            self.logger.debug("in update_nic_info(), all interface list: " + out.__str__())

    def get_nic_spec_id(self, __model, __vendor):
        if __model == 'NULL':
            __model='None'

        nic_id = 'NULL'

        cmd = 'select nic_id from nic_spec where model = \"' + __model +"\""
        self.logger.debug("in get_nic_spec_id(), DB Query: " + cmd)
        self._db_cursor.execute(cmd)
        out = self._db_cursor.fetchallDict()
        self.logger.debug("in get_nic_spec_id(), " + "Query output: " + out.__str__())

        if len(out) is 0:
            # The NIC Model is not exist
            cmd = "insert into nic_spec(model, vendor) values (\"" + __model+"\", \"" + __vendor + "\")"
            self.logger.debug("in get_nic_spec_id(), NIC Model is not exist. Add new nic_model: " + cmd)
            self._db_cursor.execute(cmd)

            cmd = 'select * from nic_spec'
            self.logger.debug("in get_nic_spec_id(), DB Query to list all nic_spec: " + cmd)
            self._db_cursor.execute(cmd)
            out = self._db_cursor.fetchallDict()
            self.logger.debug("in get_nic_spec_id(), all nic_spec list: " + out.__str__())

            cmd = 'select nic_id from nic_spec where model = \"' + __model + "\""
            self.logger.debug("in get_nic_spec_id(), DB Query: " + cmd)
            self._db_cursor.execute(cmd)
            out = self._db_cursor.fetchallDict()
            self.logger.debug("in get_nic_spec_id(), " + "Query output: " + out.__str__())
            nic_id = out[0]['nic_id']
            self.logger.debug("in get_nic_spec_id(), " + "nic_id :" + str(nic_id))
        else:
            # The NIC Model is exist
            nic_id = out[0]['nic_id']
            self.logger.debug("in get_nic_spec_id(), NIC Model is exist" + __model + ' nic_id: ' + str(nic_id))

        return nic_id

    def get_net_id(self, __net_addr):
        if __net_addr == 'NULL':
            return 'NULL'

        net_id = 'NULL'

        cmd = 'select net_id, net_address, net_subnet from network'
        self._db_cursor.execute(cmd)
        out = self._db_cursor.fetchallDict()

        print __net_addr
        nic_ip = ipaddress.ip_address(__net_addr.split('/')[0])

        for net in out:
            addr = net['net_address']+'/'+net['net_subnet']
            addr = ipaddress.ip_interface(addr.decode("utf-8"))
            net_ip = ipaddress.IPv4Network(addr)
            if nic_ip in net_ip:
                net_id = net['net_id']
                break

        if net_id == 'NULL':
            # network is not exist
            net_addr = ipaddress.IPv4Interface(__net_addr).network.__str__().split('/')
            cmd = "insert into network (net_address, net_subnet) values (\""+net_addr[0]+"\",\""+net_addr[1]+"\")"
            self.logger.debug("in get_net_id(), Insert new network DB Query: " + cmd)
            self._db_cursor.execute(cmd)

            cmd = "select net_id from network where net_address = \"" + net_addr[0] + "\""
            self.logger.debug("in get_net_id(), Insert new network DB Query: " + cmd)
            out = self._db_cursor.fetchallDict()
            net_id = out[0]['net_id']

        return net_id

    def shell_command(self, __cmd):
        self.logger.debug("Shell command: " + __cmd.__str__())
        if isinstance(__cmd, basestring):
            subproc = subprocess.Popen(shlex.split(__cmd),
                                       stdout=subprocess.PIPE,
                                       stderr=subprocess.PIPE,
                                       shell=True)
        elif isinstance(__cmd, dict):
            subproc = subprocess.Popen(__cmd, stdout=subprocess.PIPE,
                                       stderr=subprocess.PIPE, shell=True)
        (cmdout, cmderr) = subproc.communicate()
        return subproc.returncode, cmdout, cmderr

# Variable Definition Part
fp = os.path.join(os.getcwd(), 'server_config.yaml')
if os.path.exists(fp):
    o = open(fp, mode='r').read(-1)
    d = yaml.load(o)

    server_pt = d['server_port']
    db_ip = d['db_ipaddress']
    db_user = d['db_userid']
    db_password = d['db_password']
    db_name = d['db_name']

    nicmon = NICMonServer(db_ip, db_user, db_password, db_name)
else:
    print "Configuration file is not found: server_config.yaml"
    exit(1)

# REST API Part
app = Flask(__name__)


@app.route("/server/<string:server_id>/nic", methods=['POST'])
def create_nic_tuple(server_id):
    return nicmon.update_info(server_id, request.data)

app.run(port=server_pt)



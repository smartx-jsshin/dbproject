import os
import subprocess
import shlex
from flask import Flask, request
import MySQLdb
import logging
import json
import ipaddress


class NICMonServer:
    def __init__(self, __db_ip, __user, __password, __dbname):
        self.db = None
        self.logger = None

        self.init_logger()
        self.init_db(__db_ip, __user, __password, __dbname)

    def init_logger(self):
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(logging.DEBUG)
        fm = logging.Formatter('%(name)-12s: %(levelname)-8s %(message)s')
        ch = logging.StreamHandler()
        ch.setLevel(logging.DEBUG)
        ch.setFormatter(fm)
        self.logger.addHandler(ch)

    def init_db(self, __db_ip, __user, __password, __dbname):
        self.db = MySQLdb.connect(host=__db_ip,
                                  user=__user,
                                  passwd=__password,
                                  db=__dbname).cursor(MySQLdb.cursors.DictCursor)

    def update_info(self, __server_id, __nic_info):
        try:
            nic_info = json.loads(__nic_info)
        except ValueError, e:
            self.logger.error(e.message)
            return "Json Format is not Valid: (" + e.message + ")"

        self.logger.debug("Received Information ==> ")
        self.logger.debug(nic_info)

        for nic in nic_info:
            self.update_nic_info(__server_id, nic)

        return "Updated Successfully"

    def update_nic_info(self, __server_id, __nic_info):
        # Server should update follow informations
        # in "network" table
        # interface_id(auto_increment), server_id, nic_id(FK), net_id(FK), interface_name, ip_address, mac_address

        # Check duplicated tuple in "network" table

        interface_id = 1
        server_id = __server_id
        nic_id = self.get_nic_spec_id(__nic_info['model'], __nic_info['vendor'])
        interface_name = __nic_info['name']
        ip_address = __nic_info['inet']['ipaddr']
        mac_address = __nic_info['ether']['macaddr']

        net_addr = ipaddress.IPv4Interface(__nic_info['inet']['ipaddr']).network.__str__()
        net_id = self.get_net_id(net_addr)

        # Check the constraint and replace None value in to 'NULL' string
        if not interface_id or not server_id or not interface_name:
            self.logger.error("in update_nic_info(), Required information is empty!!")

        cmd = "select * from interface where server_id = " + server_id + \
              ' and interface_name = \"' + interface_name + '\"'
        self.logger.debug("in update_nic_info(), DB Query: " + cmd)
        self.db.execute(cmd)
        out = self.db.fetchallDict()
        self.logger.debug("in update_nic_info(), retrieve tuples from the DB: " + out.__str__())

        if len(out) is 1:
            # Interface is already exists
            # if exists, then find changed values, update them.
            # if not exists, then add new interface
            changed = False
            cmd = "UPDATE interface set"

            if out['interface_id'] != interface_id:
                cmd += " interface_id = " + interface_id
                changed = True
            if out['server_id'] != server_id:
                cmd += " server_id = " + server_id
                changed = True
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
                self.db.execute(cmd)
            else:
                self.logger.debug("in update_nic_info(), No Update for NIC information from Server "+ server_id)

        elif len(out) is 0:
            # Interfaces is new
            self.logger.debug("in update_nic_info(), Input new tuple into interface table: %s %s %s %s %s %s %s"
                              % (interface_id, server_id, nic_id, net_id, interface_name, ip_address, mac_address))

            #for i in server_id, nic_id, interface_name, ip_address, mac_address, net_id, interface_id:
            cmd = "Insert into " \
                  "interface (interface_id, server_id, nic_id, net_id, interface_name, ip_address, mac_address) " \
                  "VALUES " \
                  + "(\""+str(interface_id)+"\", \""+str(server_id)+"\", \""+str(nic_id)+"\", \""+str(net_id)+"\", \""\
                        +str(interface_id)+"\", \""+ip_address+"\", \""+mac_address + "\")"

            self.logger.debug("in update_nic_info(), Input Query: " + cmd)
            self.db.execute(cmd)

    def get_nic_spec_id(self, __model, __vendor):
        if __model == 'NULL':
            return None

        nic_id = None

        cmd = 'select nic_id from nic_spec where model = \"' + __model +"\""
        self.logger.debug("in get_nic_spec_id(), DB Query: " + cmd)
        self.db.execute(cmd)
        out = self.db.fetchallDict()
        self.logger.debug("in get_nic_spec_id(), " + "Query output: " + out.__str__())

        if len(out) is 0:
            # The NIC Model is not exist
            cmd = "insert into nic_spec(model, vendor) values (\"" + __model+"\", \"" + __vendor + "\")"
            self.logger.debug("in get_nic_spec_id(), NIC Model is not exist. Add new nic_model: " + cmd)
            self.db.execute(cmd)

            cmd = 'select nic_id from nic_spec'
            self.logger.debug("in get_nic_spec_id(), DB Query to list all nic_spec: " + cmd)
            self.db.execute(cmd)
            out = self.db.fetchallDict()
            self.logger.debug("in get_nic_spec_id(), all nic_spec list: " + out.__str__())

            cmd = 'select nic_id from nic_spec where model = \"' + __model + "\""
            self.logger.debug("in get_nic_spec_id(), DB Query: " + cmd)
            self.db.execute(cmd)
            out = self.db.fetchallDict()
            self.logger.debug("in get_nic_spec_id(), " + "Query output: " + out.__str__())
            nic_id = out[0]['nic_id']
            self.logger.debug("in get_nic_spec_id(), " + "nic_id :" + str(nic_id))
        else:
            # The NIC Model is exist
            nic_id = int(''.join(d for d in out[0]['nic_id'].__str__() if d.isdigit()))
            self.logger.debug("in get_nic_spec_id(), NIC Model is exist" + __model + ' nic_id: ' + str(nic_id))

        return nic_id

    def get_net_id(self, __net_addr):
        if __net_addr == 'NULL':
            return 'NULL'

        net_id = 'NULL'
        """
        cmd = 'select net_id from network where net_address = \"' + __net_addr.split('/')[0] +'\"'
        self.logger.debug("in get_net_id(), DB Query: " + cmd)
        self.db.execute(cmd)
        out = self.db.fetchallDict()
        """

        cmd = 'select net_id, net_address, net_subnet from network'
        self.db.execute(cmd)
        out = self.db.fetchallDict()

        mask = __net_addr.split('/')[1]
        nic_ip = ipaddress.IPv4Address(__net_addr.split('/')[0])

        for net in out:
            net_ip = ipaddress.IPv4Network(net['net_address']+"/"+str(net['net_subnet']))
            if nic_ip in net_ip:
                net_id = net['net_id']
                break

        if net_id == 'NULL':
            # network is not exist
            net_addr = ipaddress.IPv4Interface(__net_addr).network.__str__().split("/")[0]
            cmd = "insert into network (net_address, net_subnet) values (\"" + net_addr + "\",\"" + mask +"\")"
            self.logger.debug("in get_net_id(), Insert new network DB Query: " + cmd)
            self.db.execute(cmd)

            cmd = "select net_id from network where net_address = \"" + net_addr + "\""
            self.logger.debug("in get_net_id(), Insert new network DB Query: " + cmd)
            out = self.db.fetchallDict()
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
server_pt = "17777"
db_ip = "127.0.0.1"
db_user = "dbprj"
db_password = 'dbprj'
db_name = 'dbprj'

nicmon = NICMonServer(db_ip, db_user, db_password, db_name)

# REST API Part
app = Flask(__name__)


@app.route("/server/<string:server_id>/nic", methods=['POST'])
def create_nic_tuple(server_id):
    return nicmon.update_info(server_id, request.data)

app.run(port=server_pt)



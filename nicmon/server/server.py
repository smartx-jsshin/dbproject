import os
import subprocess
import shlex
from flask import Flask, request
import MySQLdb
import logging
import json


class NICMonServer:
    def __init__(self, __db_ip, __user, __password, __dbname):
        self.db = None
        self.logger = None

        self.init_logger()
        # self.init_db(__db_ip, __user, __password, __dbname)

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
                                  db=__dbname)

    def update_nic_info(self, __server_id, __nic_info):
        try:
            nic_info = json.loads(__nic_info)
        except ValueError, e:
            self.logger.error(e.message)
            return "Json Format is not Valid: (" + e.message + ")"

        self.logger.debug("Received Information: ")
        self.logger.debug(nic_info)
        # Parser

        return "Updated Successfully"

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
db_user = "netcs"
db_password = 'dbtest'
db_name = 'dbtest'

nicmon = NICMonServer(db_ip, db_user, db_password, db_name)

# REST API Part
app = Flask(__name__)


@app.route("/server/<string:server_id>/nic", methods=['POST'])
def create_nic_tuple(server_id):
    return nicmon.update_nic_info(server_id, request.data)

app.run(port=server_pt)



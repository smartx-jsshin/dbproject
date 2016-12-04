import os
import subprocess
import shlex

import httplib2
import logging
import json
import yaml
import time

class NICMonCollector:
    def __init__(self, __id, __server_ip, __server_pt):
        self.id = __id
        self.server_ip = __server_ip
        self.server_port = __server_pt

        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(logging.DEBUG)
        fm = logging.Formatter('%(name)-12s: %(levelname)-8s %(message)s')
        ch = logging.StreamHandler()
        ch.setLevel(logging.DEBUG)
        ch.setFormatter(fm)
        self.logger.addHandler(ch)

    def shell_command(self, __cmd):
        self.logger.debug("Shell command: " + __cmd.__str__())
        if isinstance(__cmd, basestring):
            subproc = subprocess.Popen(shlex.split(__cmd),
                                       stdout=subprocess.PIPE,
                                       stderr=subprocess.PIPE)
        elif isinstance(__cmd, list):
            subproc = subprocess.Popen(__cmd, stdout=subprocess.PIPE,
                                       stderr=subprocess.PIPE)
        (cmdout, cmderr) = subproc.communicate()
        return subproc.returncode, cmdout, cmderr

    def get_nic_list(self):
        cmd = ['ls', '-l', '/sys/class/net']
        output = self.shell_command(cmd)

        vnic_list = list()
        pnic_list = list()

        for i in output[1].split('\n'):
            j = i.split(' ')[-1]
            if "devices" in j.split('/'):
                if "virtual" in j.split('/'):
                    vnic_list.append(j.split('/')[-1])
                else:
                    pnic_list.append(j.split('/')[-1])
            else:
                continue

        self.logger.debug("Physical NIC list: " + pnic_list.__str__())
        self.logger.debug("Virtual NIC list: " + vnic_list.__str__())
        return pnic_list, vnic_list

    def collect_nic(self):
        p, v = self.get_nic_list()

        pnic_list = self.create_nic_info(p, True)
        vnic_list = self.create_nic_info(v, False)

        nic_list = pnic_list + vnic_list

        # Report to Server by HTTP Message
        if len(nic_list) is not 0:
            http = httplib2.Http()
            url = "http://"+self.server_ip+":"+self.server_port+"/server/"+str(self.id)+"/nic"
            self.logger.debug(url)
            http.request(url, body=json.dumps(nic_list), method='POST')

    def create_nic_info(self, __nic_list, __is_physical):
        nic_list = list()

        for nic_name in __nic_list:
            cmd = ['ip', 'addr', 'show', 'dev', nic_name]
            out = self.shell_command(cmd)[1]

            nic_info = dict()
            inet_info = dict()
            ether_info = dict()

            for i in out.split('\n'):
                t = i.strip().split(' ')
                if 'inet6' not in t and 'inet' in t:
                    inet_info['ipaddr'] = t[1]
                    break
            if len(inet_info) is 0:
                inet_info['ipaddr'] = 'NULL'

            for i in out.split('\n'):
                t = i.strip().split(' ')
                if 'link/ether' in t:
                    ether_info['macaddr'] = t[1]
            if len(ether_info) is 0:
                ether_info['macaddr'] = 'NULL'

            for i in out.split('\n'):
                t = i.strip().split(' ')
                if 'state' in t:
                    idx = t.index('state') + 1
                    nic_info['status'] = t[idx]

            nic_info['name'] = nic_name
            nic_info['inet'] = inet_info
            nic_info['ether'] = ether_info

            if __is_physical:
                nic_info['type'] = "physical"
                model, vendor = self.get_pnic_model(nic_name)
                nic_info['model'] = model
                nic_info['vendor'] = vendor
            elif not __is_physical:
                nic_info['type'] = "virtual"
                nic_info['model'] = self.get_vnic_model(nic_name)
                nic_info['vendor'] = 'NULL'

            if not nic_info['model']:
                nic_info['model'] = 'NULL'

            nic_list.append(nic_info)

        return nic_list

    def get_pnic_model(self, __nic_name):
        cmd1 = ['lshw', '-c', 'network']
        cmd2 = ['grep', __nic_name, '-A', '10', '-B', '7']

        subproc1 = subprocess.Popen(cmd1,
                                    stdout=subprocess.PIPE,
                                    stderr=subprocess.PIPE)

        subproc2 = subprocess.Popen(cmd2,
                                    stdin=subproc1.stdout,
                                    stdout=subprocess.PIPE,
                                    stderr=subprocess.PIPE)

        output = subproc2.communicate()

        nic_model = None
        nic_vendor = None
        for i in output[0].split('\n'):
            if "product" in i:
                nic_model = i.split(":")[1].strip()
            elif "vendor" in i:
                nic_vendor = i.split(":")[1].strip()

        self.logger.debug("NIC Model for "+__nic_name+": "+nic_model)
        return nic_model, nic_vendor

    def get_vnic_model(self, __nic_name):
        cmd = ['ethtool', '-i', __nic_name]
        out = self.shell_command(cmd)

        nic_model = 'NULL'
        for i in out[1].split('\n'):
            if "driver" in i:
                nic_model = i.split(':')[1].strip()
                self.logger.debug("NIC Model for " + __nic_name + ": " + nic_model)
                break
        return nic_model

if __name__ == "__main__":
    fp = os.path.join(os.getcwd(), 'collector_config.yaml')
    if os.path.exists(fp):
        o = open(fp, mode='r').read(-1)
        d = yaml.load(o)

        host_id = d['host_id']
        server_ip = d['server_ipaddress']
        server_pt = d['server_port']
        collect_cycle = d['collect_cycle']
        collector = NICMonCollector(host_id, server_ip, server_pt)

        while True:
            collector.collect_nic()
            time.sleep(collect_cycle)

    else:
        print "Configuration file is not found: collector_config.yaml"
        exit(1)

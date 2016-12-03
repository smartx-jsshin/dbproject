import subprocess
import shlex

import httplib2
import logging
import json

class NICMonCollector:
    def __init__(self):
        self.server_ip = '127.0.0.1'
        self.server_port = '17777'

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

    def collect(self):
        p, v = self.get_nic_list()

        pnic_list = self.create_nic_info(p, True)
        vnic_list = self.create_nic_info(v, False)

        nic_list = pnic_list + vnic_list
        print nic_list

        # Report to Server by HTTP Message
        http = httplib2.Http()
        url = "http://"+self.server_ip+":"+self.server_port+"/server/nic"
        self.logger.debug(url)
        http.request(url, body=json.dumps(nic_list), method='POST')

    def create_nic_info(self, __nic_list, __is_physical):
        nic_list = list()

        for nic_name in __nic_list:
            cmd = ['ip', 'addr', 'show', 'dev', nic_name]
            out = self.shell_command(cmd)[1]

            nic_info = dict()
            inet_info = dict()

            for i in out.split('\n'):
                t = i.strip().split(' ')
                if 'inet6' not in t and 'inet' in t:
                    inet_info['ipaddr'] = t[1]
                    inet_info['subnet'] = t[3]

            nic_info['name'] = nic_name
            nic_info['inet'] = inet_info

            if __is_physical:
                nic_info['type'] = "physical"
            elif not __is_physical:
                nic_info['type'] = "virtual"

            nic_list.append(nic_info)

        return nic_list

if __name__ == "__main__":
    collector = NICMonCollector()
    collector.collect()

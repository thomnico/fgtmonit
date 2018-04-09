#!/usr/bin/env python
#License upload using FORTIOSAPI from Github

"""
A collector for Fortinet Fortigate 

#### Dependencies

 * fortiosapi (on pypi)

#### Configuring FortigateCollector

The configuration format is as follow:
        # Options for FortigatesCollector
        path = fortinet
        interval = 9

        [devices]

        [[fgt1]]
        hostname = 10.10.10.125
        user = admin
        password = toto
        vdom = root
        https = true

        [[router2]]
        hostname = 10.10.10.74
        user = admin
        password =
        vdom = root
        https = false

Allowing to monitor multiple fortigate devices

For testing collectors etc refer to the example collector documentation.

Diamond looks for collectors in /usr/lib/diamond/collectors/ (on Ubuntu). By
default diamond will invoke the *collect* method every 60 seconds.

Diamond collectors that require a separate configuration file should place a
.cfg file in /etc/diamond/collectors/.
The configuration file name should match the name of the diamond collector
class.  For example, a collector called
*FortigateCollector.FortigateCollector* could have its configuration file placed in
/etc/diamond/collectors/FortigateCollector.cfg.

"""

import logging
from packaging.version import Version

import yaml
import sys
import os

from logging.handlers import SysLogHandler
import time
from service import find_syslog, Service

try:
    from fortiosapi import FortiOSAPI
    fortiosapi = "present"
    # define a variable to avoid stacktraces
except ImportError:
    fortiosapi = None

#formatter = logging.Formatter(
#    '%(asctime)s %(name)-12s %(levelname)-8s %(message)s')
#logger = logging.getLogger('fortiosapi')
#hdlr = logging.FileHandler('fortigatecollector.log')
#hdlr.setFormatter(formatter)
#logger.addHandler(hdlr)
#logger.setLevel(logging.DEBUG)
fortigateList = []

class MyService(Service):
    def __init__(self, *args, **kwargs):
        super(MyService, self).__init__(*args, **kwargs)
        self.logger.addHandler(SysLogHandler(address=find_syslog(),
                               facility=SysLogHandler.LOG_DAEMON))
        self.logger.setLevel(logging.INFO)
        self.fortigateList = []
        self.conf = yaml

    def configload(self):
        # fortigateList is a list of fortiosAPI object to ease the parsing and keep the session up
        # Change in yaml format the configfile
        conffile = os.getenv('FGTMONIT_CONF_FILE', "fgtmonit.yaml")
        self.conf = yaml.load(open(conffile, 'r'))
        if fortiosapi is None:
            self.logger.error("Unable to import fortiosapi python module")
            exit(2)
        # config is now a list that we map to fortigateList list of objects.

        #Brutal option logout all and reconstruct
        for fgt in fortigateList:
            self.logger.info("Logout from %s", fgt)
            fgt.logout()
            fortigateList.remove(fgt)
        self.logger.info("FortigateList should be empty is %s", fortigateList)

        for fgtc in self.conf:
            print(self.conf[fgtc]['hostname'])
            self.logger.info("device : %s", self.conf[fgtc])
            # create a FortiosAPI objects in the list:
            fortigateList.append(FortiOSAPI())
            if self.conf[fgtc]['https'] == 'false':
                fortigateList[-1].https('off')
            else:
                fortigateList[-1].https('on')
            try:
                fortigateList[-1].login(self.conf[fgtc]['hostname'],
                                    self.conf[fgtc]['user'],
                                    self.conf[fgtc]['password'])
                self.logger.info("Login successfull for : %s", self.conf[fgtc]['hostname'])
            except:
                # if failing login remove from list.
                fortigateList.remove(fortigateList[-1])
            # Log
        self.logger.info("FortigateList is %s", fortigateList)

# will need to do a much more complex service to be able to call a change on the running deamon
# #keep it simple for now
#    def reload(self):
#        pid = self.get_pid()
#        if pid:
#            self.configload()
#

    def publish(self, host, name, metric):
        self.logger.info("host: %s", host)
        for c in self.conf:
            if self.conf[c]['hostname'] == host:
                fgtid = c
        self.logger.info("host: %s, name %s: metric : %s", fgtid, name, metric)


    def run(self):

        while not self.got_sigterm():
            self.logger.info("Collecting from %s", fortigateList)
            for fgt in fortigateList:
                metrics = fgt.monitor('system', 'vdom-resource',
                                      mkey='select', vdom='root')['results']
                # TODO allow different vdom per devices
                self.logger.debug("rest api collected is %s", metrics)
                # try to change the hostname in the output

                self.publish(fgt.host,"cpu", metrics['cpu'])
                self.publish(fgt.host,"memory", metrics['memory'])
                self.publish(fgt.host,"setup_rate", metrics['setup_rate'])
                if Version(fgt.get_version()) > Version('5.6'):
                    self.publish(fgt.host,"sessions", metrics['session']['current_usage'])
                else:
                    self.publish(fgt.host,"sessions", metrics['sessions'])
            self.logger.info("resting")
            time.sleep(3)

if __name__ == '__main__':

    if len(sys.argv) != 2:
        sys.exit('Syntax: %s COMMAND' % sys.argv[0])

    cmd = sys.argv[1].lower()
    service = MyService('my_service', pid_dir='/tmp')

    if cmd == 'start':
        service.configload()
        service.start()
    elif cmd == 'stop':
        service.stop()
    elif cmd == 'restart':
        try:
            service.stop()
        except:
            pass
        while service.is_running():
            time.sleep(0.2)
        service.configload()
        service.start()
    elif cmd == 'status':
        if service.is_running():
            print "Service is running."
        else:
            print "Service is not running."
    else:
        sys.exit('Unknown command "%s".' % cmd)


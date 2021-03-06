#!/usr/bin/env python

'''Resource Agent Tester

ScenarioComponent utilities and base classes, extends Pacemaker's CTS
 '''

__copyright__ = '''
Copyright (C) 2015-2016 Damien Ciabrini <dciabrin@redhat.com>
Licensed under the GNU GPL.
'''

#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 3
# of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301  USA.


import sys, signal, time, os, re, string, subprocess, tempfile
from stat import *
from cts import CTS
from cts.CTStests import CTSTest
from cts.CM_ais import crm_mcp
from cts.CTSscenarios import *
from cts.CTSaudits import *
from cts.CTSvars   import *
from cts.patterns  import PatternSelector
from cts.logging   import LogFactory
from cts.remote    import RemoteFactory
from cts.watcher   import LogWatcher
from cts.environment import EnvFactory
from racts.rapatterns import RATemplates

class RATesterScenarioComponent(ScenarioComponent):
    '''Assertion-friendly base class for scenario setup/teardown.
    '''
    def __init__(self, environment, verbose=True):
        self.rsh = RemoteFactory().getInstance()
        self.logger = LogFactory()
        self.Env = environment
        self.verbose = verbose
        self.ratemplates = RATemplates()

    def node_fqdn(self, node):
        return self.rsh(node, "getent ahosts %s | awk '/STREAM/ {print $3}'"%node, stdout=1).strip()

    def copy_to_nodes(self, files, create_dir=False, owner=False, perm=False, template=False):
        for node in self.Env["nodes"]:
            for localfile,remotefile in files:
                if create_dir:
                    remotedir=os.path.dirname(remotefile)
                    rc = self.rsh(node, "mkdir -p %s" % remotedir)
                    assert rc == 0, "create dir \"%s\" on remote node \"%s\"" % (remotedir, node)
                src = os.path.join(os.path.dirname(os.path.abspath(__file__)), localfile)
                with tempfile.NamedTemporaryFile() as tmp:
                    if template:
                        with open(src,"r") as f: template=f.read()
                        tmp.write(template.replace("{{node}}",self.node_fqdn(node)))
                        tmp.flush()
                        cpsrc=tmp.name
                    else:
                        cpsrc=src
                    rc = self.rsh.cp(cpsrc, "root@%s:%s" % (node, remotefile))
                    assert rc == 0, "copy test data \"%s\" on remote node \"%s\"" % (src, node)
                    if owner:
                        rc = self.rsh(node, "chown %s %s" % (owner, remotefile))
                        assert rc == 0, "change ownership of \"%s\" on remote node \"%s\"" % (src, node)
                    if perm:
                        rc = self.rsh(node, "chmod %s %s" % (perm, remotefile))
                        assert rc == 0, "change permission of \"%s\" on remote node \"%s\"" % (src, node)

    def get_candidate_path(self, candidates, is_dir=False):
        testopt = "-f" if is_dir is False else "-d"
        target = False
        for candidate in candidates:
            if self.rsh(self.Env["nodes"][0], "test %s %s"%(testopt, candidate)) == 0:
                return candidate
        assert target

    def IsApplicable(self):
        return 1

    def SetUp(self, cluster_manager):
        try:
            self.setup_scenario(cluster_manager)
            return 1
        except AssertionError as e:
            print("Setup of scenario %s failed: %s"%\
                  (self.__class__.__name__,str(e)))
        return 0

    def TearDown(self, cluster_manager):
        try:
            self.teardown_scenario(cluster_manager)
            return 1
        except AssertionError as e:
            print("Teardown of scenario %s failed: %s"%\
                  (self.__class__.__name__,str(e)))
        return 0

    def log(self, args):
        self.logger.log(args)

    def debug(self, args):
        self.logger.debug(args)

    def rsh_check(self, target, command, expected = 0):
        if self.verbose: self.log("> [%s] %s"%(target,command))
        res=self.rsh(target, command+" &>/dev/null")
        assert res == expected, "\"%s\" returned %d"%(command,res)

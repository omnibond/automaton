# Copyright 2017
#
# Licensed under the Apache License, Version 2.0, <LICENSE-APACHE or
# http://apache.org/licenses/LICENSE-2.0> or the MIT license <LICENSE-MIT or
# http://opensource.org/licenses/MIT> or the LGPL, Version 2.0 <LICENSE-LGPLv2 or
# https://www.gnu.org/licenses/old-licenses/lgpl-2.0.txt>, at your option.
# This file may not be copied, modified, or distributed except according to those terms.


import sys
import os

from scheduler import Scheduler

sys.path.append(os.path.join(os.path.dirname(__file__), '..'))


class Torque(Scheduler):

    def __init__(self, **kwargs):
        super(Torque, self).__init__(**kwargs)

    def generateParentJobScriptHeader(self, numNodes, numCores, wallTime):
        jobScriptHeader= """#!/bin/bash\n#PBS -l nodes=""" + str(numNodes) + """:ppn=""" + str(numCores) + """\n#PBS -l walltime=""" + str(wallTime) + """\n"""
        return {"status": "success", "payload": jobScriptHeader}

    def generateChildJobScriptHeader(self, numNodes, numCores, wallTime, jobPrefixString):
        jobScriptHeader = "#!/bin/bash\n#PBS -l nodes=" + str(numNodes) + ":ppn=" + str(numCores) + "\n#PBS -l walltime=" + str(wallTime) + "\n"
        return {"status": "success", "payload": jobScriptHeader}

    def getCommands(self):
       return {"status": "success", "payload": {"submit": "qsub", "cancel": "qdel", "monitor": "qstat"}}

    def checkExperimentJobCompletion(self):
        return {"status": "error", "payload": "checkExperimentJobCompletion not implemented for " + str(self.schedType) + "."}

    def submitJob(self, **kwargs):
        return {"status": "error", "payload": "submitJob not implemented for " + str(self.schedType) + "."}

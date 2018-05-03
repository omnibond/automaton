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


class Slurm(Scheduler):

    def __init__(self, **kwargs):
        super(Slurm, self).__init__(**kwargs)

    def generateParentJobScriptHeader(self, numNodes, numCores, wallTime):
        # For the moment take out the -N because spot fleet we don't know how many we will have.
        # Also remove the --ntasks-per-node since we won't know how many the first instance to come up has.
        #jobScriptHeader = """#!/bin/bash\n#SBATCH -N """ + str(numNodes) + """\n#SBATCH --ntasks-per-node """ + str(numCores) + """\n#SBATCH --time=""" + str(wallTime) + """\n"""
        jobScriptHeader = """#!/bin/bash\n#SBATCH --time=""" + str(wallTime) + """\n"""
        return {"status": "success", "payload": jobScriptHeader}

    def generateChildJobScriptHeader(self, numNodes, numCores, wallTime, jobPrefixString, sharedFilesystemPath):
        # For the moment take out the --n-tasks-per-node because we don't know how many cores will be on each machine.
        # But we do know that each job gets one node so for now just leave it at that.
        #jobScriptHeader = "#!/bin/bash\n#SBATCH -N " + str(numNodes) + "\n#SBATCH --ntasks-per-node " + str(numCores) + "\n#SBATCH --job-name=" + str(jobPrefixString) + "\n#SBATCH --time=" + str(wallTime) + "\n#SBATCH -D " + str(sharedFilesystemPath)
        jobScriptHeader = "#!/bin/bash\n#SBATCH -N " + str(numNodes) + "\n#SBATCH --job-name=" + str(jobPrefixString) + "\n#SBATCH --time=" + str(wallTime) + "\n#SBATCH -D " + str(sharedFilesystemPath)
        return {"status": "success", "payload": jobScriptHeader}

    def checkExperimentJobCompletion(self, verboseOutput, jobPrefixString):
        stillRunning = 0
        lineNum = 0
        for line in verboseOutput.split("\n"):
            lineNum += 1
            if "JOBID" not in line and str(jobPrefixString) in line:
                stillRunning += 1
        print "STILL RUNNING: " + str(stillRunning)
        if stillRunning == 0:
            return {"status": "success", "payload": True}
        else:
            return {"status": "success", "payload": False}

    def getCommands(self):
        return {"status": "success", "payload": {"submit": "sbatch", "cancel": "scancel", "monitor": "squeue"}}

    def submitJob(self):
        return {"status": "error", "payload": "submitJob not implemented for " + str(self.schedType) + "."}

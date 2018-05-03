# Copyright 2017
#
# Licensed under the Apache License, Version 2.0, <LICENSE-APACHE or
# http://apache.org/licenses/LICENSE-2.0> or the MIT license <LICENSE-MIT or
# http://opensource.org/licenses/MIT> or the LGPL, Version 2.0 <LICENSE-LGPLv2 or
# https://www.gnu.org/licenses/old-licenses/lgpl-2.0.txt>, at your option.
# This file may not be copied, modified, or distributed except according to those terms.


class Scheduler(object):

    def __init__(self, schedType):
        self.schedType = schedType

        # Placeholder for API Key that can be used to submit things to the scheduler
        self.apiKey = None

    def generateParentJobScriptHeader(self, **kwargs):
        return {"status": "error", "payload": "Base Scheduler Class method generateParentJobScriptHeader not implemented for " + str(self.schedType) + "."}

    def generateChildJobScriptHeader(self, **kwargs):
        return {"status": "error", "payload": "Base Scheduler Class method generateChildJobScriptHeader not implemented for " + str(self.schedType) + "."}

    def getCommands(self, **kwargs):
        return {"status": "error", "payload": "Base Scheduler Class method getCommands not implemented for " + str(self.schedType) + "."}

    def checkExperimentJobCompletion(self, **kwargs):
        return {"status": "error", "payload": "Base Scheduler Class method checkExperimentJobCompletion not implemented for " + str(self.schedType) + "."}

    def submitJob(self, **kwargs):
        return {"status": "error", "payload": "Base Scheduler Class method submitJob not implemented for " + str(self.schedType) + "."}

    def getJobStatus(self, **kwargs):
        return {"status": "error", "payload": "Base Scheduler Class method getJobStatus not implemented for " + str(self.schedType) + "."}

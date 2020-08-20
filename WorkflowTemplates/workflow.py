# Copyright 2017
#
# Licensed under the Apache License, Version 2.0, <LICENSE-APACHE or
# http://apache.org/licenses/LICENSE-2.0> or the MIT license <LICENSE-MIT or
# http://opensource.org/licenses/MIT> or the LGPL, Version 2.0 <LICENSE-LGPLv2 or
# https://www.gnu.org/licenses/old-licenses/lgpl-2.0.txt>, at your option.
# This file may not be copied, modified, or distributed except according to those terms.


class Workflow(object):
    def __init__(self, name, wfType, options, schedulerType, environment, scheduler=None, ccq=None):
        self.name = name
        self.wfType = wfType
        self.options = options
        self.schedulerType = schedulerType
        self.environment = environment
        self.scheduler = scheduler
        self.ccq = ccq

    def run(self, **kwargs):
        return {"status": "error", "payload": "Base Workflow Class method run not implemented for " + str(self.wfType) + "."}

    def monitor(self, **kwargs):
        return {"status": "error", "payload": "Base Workflow Class method monitor not implemented for " + str(self.wfType) + "."}

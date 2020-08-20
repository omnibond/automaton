# Copyright 2017
#
# Licensed under the Apache License, Version 2.0, <LICENSE-APACHE or
# http://apache.org/licenses/LICENSE-2.0> or the MIT license <LICENSE-MIT or
# http://opensource.org/licenses/MIT> or the LGPL, Version 2.0 <LICENSE-LGPLv2 or
# https://www.gnu.org/licenses/old-licenses/lgpl-2.0.txt>, at your option.
# This file may not be copied, modified, or distributed except according to those terms.


class Resource(object):
    def __init__(self, cloudType, region, profile="default"):
        self.cloudType = cloudType
        self.region = region
        self.profile = profile

    def createControlResources(self, **kwargs):
        return {"status": "error", "payload": "Base Resource Class method createControlResources not implemented for " + str(self.cloudType) + "."}

    def deleteControlResources(self, **kwargs):
        return {"status": "error", "payload": "Base Resource Class method deleteControlResources not implemented for " + str(self.cloudType) + "."}

    def monitorControlResources(self, **kwargs):
        return {"status": "error", "payload": "Base Resource Class method monitorControlResources not implemented for " + str(self.cloudType) + "."}

    def getValue(self, **kwargs):
        return {"status": "error", "payload": "Base Resource Class method getValue not implemented for " + str(self.cloudType) + "."}

    def writeObjectsToDatabase(self, **kwargs):
        return {"status": "error", "payload": "Base Resource Class method writeObjectsToDatabase not implemented for " + str(self.cloudType) + "."}

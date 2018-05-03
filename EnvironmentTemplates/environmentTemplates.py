# Copyright 2017
#
# Licensed under the Apache License, Version 2.0, <LICENSE-APACHE or
# http://apache.org/licenses/LICENSE-2.0> or the MIT license <LICENSE-MIT or
# http://opensource.org/licenses/MIT> or the LGPL, Version 2.0 <LICENSE-LGPLv2 or
# https://www.gnu.org/licenses/old-licenses/lgpl-2.0.txt>, at your option.
# This file may not be copied, modified, or distributed except according to those terms.


class EnvironmentTemplate(object):
    def __init__(self, environmentType, parameters, templateName):
        self.environmentType = environmentType
        self.parameters = parameters
        self.templateName = templateName
        self.template = None

    def get(self, **kwargs):
        return {"status": "error", "payload": "Base EnvironmentTemplate Class method get not implemented for " + str(self.environmentType) + "."}

    def create(self, **kwargs):
        return {"status": "error", "payload": "Base EnvironmentTemplate Class method create not implemented for " + str(self.environmentType) + "."}

    def delete(self, **kwargs):
        return {"status": "error", "payload": "Base EnvironmentTemplate Class method delete not implemented for " + str(self.environmentType) + "."}

    def populate(self, **kwargs):
        return {"status": "error", "payload": "Base EnvironmentTemplate Class method populate not implemented for " + str(self.environmentType) + "."}

    def listTemplates(self, **kwargs):
        return {"status": "error", "payload": "Base EnvironmentTemplate Class method listTemplates not implemented for " + str(self.environmentType) + "."}

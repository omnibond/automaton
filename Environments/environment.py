# Copyright 2017
#
# Licensed under the Apache License, Version 2.0, <LICENSE-APACHE or
# http://apache.org/licenses/LICENSE-2.0> or the MIT license <LICENSE-MIT or
# http://opensource.org/licenses/MIT> or the LGPL, Version 2.0 <LICENSE-LGPLv2 or
# https://www.gnu.org/licenses/old-licenses/lgpl-2.0.txt>, at your option.
# This file may not be copied, modified, or distributed except according to those terms.


import traceback


class Environment(object):
    def __init__(self, environmentType, name, cloudType, userName, password, controlParameters, ccEnvironmentParameters, generalParameters, firstName, lastName, pempath, dnsName=None, controlResourceName=None, region=None, profile=None):
        self.environmentType = environmentType
        self.name = name
        self.cloudType = cloudType
        self.userName = userName
        self.password = password
        self.firstName = firstName
        self.lastName = lastName
        self.pempath = pempath
        self.controlParameters = controlParameters
        self.ccEnvironmentParameters = ccEnvironmentParameters
        self.generalParameters = generalParameters

        # We initially define these parameters as None because we haven't created the Control Resources for them. As we create the resources we define these variables for later use.
        self.sessionCookies = None
        self.dnsName = dnsName
        self.controlResourceName = controlResourceName
        self.region = region
        self.profile = profile

        # Define which scheduler types are valid for a particular environment
        #self.supportedSchedulers = []

    def createResourceClass(self, region=None, profile=None):
        try:
            environmentClass = __import__(str(self.cloudType).lower() + "Resources")
            # Get the actual class that we need to instantiate (ex: from cloudycluster import CloudyCluster)
            myClass = getattr(environmentClass, self.cloudType[0].upper() + self.cloudType[1:] + "Resources")
            if profile is not None:
                kwargs = {"cloudType": self.cloudType, "region": region, "profile": profile}
            else:
                kwargs = {"cloudType": self.cloudType, "region": region}
            # Instantiate the class with the required parameters
            resourceClass = myClass(**kwargs)
            #print "resourceClass is "+str(resourceClass)
            return {'status': "success", "payload": resourceClass}
        except Exception as e:
            return {"status": "error", "payload": {"error": "Unable to create an instance of the resource class for the cloudType: " + str(self.cloudType) + ". Please make sure the cloudType is specified properly.", "traceback": ''.join(traceback.format_exc())}}

    def createSchedulerClass(self, schedulerType=None):
        try:
            if schedulerType is None:
                return {"status": "error", "payload": {"error":"Unable to create an instance of the Scheduler class because the scheduler type is not specified. Please make sure the schedulerType field is specified properly.", "traceback": ''.join(traceback.format_stack())}}
            schedulerModule = __import__(str(schedulerType).lower())
            # Get the actual class that we need to instantiate (ex: from cloudycluster import CloudyCluster)
            schedulerClass = getattr(schedulerModule, str(schedulerType[0].upper() + schedulerType[1:]))
            kwargs = {"schedType": schedulerType}
            scheduler = schedulerClass(**kwargs)
            return {'status': "success", "payload": scheduler}
        except Exception as e:
            return {"status": "error", "payload": {"error": "Encountered an error attempting to create an instance of the Scheduler class.", "traceback": ''.join(traceback.format_exc())}}

    def getSession(self):
        return {"status": "error", "payload": "Base Environment Class method getSession not implemented for " + str(self.environmentType) + "."}

    def createControl(self, **kwargs):
        return {"status": "error", "payload": "Base Environment Class method createControl not implemented for " + str(self.environmentType) + "."}

    def createEnvironment(self, **kwargs):
        return {"status": "error", "payload": "Base Environment Class method createEnvironment not implemented for " + str(self.environmentType) + "."}

    def deleteControl(self, **kwargs):
        return {"status": "error", "payload": "Base Environment Class method deleteControl not implemented for " + str(self.environmentType) + "."}

    def deleteEnvironment(self, **kwargs):
        return {"status": "error", "payload": "Base Environment Class method deleteEnvironment not implemented for " + str(self.environmentType) + "."}

    def checkState(self, **kwargs):
        return {"status": "error", "payload": "Base Environment Class method checkState not implemented for " + str(self.environmentType) + "."}

    def changeState(self, **kwargs):
        return {"status": "error", "payload": "Base Environment Class method changeState not implemented for " + str(self.environmentType) + "."}

    def getApiKey(self, **kwargs):
        return {"status": "error", "payload": "Base Environment Class method getApiKey not implemented for " + str(self.environmentType) + "."}

    def genApiKey(self, **kwargs):
        return {"status": "error", "payload": "Base Environment Class method genApiKey not implemented for " + str(self.environmentType) + "."}

    def submitJob(self, **kwargs):
        return {"status": "error", "payload": "Base Environment Class method submitJob not implemented for " + str(self.environmentType) + "."}

    def monitorJob(self, **kwargs):
        return {"status": "error", "payload": "Base Environment Class method monitorJob not implemented for " + str(self.environmentType) + "."}

    def getJobSubmitDns(self, **kwargs):
        return {"status": "error", "payload": "Base Environment Class method getJobSubmitDns not implemented for " + str(self.environmentType) + "."}

    def getControlDns(self, **kwargs):
        return {"status": "error", "payload": "Base Environment Class method getControlDns not implemented for " + str(self.environmentType) + "."}

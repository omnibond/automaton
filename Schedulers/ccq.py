# Copyright 2017
#
# Licensed under the Apache License, Version 2.0, <LICENSE-APACHE or
# http://apache.org/licenses/LICENSE-2.0> or the MIT license <LICENSE-MIT or
# http://opensource.org/licenses/MIT> or the LGPL, Version 2.0 <LICENSE-LGPLv2 or
# https://www.gnu.org/licenses/old-licenses/lgpl-2.0.txt>, at your option.
# This file may not be copied, modified, or distributed except according to those terms.


import sys
import os
import hashlib
import requests
import json
import traceback
import subprocess

from scheduler import Scheduler

sys.path.append(os.path.join(os.path.dirname(__file__), '..'))


class Ccq(Scheduler):

    def __init__(self, **kwargs):
        super(Ccq, self).__init__(**kwargs)

    def generateParentJobScriptHeader(self, numNodes, numCores, wallTime):
        print("Not yet implemented.")
        return {"status": "success", "payload": "Not yet implemented."}

    def generateChildJobScriptHeader(self, numNodes, numCores, wallTime, jobPrefixString):
        print("Not yet implemented.")
        return {"status": "success", "payload": "Not yet implemented."}

    def getCommands(self, **kwargs):
        return {"status": "success", "payload": {"submit": "ccqsub", "cancel": "ccqdel", "monitor": "ccqstat"}}

    def submitJob(self, sessionCookies, jobObj, ccAccessKey, loginDomainName):
        encodedUserName = ""
        encodedPassword = ""
        valKey = ""
        dateExpires = ""
        certLength = 1

        jobName = jobObj['jobName']
        jobScriptLocation = jobObj['jobScriptLocation']
        jobScriptText = jobObj['jobScriptText']
        ccOptionsParsed = jobObj['ccOptionsParsed']
        jobMD5Hash = jobObj['jobMD5Hash']

        final = {"jobScriptLocation": str(jobScriptLocation), "jobScriptFile": str(jobScriptText), "jobName": str(jobName), "ccOptionsCommandLine": ccOptionsParsed, "jobMD5Hash": jobMD5Hash, "userName": str(encodedUserName), "password": str(encodedPassword), "valKey": str(valKey), "dateExpires": str(dateExpires), "certLength": str(certLength), "ccAccessKey": str(ccAccessKey), "remoteUserName": None}

        if loginDomainName is None:
            return {"status": "error", "payload": "There was a problem trying to get the Login Instance's DNS name that is required to submit the job."}
        else:
            ccqsubURL = "https://" + str(loginDomainName) + "/srv/ccqsub"
            results = requests.post(ccqsubURL, cookies=sessionCookies, json=final)

            jobOutput = json.loads(results.content)
            if jobOutput['status'] == "success":
                jobId = jobOutput['payload']['message'].split(":")[1][1:5]
                return {"status": "success", "payload": {"message": "The job has been successfully submitted to ccq.", "jobId": str(jobId)}}
            else:
                return {"status": "error", "payload": {"error": jobOutput['payload'], "traceback": ''.join(traceback.format_stack())}}

    def generateCcqSubmitParameters(self, environment, jobWorkDir, jobScriptText, options):
        # We have to build the object that the ccqsub utility would have built for us. This allows for the dynamic creation of the instances.
        # Set up the CCQ parameters required to submit the job.

        if str(environment.cloudType).lower() == "gcp":
            volumeType = "pd-standard"
        elif str(environment.cloudType).lower() == "aws":
            volumeType = "ssd"
        else:
            return {"status": "error", "payload": {"error": "Unable to determine the volume type for the environment type provided.", "traceback": ''.join(traceback.format_stack())}}

        ccOptionsParsed = {"numberOfInstancesRequested": "1",  "numCpusRequested": "1", "wallTimeRequested": "None", "stdoutFileLocation": "default", "stderrFileLocation": "default", "combineStderrAndStdout": "None", "copyEnvironment": "None", "eventNotification": "None", "mailingAddress": "None", "jobRerunable": "None", "memoryRequested": "1000", "accountToCharge": "None", "jobBeginTime": "None", "jobArrays": "None", "useSpot": "no", "spotPrice": "None", "requestedInstanceType": "default", "networkTypeRequested": "default", "optimizationChoice": "cost",  "pathToExecutable": "None", "criteriaPriority": "mcn", "schedulerToUse": "default", "schedType": "default", "volumeType": str(volumeType), "certLength": "1", "jobWorkDir": str(jobWorkDir), "justPrice": "false", "ccqHubSubmission": "False", "useSpotFleet": "False", "spotFleetWeights": "None", "spotFleetTotalSize": "None", "spotFleetType": "lowestPrice", "terminateInstantly": "False", "skipProvisioning": "False", "submitInstantly": "False", "timeLimit": "None", "createPInstances": "False", "image": "None", "maxIdle": "5", "placementGroupName": "None", "useGpu": "False", "gpuType": "None", "usePreemptible": "False", "cpuPlatform": "None", "maintain": "False"}

        for attribute in list(options.keys()):
            ccOptionsParsed[attribute] = str(options[attribute])

        if str(ccOptionsParsed['requestedInstanceType']) != "default":
            ccOptionsParsed['userSpecifiedInstanceType'] = "true"
        else:
            ccOptionsParsed['userSpecifiedInstanceType'] = "false"

        if str(ccOptionsParsed["spotPrice"]).lower() != "none":
            ccOptionsParsed['useSpot'] = "yes"

        # See if the user specified a GPU configuration and if so set the gcpgpu flag to True
        if str(ccOptionsParsed['gpuType']) != "None":
            ccOptionsParsed['useGpu'] = True

        # ccq generates an MD5 Hash to determine if the job has been ran before, we need to generate that here
        jobScriptTextTrimmed = ''.join(jobScriptText.split())
        #Calculate the MD5 hash for the job script:
        newJobScriptMD5Hash = hashlib.md5(jobScriptTextTrimmed).hexdigest()

        # Return the generated job text and the object we built
        return {"status": "success", "payload": {"ccOptionsParsed": ccOptionsParsed, "jobMD5Hash": newJobScriptMD5Hash}}

    def getOrGenerateApiKey(self, environment):
        # Need to get the CC Access Key for the username provided, if none exist then we need to generate one for them and use it
        apiKey = None
        values = environment.getApiKey()
        if values['status'] != "success":
            # The user doesn't have an app key so we need to generate one
            values = environment.genApiKey()
            if values['status'] != "success":
                return {"status": "error", "payload": values['payload']}
            else:
                values = environment.getApiKey()
                if values['status'] != "success":
                    return {"status": "error", "payload": {"error": "There was a problem obtaining the newly generated API key.", "traceback": values['payload']['traceback']}}
                else:
                    apiKey = values['payload']
                    self.apiKey = apiKey
                    return {"status": "success", "payload": apiKey}
        else:
            # We got our API key and don't need to generate a new one
            apiKey = values['payload']
            self.apiKey = apiKey
            return {"status": "success", "payload": apiKey}

    def getJobStatus(self, environment, jobId, schedulerName, loginDNS):
        # Need to get the CC Access Key for the username provided, if none exist then we need to generate one for them and use it
        apiKey = None
        if self.apiKey is None:
            values = self.getOrGenerateApiKey(environment)
            if values['status'] != "success":
                return values
            else:
                apiKey = values['payload']
        else:
            # We have already retrieved the API key so we no longer have to go get it.
            apiKey = self.apiKey

        # Now that we have the API key we can move on to getting the actual job status
        encodedUserName = ""
        encodedPassword = ""
        valKey = ""
        dateExpires = ""
        certLength = 1

        final = {"jobId": str(jobId), "userName": str(encodedUserName), "password": str(encodedPassword), "verbose": False, "instanceId": None, "jobNameInScheduler": None, "schedulerName": str(schedulerName), 'schedulerType': None, 'schedulerInstanceId': None, 'schedulerInstanceName': None, 'schedulerInstanceIp': None, 'printErrors': "False", "valKey": str(valKey), "dateExpires": str(dateExpires), "certLength": str(certLength), "jobInfoRequest": False, "ccAccessKey": str(apiKey), "printOutputLocation": "False", "printInstancesForJob": "False", "remoteUserName": environment.userName, "databaseInfo": None}

        ccqstatURL = "https://" + str(loginDNS) + "/srv/ccqstat"
        results = requests.post(ccqstatURL, cookies=environment.sessionCookies, json=final)

        jobOutput = json.loads(results.content)
        if jobOutput['status'] == "success":
            # Check and make sure the job was not deleted at some point
            if "The specified job Id does not exist in the database." not in str(jobOutput['payload']['message']):
                splitText = jobOutput['payload']['message'].split(" ")
                jobState = splitText[len(splitText)-1].replace("\n", "")
                return {"status": "success", "payload": jobState}
            else:
                return {"status": "error", "payload": "The job no longer exists within ccq, it was probably deleted by someone using the ccqdel command within the CloudyCluster Environments."}
        else:
            return {"status": "error", "payload": jobOutput['payload']}

    def submitJobCommandLine(self, transport, jobScriptLocation, jobScriptInfo):
        try:
            values = jobScriptInfo.executeCommand(transport, "ccqsub -js " + str(jobScriptLocation) + " -i " + str(self.apiKey))
            if values['status'] != "success":
                return values
            else:
                if "The job has successfully been submitted to the scheduler" in values['payload']['stdout']:
                    jobId = str(values['payload']['stdout']).split("job id is: ")[1].split(" ")[0]
                    schedulerName = str(values['payload']['stdout']).split("been submitted to the scheduler ")[1].split(" ")[0]
                    return {"status": "success", "payload": {"jobId": str(jobId), "schedulerName": str(schedulerName), "message": values['payload']['stdout']}}
                return values
        except Exception as e:
            return {"status": "error", "payload": {"error": "There was a problem encountered when trying to submit the job to the ccq scheduler.", "traceback": ''.join(traceback.format_exc(e))}}

# Copyright 2017
#
# Licensed under the Apache License, Version 2.0, <LICENSE-APACHE or
# http://apache.org/licenses/LICENSE-2.0> or the MIT license <LICENSE-MIT or
# http://opensource.org/licenses/MIT> or the LGPL, Version 2.0 <LICENSE-LGPLv2 or
# https://www.gnu.org/licenses/old-licenses/lgpl-2.0.txt>, at your option.
# This file may not be copied, modified, or distributed except according to those terms.


import os
import time
import traceback
import sys
import requests
import ast
import json
from requests import ConnectionError
from environment import Environment
import csv
from random import randint

sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
sys.path.append(os.path.join(os.path.dirname(__file__), '../Resources'))
sys.path.append(os.path.join(os.path.dirname(__file__), '../EnvironmentTemplates'))


class CloudyCluster(Environment):

    def __init__(self, **kwargs):
        self.supportedSchedulers = ["ccq", "torque", "slurm"]
        super(CloudyCluster, self).__init__(**kwargs)

    def getSession(self):
        try:
            results = requests.post("https://" + str(self.dnsName) + "/srv/cloudyLogin", json={'userName': str(self.userName), 'password': str(self.password)})

            if "Incorrect User / Password Combination" in str(results.content) or "You have too many failed login attempts" in str(results.content):
                return {"status": "error", "payload": {"error": str(json.loads(results.content)['message']), "traceback": ''.join(traceback.format_stack())}}
            if "Please Login" in str(results.content):
                return {"status": "error", "payload": {"error": "Invalid Username / Password combination.", "traceback": ''.join(traceback.format_stack())}}

            sessionCookies = results.cookies
            self.sessionCookies = sessionCookies
            return {"status": "success", "payload": sessionCookies}

        except ConnectionError as e:
            return {"status": "error", "payload": {"error": "Unable to locate CloudyCluster Control Node. Check the DNS name and try again!", "traceback": ''.join(traceback.format_exc())}}
        except Exception as e:
            return {"status": "error", "payload": {"error": "There was an error when trying to create the session.", "traceback": ''.join(traceback.format_exc(e))}}

    def validateControl(self, resourceClass, instance):
        try:
            correct_key = resourceClass.getStartupKey(instance, self.controlParameters)["payload"]
            url = "https://"+self.dnsName+"/srv/validateInstance"
            r = requests.post(url, json = {"key": correct_key})
            jar = r.cookies
            values = json.loads(r.text)
            if "error" in values:
                return {'status': 'error', 'payload': {"error": values["error"], "traceback": ''.join(traceback.format_stack())}}
            inviteKey = values['payload']['uuid']
            ######################################
            url = "https://"+self.dnsName+"/srv/cloudySave"
            specialObj = {'lastName': self.lastName, 'firstName': self.firstName, 'password': self.password, 'userName': self.userName, 'inviteKey': inviteKey}
            r = requests.post(url, cookies=jar, json=specialObj)
            values = json.loads(r.text)
            if values['status'] != 'success':
                return {'status': values['status'], 'payload': {"error": values['message'], "traceback": ''.join(traceback.format_stack())}}
            ######################################
            url = "https://"+self.dnsName+"/srv/getValididatorObj"
            r = requests.get(url, cookies=jar)
            values = json.loads(r.text)
            if values["status"] != "success":
                return {'status': values['status'], 'payload': {"error": values['message'], "traceback": ''.join(traceback.format_stack())}}
            else:
                sessionCookies = r.cookies
                return {"status": values['status'], "payload": sessionCookies}
        except Exception as e:
            return {"status": "error", "payload": {"error": "There was an error trying to validate the Control Instance.", "traceback": ''.join(traceback.format_exc())}}

    def createControl(self, templateLocation, resourceName):
        resourceClass = None
        try:
            values = self.createResourceClass(self.region, self.profile)
            if values['status'] != "success":
                return {"status": "error", "payload": {"error": values['payload']['error'], "traceback": values['payload']['traceback']}}
            else:
                resourceClass = values['payload']
        except Exception as e:
            return {"status": "error", "payload": {"error": "There was a problem parsing the configuration file for the required variables.", "traceback": ''.join(traceback.format_exc())}}

        kwargs = {"templateLocation": str(templateLocation), "resourceName": str(resourceName), "options": self.controlParameters}
        values = resourceClass.createControlResources(**kwargs)
        if values['status'] != "success":
            return {"status": "error", "payload": values['payload']}
        else:
            print("Successfully started the creation of the Control Resources. Now monitoring to determine when the resources are up and running.")
            resourceId = values['payload']
            if "instance" in values:
                instance = values["instance"]
            else:
                instance = resourceName
            if str(self.cloudType) == "aws":
                f = open('infoFile', 'w')
                f.write("controlResources="+str(resourceId)+"\n")
                f.close()
            if str(self.cloudType).lower() == "aws":
                print("The newly created Cloud Formation Stack Id is: " + str(resourceId))
                values = resourceClass.monitorControlResources(resourceId, "creation")
            elif str(self.cloudType).lower() == "gcp":
                values['status'] = "success"
            if values['status'] != "success":
                return {"status": "error", "payload": values['payload']}
            else:
                if str(self.cloudType).lower() == "aws":
                    print("The Control Resources are up and running, retrieving the new IP address of the Control Resources.")
                    values = resourceClass.getValue("InstanceIP", resourceId)
                elif str(self.cloudType).lower() == "gcp":
                    values['status'] = "success"
                if values['status'] != "success":
                    return {"status": "error", "payload": values['payload']}
                else:
                    print("Successfully retrieved the new IP address of the Control Resources. Now obtaining the newly assigned DNS name for the Control Resources. The Control Node IP Address is: " + str(values['payload']) + ".")
                    ipAddress = values['payload']
                    maxTimeToWait = 600
                    timeElapsed = 0
                    timeToWait = 60
                    done = False
                    values = None
                    while not done:
                        values = self.getControlDns(ipAddress)
                        if values['status'] != "success":
                            if maxTimeToWait < timeElapsed:
                                done = True
                            time.sleep(timeToWait)
                            timeElapsed += timeToWait
                        else:
                            done = True
                    if values['status'] != "success":
                        return {"status": "error", "payload": values['payload']}
                    else:
                        print("Successfully retrieved the new DNS name for the Control Resources. The new DNS name is: " + str(self.dnsName))
                        print("Now obtaining the newly created Database Table names.")
                        values = self.getDatabaseTableNames()
                        if values['status'] != "success":
                            print(values)
                            return {"status": "error", "payload": values['payload']}
                        else:
                            print("Successfully obtained the newly created Database Table names.")
                            stuff = self.validateControl(resourceClass, instance)
                            if stuff["status"] != "success":
                                if "File failed to validate" in str(stuff['payload']['error']):
                                    return {"status": "error", "payload": {"error": "The .pem key file location specified in the configuration file does not match the .pem key file used to launch the instances. Please check the key and try again.", "traceback": ''.join(traceback.format_stack())}}
                                return {"status": "error", "payload": stuff["payload"]}
                            else:
                                values = self.getSession()
                                if values['status'] != "success":
                                    return {"status": "error", "payload": values['payload']}
                                else:
                                    time.sleep(randint(0, 180))
                                    try:
                                        self.controlParameters['readcapacity']
                                        self.controlParameters['writecapacity']
                                        values = self.modifyDBThroughput(self.controlParameters['readcapacity'], self.controlParameters['writecapacity'])
                                        if values['status'] != "success":
                                            return {"status": "error", "payload": values['payload']}
                                        else:
                                            print("Successfully modified the Database throughput to the values requested in the configuration file.")
                                    except Exception as e:
                                        # The user did not specify any modifications to the DB Throughput so we just leave it as the default.
                                        pass

                                    values = self.genApiKey()
                                    if values['status'] != "success":
                                        return {"status": "error", "payload": values['payload']}
                                    else:
                                        print("Successfully generated a new API Key for the user. Now writing out a few last configuration details.")
                                        values = self.writeOutEfsObjectToDb()
                                        if values['status'] != "success":
                                            return {"status": "error", "payload": values['payload']}
                                        else:
                                            print("Successfully wrote out the last few configuration details.")
                                            print("\n")
                                            return {"status": "success", "payload": self.dnsName}

    def createEnvironment(self):
        # Here we will need to get the Template class for CloudyCluster and try and retrieve the template variables
        try:
            kwargs = {"environmentType": self.environmentType, "parameters": self.ccEnvironmentParameters, "templateName": self.ccEnvironmentParameters['templatename']}
        except Exception as e:
            return {"status": "error", "payload": {"error": "There was a problem parsing the configuration file for the required variables.", "traceback": ''.join(traceback.format_stack())}}

        # Load the module (ex: import cloudycluster)
        environmentTemplateClass = __import__(str(self.environmentType).lower() + "Templates")

        # Get the actual class that we need to instantiate (ex: from cloudycluster import CloudyCluster)
        myClass = getattr(environmentTemplateClass, self.environmentType + "Template")

        # Instantiate the class with the required parameters
        environmentTemplate = myClass(**kwargs)

        values = environmentTemplate.get()
        if values['status'] != "success":
            return {"status": "error", "payload": values['payload']}
        else:
            values = environmentTemplate.populate(self.name, self.cloudType)
            if values['status'] != "success":
                return {"status": "error", "payload": values['payload']}
            else:
                # This is the ClusterObject that we need to pass to the /CloudyCluster/Base route
                template = values['payload']['template']
                self.name = values['payload']['environmentName']
                print("The new full Environment name is: " + str(self.name))
                values = self.saveEnvironmentConfig(template)
                if values['status'] != "success":
                    return {"status": "error", "payload": values['payload']}
                else:
                    values = self.startEnvironmentCreation(template)
                    if values['status'] != "success":
                        return {"status": "error", "payload": values['payload']}
                    else:
                        values = self.monitorEnvironmentCreation()
                        if values['status'] != "success":
                            return {"status": "error", "payload": values['payload']}
                        else:
                            return {"status": "success", "payload": "The Environment was created successfully."}

    def deleteControl(self):
        values = self.createResourceClass(self.region, self.profile)
        if values['status'] != "success":
            return {"status": "error", "payload": values['payload']}
        else:
            resourceClass = values['payload']

        try:
            url = 'https://'+str(self.dnsName)+'/srv/deleteOriginalControlNode'
            r = requests.post(url, cookies=self.sessionCookies, json={'deleteTable': "true"})
            response = json.loads(r.content)
            if response['status'] != "success":
                return {"status": "error", "payload": {"error": response['message'], "traceback": ''.join(traceback.format_stack())}}
            else:
                return {"status": "success", "payload": "The Control Resources have been deleted successfully."}
        except Exception as e:
            return {"status": "error", "payload": {"error": "There was an error when trying to delete the Control Resources.", "traceback": ''.join(traceback.format_exc(e))}}

    def deleteEnvironment(self):
        if "-" not in self.name:
            return {"status": "error", "payload": {"error": "In order to delete the Environment properly the full Environment name is required. This looks like <environment_name>-XXXX, please specify the full Environment name using the -en commandline argument or by specifying the environmentName field in the General section of the configuration file.", "traceback": ''.join(traceback.format_stack())}}

        if self.sessionCookies is None:
            values = self.getSession()
            if values['status'] != "success":
                return {"status": "error", "payload": values['payload']}

        # We need to get the ClusterObject in order to be able to delete the Environment
        clusterObject = None
        values = self.getEnvironmentObject()
        if values['status'] != "success":
                return {"status": "error", "payload": values['payload']}
        else:
            clusterObject = values['payload']

        try:
            clusterObject["action"] = "terminate"
            url = 'https://'+str(self.dnsName)+'/srv/cloudycluster/Base'
            try:
                r = requests.post(url, cookies=self.sessionCookies, json={'clusterObj': clusterObject}, timeout=60)
                try:
                    response = json.loads(r.content)
                    if response['status'] != "success":
                        return {"status": "error", "payload": {"error": response['message'], "traceback": ''.join(traceback.format_stack())}}
                except Exception as e:
                    # We need to time out so that we can monitor the deletion of the Environment, we time out the request so that we can do other things while the Environment is deleting.
                    pass
            except Exception as e:
                # If we timeout it throws an exception which means we successfully started the delete and now we can monitor it
                pass

            # We successfully started the deletion of the Environment, now we need to monitor it
            values = self.monitorEnvironmentDeletion()
            if values['status'] != "success":
                return {"status": "success", "payload": values['payload']}
            else:
                print("The Environment has successfully been deleted.")
                return {"status": "success", "payload": "The Environment has been successfully deleted."}
        except Exception as e:
            return {"status": "error", "payload": {"error": "There was an error when trying to delete the Environment.", "traceback": ''.join(traceback.format_exc(e))}}

    def checkState(self):
        try:
            # Currently only checks to see if the environment is running, needs to be expanded to check if stopped and stuff
            done = True
            networkResponse = requests.post('https://' + str(self.dnsName) + "/srv/getSpinningClusterPart", cookies=self.sessionCookies, json={"clusterName": str(self.name), "groupName": "VPC Info", "type": "Network"})
            networkResults = networkResponse.content
            networkResults = json.loads(networkResults)['Network']['VPC Info']['instances']
            for instance in networkResults:
                if str(instance)[:2] == "i-":
                    stateInfo = ast.literal_eval(networkResults[instance]["State"])
                    if str(stateInfo["Name"]).lower() != "running":
                        print("Instance (" + str(instance) + ") is not yet in the running state.")
                        # Instance has not yet successfully stopped/resumed so we must loop through again
                        done = False

            utilityResponse = requests.post('https://' + str(self.dnsName) + "/srv/getSpinningClusterPart", cookies=self.sessionCookies, json={"clusterName": str(self.name), "groupName": "Utility", "type": "Utility"})
            utilityResults = utilityResponse.content
            utilityResults = json.loads(utilityResults)['Utility']['Utility']['instances']
            for instance in utilityResults:
                if str(instance)[:2] == "i-":
                    stateInfo = ast.literal_eval(utilityResults[instance]["State"])
                    if str(stateInfo["Name"]).lower() != str("running") and utilityResults[instance]["RecType"] != "ControlNode":
                        print("Instance (" + str(instance) + ") is not yet in the running state.")
                        # Instance has not yet successfully stopped/resumed so we must loop through again
                        done = False
            if done:
                return {"status": "success", "payload": True}
            else:
                return {"status": "success", "payload": False}
        except Exception as e:
            return {"status": "error", "payload": {"error": "There was an error when trying to check the state of the Environment.", "traceback": ''.join(traceback.format_exc())}}

    def changeState(self, action):
        desiredState = ""
        if action == "pause":
            desiredState = "stopped"
        elif action == "resume":
            desiredState = "running"
        else:
            return {"status": "error", "payload": {"error": "Unsupported state (" + str(action) + ") passed to changeEnvironmentState.", "traceback": ''.join(traceback.format_stack())}}

        results = requests.post('https://' + str(self.dnsName) + "/srv/cloudycluster/Base", cookies=self.sessionCookies, json={"clusterObj": {"action": action, "clusterName": str(self.name), "groupName": "all", "instanceID": "all", "nodeType": "all", "schedType": None}})

        # It takes a few minutes for the environment to resume so wait two minutes before checking to see if the instances are running.
        if desiredState == "running":
            time.sleep(120)

        # Need to check and make sure that all the instances actually paused/resumed successfully before returning success. For the small environment we will need to check both Utility and Network groups
        print("Waiting for the instances to enter the desired state.")
        done = False
        timeElapsed = 0
        maxTimeToWait = 360
        sleepTime = 30
        while not done:
            try:
                done = True
                networkResponse = requests.post('https://' + str(self.dnsName) + "/srv/getSpinningClusterPart", cookies=self.sessionCookies, json={"clusterName": str(self.name), "groupName": "VPC Info", "type": "Network"})
                networkResults = networkResponse.content
                networkResults = json.loads(networkResults)['Network']['VPC Info']['instances']
                for instance in networkResults:
                    if str(instance)[:2] == "i-":
                        stateInfo = ast.literal_eval(networkResults[instance]["State"])
                        if str(stateInfo["Name"]).lower() != str(desiredState):
                            print("Instance (" + str(instance) + ") is not yet in the " + str(desiredState) +" state.")
                            # Instance has not yet successfully stopped/resumed so we must loop through again
                            done = False

                utilityResponse = requests.post('https://' + str(self.dnsName) + "/srv/getSpinningClusterPart", cookies=self.sessionCookies, json={"clusterName": str(self.name), "groupName": "Utility", "type": "Utility"})
                utilityResults = utilityResponse.content
                utilityResults = json.loads(utilityResults)['Utility']['Utility']['instances']
                for instance in utilityResults:
                    if str(instance)[:2] == "i-":
                        stateInfo = ast.literal_eval(utilityResults[instance]["State"])
                        if str(stateInfo["Name"]).lower() != str(desiredState) and utilityResults[instance]["RecType"] != "ControlNode":
                            print("Instance (" + str(instance) + ") is not yet in the " + str(desiredState) +" state.")
                            # Instance has not yet successfully stopped/resumed so we must loop through again
                            done = False
                if not done:
                    time.sleep(sleepTime)
                    timeElapsed += sleepTime
                    if timeElapsed > maxTimeToWait:
                        if desiredState == "stopped":
                            return {"status": "error", "payload": {"error": "Timeout waiting for the instances to stop successfully. The instances may not be completely stopped and you could still be incurring charges.", "traceback": ''.join(traceback.format_stack())}}
                        elif desiredState == "running":
                            return {"status": "error", "payload": {"error": "Timeout waiting for the instances to enter the running state successfully. The instances may not be completely started and you could still be incurring charges. Make sure that the AWS Limits on this AWS account are able to handle the number of running instances.", "traceback": ''.join(traceback.format_stack())}}
                else:
                    if desiredState == "stopped":
                        return {"status": "success", "payload": "The environment has been successfully paused."}
                    elif desiredState == "running":
                        return {"status": "success", "payload": "The environment has been successfully resumed."}
            except Exception as e:
                time.sleep(sleepTime)
                timeElapsed += sleepTime
                if timeElapsed > maxTimeToWait:
                    if desiredState == "stopped":
                        return {"status": "error", "payload": {"error": "Timeout waiting for the instances to stop successfully. The instances may not be completely stopped and you could still be incurring charges.", "traceback": ''.join(traceback.format_stack())}}
                    elif desiredState == "running":
                        return {"status": "error", "payload": {"error": "Timeout waiting for the instances to enter the running state successfully. The instances may not be completely started and you could still be incurring charges. Make sure that the AWS Limits on this AWS account are able to handle the number of running instances.", "traceback": ''.join(traceback.format_stack())}}

    def getApiKey(self):
        maxTimeToWait = 180
        timeElapsed = 0
        timeToWait = 30
        done = False
        while not done:
            try:
                ccAccessKey = None
                results = requests.post("https://" + str(self.dnsName) + "/srv/listAppKeys", cookies=self.sessionCookies)
                output = json.loads(results.content)
                for key in output['payload']:
                    if key['userName'] == str(self.userName):
                        ccAccessKey = key['key']

                if ccAccessKey is not None:
                    return {"status": "success", "payload": str(ccAccessKey)}
                else:
                    return {"status": "error", "payload": {"error": "Unable to retrieve the CC App Key required for ccq job submission. Check to make sure the user you are submitting the job as has created a CC App key through the CC UI.", "traceback": ''.join(traceback.format_stack())}}
            except Exception as e:
                if timeElapsed > maxTimeToWait:
                    return {"status": "error", "payload": {"error": "Unable to retrieve the CC App Key required for ccq job submission due to an exception. Check to make sure the user you are submitting the job as has created a CC App key through the CC UI.", "traceback": ''.join(traceback.format_exc())}}
                else:
                    time.sleep(timeToWait)
                    timeElapsed += timeToWait

    def genApiKey(self):
        maxTimeToWait = 180
        timeElapsed = 0
        timeToWait = 30
        done = False
        while not done:
            try:
                url = 'https://' + str(self.dnsName) + '/srv/saveAndGenUserAppKey'
                r = requests.post(url, cookies=self.sessionCookies, json={'userName': ""})
                values = json.loads(r.content)
                if values['status'] != "success":
                    return {"status": "error", "payload": {"error": values['message'], "traceback": ''.join(traceback.format_exc())}}
                else:
                    return {"status": "success", "payload": values['message']}
            except Exception as e:
                if timeElapsed > maxTimeToWait:
                    return {"status": "error", "payload": {"error": "There was a problem trying to generate a new API Key.", "traceback": ''.join(traceback.format_exc())}}
                else:
                    time.sleep(timeToWait)
                    timeElapsed += timeToWait

    def monitorJob(self, jobId, ccAccessKey, schedulerName, loginDomainName, verbose, jobPrefixString, schedType):
        encodedUserName = ""
        encodedPassword = ""
        valKey = ""
        dateExpires = ""
        certLength = 1

        final = {"jobId": str(jobId), "userName": str(encodedUserName), "password": str(encodedPassword), "verbose": verbose, "instanceId": None, "jobNameInScheduler": None, "schedulerName": str(schedulerName), "schedulerHostName": None, 'schedulerType': None, 'schedulerInstanceId': None, 'schedulerInstanceName': None, 'schedulerInstanceIp': None, "printJobOwner": "False", "printSubmissionTime": "False", "printDispatchTime": "False", "printSubmitHost": "False", "printNumCPUs": "False", 'printErrors': "False", "valKey": str(valKey), "dateExpires": str(dateExpires), "certLength": str(certLength), "jobInfoRequest": False, "ccAccessKey": str(ccAccessKey), "printOutputLocation": "False", "printInstancesForJob": "False", "remoteUserName": None, "databaseInfo": None}

        ccqstatURL = "https://" + str(loginDomainName) + "/srv/ccqstat"
        results = requests.post(ccqstatURL, cookies=self.sessionCookies, json=final)

        jobOutput = json.loads(results.content)
        if jobOutput['status'] == "success":
            #TODO need to put code here to handle the checks for determining if all of the generated jobs have finished successfully
            if verbose:
                # We need to send the job output to the checkJobCompletion method to see if all the jobs are done
                stillRunning = 0
                lineNum = 0
                for line in jobOutput['payload']['message'].split("\n"):
                    lineNum += 1
                    if "JOBID" not in line and str(jobPrefixString) in line:
                        stillRunning += 1
                print("STILL RUNNING: " + str(stillRunning))
                if stillRunning == 0:
                    return {"status": "success", "payload": True}
                else:
                    return {"status": "success", "payload": False}
            else:
                # Check and make sure the job was not deleted at some point
                if "The specified job Id does not exist in the database." not in str(jobOutput['payload']['message']):
                    splitText = jobOutput['payload']['message'].split(" ")
                    jobState = splitText[len(splitText)-1].replace("\n", "")
                    return {"status": "success", "payload": jobState}
                else:
                    return {"status": "error", "payload": {"error": "The job no longer exists within ccq, it was probably deleted by someone using the ccqdel command within the CloudyCluster Environments.", "traceback": ''.join(traceback.format_stack())}}
        else:
            return {"status": "error", "payload": jobOutput['payload']}

    def getJobSubmitDns(self):
        maxTimeToWait = 180
        timeElapsed = 0
        timeToWait = 30
        done = False
        while not done:
            try:
                loginDomainName = None
                # The job is submitted to the Login Instance so we must get it's domain name here.
                utilityResponse = requests.post('https://' + str(self.dnsName) + "/srv/getSpinningClusterPart", cookies=self.sessionCookies, json={"clusterName": str(self.name), "groupName": "Utility", "type": "Utility"})
                utilityResults = utilityResponse.content
                utilityResults = json.loads(utilityResults)['Utility']['Utility']['instances']
                for instance in utilityResults:
                    if str(self.cloudType).lower() == "aws":
                        if str(instance)[:2] == "i-":
                            if utilityResults[instance]["RecType"] == "WebDavNode":
                                loginDomainName = utilityResults[instance]['domainName']
                    elif str(self.cloudType).lower() == "gcp":
                        if utilityResults[instance]["RecType"] == "WebDavNode":
                            loginDomainName = utilityResults[instance]['domainName']

                if loginDomainName is None:
                    if timeElapsed > maxTimeToWait:
                        return {"status": "error", "payload": {"error": "There was a problem trying to get the Login Instance's DNS name that is required to submit the job.", "traceback": ''.join(traceback.format_stack())}}
                    else:
                        time.sleep(timeToWait)
                        timeElapsed += timeToWait
                else:
                    return {"status": "success", "payload": loginDomainName}
            except Exception as e:
                if timeElapsed > maxTimeToWait:
                    return {"status": "error", "payload": {"error": "There was a problem trying to get the Login Instance's DNS name that is required to submit the job.", "traceback": ''.join(traceback.format_exc())}}
                else:
                    print(traceback.format_exc())
                    time.sleep(timeToWait)
                    timeElapsed += timeToWait

    def getControlDns(self, ipAddress):
        try:
            tempurl = "http://"+str(ipAddress)+"/srv/getCurrentDomain"
            r = requests.get(tempurl)
            values = json.loads(r.content)
            if values['status'] != "success":
                return {"status": "error", "payload": {"error": str(values['message']), "traceback": ''.join(traceback.format_stack())}}
            else:
                self.dnsName = values['payload']
                done = True
                return {"status": "success", "payload": values['payload']}
        except Exception as e:
                return {"status": "error", "payload": {"error": "There was a problem trying to obtain the Control Instance DNS.", "traceback": ''.join(traceback.format_exc())}}

    def getDatabaseTableNames(self):
        maxTimeToWait = 300
        timeElapsed = 0
        timeToWait = 30
        done = False
        while not done:
            try:
                tempurl = "https://" + str(self.dnsName) + "/srv/getGeneratedTableNames"
                r = requests.get(tempurl)
                values = json.loads(r.content)
                if values['status'] != "success":
                    return {"status": "error", "payload": {"error": str(values['message']), "traceback": ''.join(traceback.format_stack())}}
                else:
                    return {"status": "success", "payload": values['payload']}
            except Exception as e:
                if timeElapsed > maxTimeToWait:
                    return {"status": "error", "payload": {"error": "There was a problem trying to obtain the DB Table names.", "traceback": ''.join(traceback.format_exc())}}
                else:
                    time.sleep(timeToWait)
                    timeElapsed += timeToWait

    def prePopulatedDb(self, objectTableCsvFile, lookupTableCsvFile, objectTableName, lookupTableName):
        values = self.createResourceClass(self.region, self.profile)
        if values['status'] != "success":
            return {"status": "error", "payload": values['payload']}
        else:
            resourceClass = values['payload']

        dbObjectTableItemList = []

        try:
            with open(objectTableCsvFile) as csvFile:
                reader = csv.DictReader(csvFile)
                for row in reader:
                    tempRow = {}
                    for item in row:
                        if row[item] != "":
                            tempRow[item] = row[item]
                    dbObjectTableItemList.append(tempRow)
        except Exception as e:
            return {"status": "error", "payload": {"error": "Encountered an error when trying to load the provided Object Table data from the CSV file.", "traceback": ''.join(traceback.format_exc)}}

        dbIndexTableItemList = []
        try:
            with open(lookupTableCsvFile) as csvFile:
                reader = csv.DictReader(csvFile)
                for row in reader:
                    tempRow = {}
                    for item in row:
                        if row[item] != "":
                            tempRow[item] = row[item]
                    dbIndexTableItemList.append(tempRow)
        except Exception as e:
            return {"status": "error", "payload": {"error": "Encountered an error when trying to load the provided Lookup Table data from the CSV file.", "traceback": ''.join(traceback.format_exc)}}

        values = resourceClass.writeObjectsToDatabase(dbIndexTableItemList, dbObjectTableItemList, lookupTableName, objectTableName)
        if values['status'] != "success":
            return {"status": "error", "payload": values['payload']}
        else:
            return {"status": "success", "payload": values['payload']}

    def writeOutEfsObjectToDb(self):
        maxTimeToWait = 180
        timeElapsed = 0
        timeToWait = 30
        done = False
        while not done:
            try:
                url = 'https://' + str(self.dnsName) + '/srv/writeEfs'
                r = requests.get(url)
                try:
                    response = json.loads(r.content)
                    if response['status'] == "error":
                        return {"status": "error", "payload": {"error": response['message'], "traceback": ''.join(traceback.format_stack())}}
                except Exception as e:
                    # This route does not return anything on success
                    return {"status": "success", "payload": "Successfully wrote out the EFS object to the DB."}
            except Exception as e:
                if timeElapsed > maxTimeToWait:
                    return {"status": "error", "payload": {"error": "There was an error encountered when attempting to write out the EFS object to the DB.", "traceback": ''.join(traceback.format_exc())}}
                else:
                    time.sleep(timeToWait)
                    timeElapsed += timeToWait

    def saveEnvironmentConfig(self, template):
        maxTimeToWait = 180
        timeElapsed = 0
        timeToWait = 30
        done = False
        while not done:
            try:
                url = 'https://' + str(self.dnsName) + '/srv/saveCluster'
                r = requests.post(url, cookies=self.sessionCookies, json={'clusterObj': template, 'clusterName': str(self.name)})
                response = json.loads(r.content)
                if response['response'] != "success":
                    return {"status": "error", "payload": {"error": response['message'], "traceback": ''.join(traceback.format_stack())}}
                else:
                    return {"status": "success", "payload": "Successfully wrote out the Cluster object to the DB."}
            except Exception as e:
                if timeElapsed > maxTimeToWait:
                    return {"status": "error", "payload": {"error": "There was an error encountered when attempting to write out the Cluster object to the DB.", "traceback": ''.join(traceback.format_exc())}}
                else:
                    time.sleep(timeToWait)
                    timeElapsed += timeToWait

    def startEnvironmentCreation(self, template):
        maxTimeToWait = 180
        timeElapsed = 0
        timeToWait = 30
        done = False
        while not done:
            try:
                url = 'https://' + str(self.dnsName) + '/srv/startCluster'
                r = requests.post(url, cookies=self.sessionCookies, json={'clusterObj': template})
                response = json.loads(r.content)
                print("RESPONSE IS ")
                print(str(response))
                if response['response'] != "success":
                    return {"status": "error", "payload": {"error": response['message'], "traceback": ''.join(traceback.format_stack())}}
                else:
                    return {"status": "success", "payload": "The Environment creation was started successfully."}
            except Exception as e:
                if timeElapsed > maxTimeToWait:
                    return {"status": "error", "payload": {"error": "There was an error encountered when attempting to start the Environment creation.", "traceback": ''.join(traceback.format_exc())}}
                else:
                    time.sleep(timeToWait)
                    timeElapsed += timeToWait

    def monitorEnvironmentCreation(self):
        clusterError = None
        url = 'https://' + str(self.dnsName) + '/srv/getSpinningCluster'
        maxTimeToWait = 2400 # 20 minutes=1200, 40 minutes=2400, 60 minutes=3600
        timeElapsed = 0
        timeToWait = 120
        done = False
        while not done:
            try:
                r = requests.post(url, cookies=self.sessionCookies, json={'clusterName': str(self.name)})
                clusterInfo = json.loads(r.content)
                if clusterInfo['clusterSpunUp'] == "true":
                    time.sleep(120)
                    return {"status": "success", "payload": "The Environment has been created successfully."}
                else:
                    if str(clusterInfo['clusterError']) != "none":
                        # Environment encountered an error and failed
                        return {"status": "error", "payload": {"error": "There was an error encountered during the creation of the new Environment.\n" + str(clusterError), "traceback": ''.join(traceback.format_stack())}}
            except Exception as e:
                print("Checking status error:")
                print(''.join(traceback.format_exc()))
                print("Printing content of response\n")
                print(r.content)
                pass

            if maxTimeToWait < timeElapsed:
                # Timeout waiting for Environment to spin up
                return {"status": "error", "payload": {"error": "The new Environment did not spin up successfully before hitting the timeout.", "traceback": ''.join(traceback.format_stack())}}
            else:
                time.sleep(timeToWait)
                timeElapsed += timeToWait

    def getEnvironmentObject(self):
        maxTimeToWait = 180
        timeElapsed = 0
        timeToWait = 30
        done = False
        while not done:
            try:
                url = 'https://'+str(self.dnsName)+'/srv/getClusterByName'
                r = requests.post(url, cookies=self.sessionCookies, json={'clusterName': self.name})
                response = json.loads(r.content)
                try:
                    if response['status'] == "error":
                        return {"status": "error", "payload": {"error": response['message'], "traceback": ''.join(traceback.format_stack())}}
                except Exception as e:
                    # If successful and the Environment doesn't exist we get back a blank object
                    if len(response) > 0:
                        return {"status": "success", "payload": response}
                    else:
                        return {"status": "error", "payload": {"error": "The requested Environment was not found on the Control Resource specified.", "traceback": ''.join(traceback.format_stack())}}
            except Exception as e:
                if timeElapsed > maxTimeToWait:
                    return {"status": "error", "payload": {"error": "There was an error when trying to obtain the information required to delete the Environment from the Environment.", "traceback": ''.join(traceback.format_exc(e))}}
                else:
                    time.sleep(timeToWait)
                    timeElapsed += timeToWait

    def monitorEnvironmentDeletion(self):
        maxTimeToWait = 2400 # 20 minutes
        timeElapsed = 0
        timeToWait = 120
        done = False
        print("Now waiting for the Environment to delete.")
        while not done:
            print("You have waited " + str(int(timeElapsed)/int(60)) + " minutes for the Environment to delete.")
            try:
                url = 'https://'+str(self.dnsName)+'/srv/getClusterByName'
                r = requests.post(url, cookies=self.sessionCookies, json={'clusterName': self.name})
                try:
                    response = json.loads(r.content)
                    try:
                        if response['status'] == "error":
                            pass
                    except Exception as e:
                        if len(response) > 0:
                            # We still got the Cluster Object back
                            pass
                except Exception as e:
                    # The clusterObject is gone from the database we can return success
                    done = True
                    return {"status": "success", "payload": "The Environment has been deleted successfully"}
            except Exception as e:
                pass

            if maxTimeToWait < timeElapsed:
                # Timeout waiting for Environment to spin up
                done = True
                return {"status": "error", "payload": {"error": "The timeout was reached while waiting for the Environment to delete.", "traceback": ''.join(traceback.format_stack())}}
            else:
                time.sleep(timeToWait)
                timeElapsed += timeToWait

    def getLoginInstanceDomainName(self):
        maxTimeToWait = 180
        timeElapsed = 0
        timeToWait = 30
        done = False
        while not done:
            try:
                loginDomainName = None
                # The job is submitted to the Login Instance so we must get it's domain name here.
                utilityResponse = requests.post('https://' + str(self.dnsName) + "/srv/getSpinningClusterPart", cookies=self.sessionCookies, json={"clusterName": str(self.name), "groupName": "Utility", "type": "Utility"})
                utilityResults = utilityResponse.content
                utilityResults = json.loads(utilityResults)['Utility']['Utility']['instances']
                for instance in utilityResults:
                    if str(self.cloudType).lower() == "aws":
                        if str(instance)[:2] == "i-":
                            if utilityResults[instance]["RecType"] == "WebDavNode":
                                loginDomainName = utilityResults[instance]['domainName']
                    elif str(self.cloudType).lower() == "gcp":
                        if "-wd-" in str(instance):
                            loginDomainName = utilityResults[instance]['domainName']

                if loginDomainName is None:
                    return {"status": "error", "payload": {"error": "Unable to find the Login instance DNS.", "traceback": ''.join(traceback.format_stack())}}
                else:
                    return {"status": "success", "payload": loginDomainName}
            except Exception as e:
                if timeElapsed > maxTimeToWait:
                    return {"status": "error", "payload": {"error": "An error was encountered while trying to retrieve the Login instance DNS.", "traceback": ''.join(traceback.format_exc())}}
                else:
                    time.sleep(timeToWait)
                    timeElapsed += timeToWait

    # Get the state of the job that we submitted from the ccq scheduler
    def getJobState(self, jobId, ccAccessKey, schedulerName, loginDomainName, verbose, jobPrefixString, schedType):
        encodedUserName = ""
        encodedPassword = ""
        valKey = ""
        dateExpires = ""
        certLength = 1

        values = self.createSchedulerClass(schedulerType=schedType)
        if values['status'] != "success":
            return {"status": "error", "payload": values['payload']}
        else:
            scheduler = values['payload']

        final = {"jobId": str(jobId), "userName": str(encodedUserName), "password": str(encodedPassword), "verbose": verbose, "instanceId": None, "jobNameInScheduler": None, "schedulerName": str(schedulerName), "schedulerHostName": None, 'schedulerType': None, 'schedulerInstanceId': None, 'schedulerInstanceName': None, 'schedulerInstanceIp': None, "printJobOwner": "False", "printSubmissionTime": "False", "printDispatchTime": "False", "printSubmitHost": "False", "printNumCPUs": "False", 'printErrors': "False", "valKey": str(valKey), "dateExpires": str(dateExpires), "certLength": str(certLength), "jobInfoRequest": False, "ccAccessKey": str(ccAccessKey), "printOutputLocation": "False", "printInstancesForJob": "False", "remoteUserName": None, "databaseInfo": None}

        ccqstatURL = "https://" + str(loginDomainName) + "/srv/ccqstat"
        results = requests.post(ccqstatURL, cookies=self.sessionCookies, json=final)

        jobOutput = json.loads(results.content)
        if jobOutput['status'] == "success":
            if verbose:
                # We need to send the job output to the checkJobCompletion method to see if all the jobs are done
                values = scheduler.checkExperimentJobCompletion(jobOutput['payload']['message'], jobPrefixString)
                if values['status'] != "success":
                    return {"status": "error", "payload": values['payload']}
                else:
                    return {"status": "success", "payload": values['payload']}
            else:
                # Check and make sure the job was not deleted at some point
                if "The specified job Id does not exist in the database." not in str(jobOutput['payload']['message']):
                    splitText = jobOutput['payload']['message'].split(" ")
                    jobState = splitText[len(splitText)-1].replace("\n", "")
                    return {"status": "success", "payload": jobState}
                else:
                    return {"status": "error", "payload": "The job no longer exists within ccq, it was probably deleted by someone using the ccqdel command within the CloudyCluster Environments."}
        else:
            return {"status": "error", "payload": jobOutput['payload']}

    def modifyDBThroughput(self, readCapacity, writeCapacity):
        maxTimeToWait = 180
        timeElapsed = 0
        timeToWait = 30
        done = False
        while not done:
            try:
                url = 'https://' + str(self.dnsName) + '/srv/setNewDBThroughput'
                r = requests.post(url, cookies=self.sessionCookies, json={"read": str(readCapacity), "write": str(writeCapacity)})
                values = json.loads(r.content)
                if values['status'] != "success":
                    if "The provisioned throughput for the table will not change" in values['message']:
                        return {"status": "success", "payload": "Successfully updated the DB Table Capacity"}
                    return {"status": "error", "payload": values['message']}
                else:
                    return {"status": "success", "payload": values['message']}
            except Exception as e:
                if timeElapsed > maxTimeToWait:
                    return {"status": "error", "payload": {"error": "There was a problem trying to update the Database Throughput values.", "traceback": ''.join(traceback.format_exc())}}
                else:
                    time.sleep(timeToWait)
                    timeElapsed += timeToWait

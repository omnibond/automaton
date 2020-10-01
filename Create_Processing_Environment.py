# Copyright 2017
#
# Licensed under the Apache License, Version 2.0, <LICENSE-APACHE or
# http://apache.org/licenses/LICENSE-2.0> or the MIT license <LICENSE-MIT or
# http://opensource.org/licenses/MIT> or the LGPL, Version 2.0 <LICENSE-LGPLv2 or
# https://www.gnu.org/licenses/old-licenses/lgpl-2.0.txt>, at your option.
# This file may not be copied, modified, or distributed except according to those terms.


import sys
import argparse
import os
import uuid
import traceback
import json
from random import randint
import time

import oauth2client.client

import emailScript as tidings
import configparser

sys.path.append(os.path.dirname(os.path.realpath(__file__))+str("/Schedulers"))
sys.path.append(os.path.dirname(os.path.realpath(__file__))+str("/Resources"))
sys.path.append(os.path.dirname(os.path.realpath(__file__))+str("/Environments"))
sys.path.append(os.path.dirname(os.path.realpath(__file__))+str("/WorkflowTemplates"))
sys.path.append(os.path.dirname(os.path.realpath(__file__))+str("/JobScriptTemplates"))


def main():
    parser = argparse.ArgumentParser(description="A utility that users can utilize to setup and create a CloudyCluster Control Node.")
    parser.add_argument('-V', '--version', action='version', version='ccAutomaton (version 1.0)')
    parser.add_argument('-et', '--environmentType', help="The type of environment to create.", default=None)
    parser.add_argument('-all', action='store_true', help="Run the entire process: create Control Resources, create an Environment, submit the specified jobs, and upon job completion delete the Environment and the Control Resources.", default=None)
    parser.add_argument('-cf', '--configFilePath', help="The path to the configuration file to be used by ccAutomaton. The default is the ccAutomaton.conf file in the local directory.", default="ccAutomaton.conf")
    parser.add_argument('-cc', action='store_true', help="If specified, this argument tells ccAutomaton to create new Control Resources.", default=None)
    parser.add_argument('-ce', action='store_true', help="If specified, this argument tells ccAutomaton to create a new Environment.", default=None)
    parser.add_argument('-rj', action='store_true', help="If specified, this argument tells ccAutomaton to run the jobs specified in the configuration file.", default=None)
    parser.add_argument('-de', action='store_true', help="If specified, this argument tells ccAutomaton to delete the specified Environment.", default=None)
    parser.add_argument('-dc', action='store_true', help="If specified, this argument tells ccAutomaton to delete the specified Control Resources.", default=None)
    parser.add_argument('-dn', '--domainName', help="The domain name of the Control Resources of the Environment you want to use. If requesting to run jobs, delete an Environment or delete Control Resources this argument specifies which Control Resource should be used to perform the requested actions.", default=None)
    parser.add_argument('-jr', '--jobsToRun', help="A list of job scripts or workflow templates (with options specified) to be run on the specified environment.", default=None)
    parser.add_argument('-en', '--environmentName', help="The name of the Environment that you wish to use to fulfill your requests.", default=None)
    parser.add_argument('-crn', '--controlResourceName', help="The name of the Control Resources that you wish to delete.", default=None)
    parser.add_argument('-r', '--region', help="The region where the Control Resources are located.", default=None)
    parser.add_argument('-p', '--profile', help="The profile to use for the Resource API.", default=None)
    parser.add_argument('-dff', '--deleteFromFile', help="Deletes your Environment, Control Node, and Control Resources", default=None)
    args = parser.parse_args()

    environmentType = args.environmentType
    configFilePath = args.configFilePath
    doAll = args.all
    createControl = args.cc
    createEnvironment = args.ce
    runJobs = args.rj
    deleteEnvironment = args.de
    deleteControl = args.dc
    dnsName = args.domainName
    jobsToRun = args.jobsToRun
    environmentName = args.environmentName
    controlResourceName = args.controlResourceName
    profile = args.profile
    deleteFromFile = args.deleteFromFile

    controlParameters = None
    ccEnvironmentParameters = None
    generalParameters = None
    userName = None
    password = None
    cloudType = None
    region = None
    firstName = None
    lastName = None
    pempath = None

    try:
        import botocore
        import boto3
        import paramiko
        import requests
        import googleapiclient
    except Exception as e:
        print("The use of ccAutomaton requires the botocore, boto3, paramiko, requests, and googleapiclient Python libraries to operate properly. These can be installed using pip via the following commands:")
        print("pip install botocore boto3 google-api-python-client paramiko requests")
        print("If you do not have pip installed it can be installed on most Linux Distributions as the python-pip package.")
        print("Please install the required libraries and try again.")
        sys.exit(0)

    if environmentType is None:
        # Check and see if there was an argument passed. If there was then we use that as the environment type
        try:
            environmentType = args[1]
        except Exception as e:
            print("You must specify an environment type when running the ccAutomaton utility. This can be done using the -et argument or by adding the environment type after the command.")
            sys.exit(0)

    # Read in configuration values from the ccAutomaton.conf file from the local directory
    parser = configparser.ConfigParser()
    try:
        parser.read(str(configFilePath))
    except Exception as e:
        print("There was a problem trying to read the configuration file specified.")
        print(''.join(traceback.format_stack()))
        sys.exit(0)

    sections = parser.sections()

    configurationFileParameters = {}
    for section in sections:
        configurationFileParameters[str(section)] = {}
        options = parser.options(section)
        for option in options:
            try:
                configurationFileParameters[str(section)][option] = parser.get(section, option)
            except Exception as e:
                print(e)
                configurationFileParameters[str(section)][option] = None

    # Check and see if the cloud type has been configured in the conf file
    try:
        cloudType = configurationFileParameters['General']['cloudtype']
        cloudType = cloudType[0].upper() + cloudType[1:]
        generalParameters = configurationFileParameters['General']
    except Exception as e:
        print(''.join(traceback.format_exc(e)))
        print("Unable to find the requested cloud type in the configuration file specified. Please check the file and be sure that there is a cloudtype field in the general section and try again.")
        sys.exit(0)

    # Check to see if email is enabled on job fails and cluster fails
    ###TODO Encrypt Password and use username as a key in a seperate file with utility to set it (KBW/JCE)
    try:
        emailParams = {}
        emailParams['email'] = configurationFileParameters['General']['email']
        emailParams['sender'] = configurationFileParameters['General']['sender']
        emailParams['sendpw'] = configurationFileParameters['General']['sendpw']
        emailParams['smtp'] = configurationFileParameters['General']['smtp']
    except Exception as e:
        print("Emails disabled\nNow continuing")
        emailParams = None
        pass

    # Get the profile to use for the resource creation (switches out which account to use)
    if profile is None:
        try:
            profile = configurationFileParameters[str(environmentType) + str(cloudType)]['profile']
        except Exception as e:
            # Profile is not required so if we don't find it we just move on
            pass

    # Check and make sure the user has supplied the username, password, firstname, and lastname for the Environment to be created.
    try:
        userName = configurationFileParameters['UserInfo']['username']
    except Exception as e:
        print("Unable to find the username in the configuration file specified. Please check the file and be sure that there is a username field in the UserInfo section and try again.")
        sys.exit(0)

    try:
        password = configurationFileParameters['UserInfo']['password']
    except Exception as e:
        print("Unable to find the user password in the configuration file specified. Please check the file and be sure that there is a password field in the UserInfo section and try again.")
        sys.exit(0)

    try:
        firstName = configurationFileParameters['UserInfo']['firstname']
    except Exception as e:
        print("Unable to find the firstname in the configuration file specified. Please check the file and be sure that there is a firstname field in the UserInfo section and try again.")

    try:
        lastName = configurationFileParameters['UserInfo']['lastname']
    except Exception as e:
        print("Unable to find the lastname in the configuration file specified. Please check the file and be sure that there is a lastname field in the UserInfo section and try again.")

    try:
        pempath = configurationFileParameters['UserInfo']['pempath']
    except Exception as e:
        print("Unable to find the pempath(file path to your pemkey) in the configuration file specified.  Please check the file and be sure that there is a pempath field in the UserInfo section and try again.")

    if environmentName is None:
        try:
            environmentName = configurationFileParameters['General']['environmentname']
        except Exception as e:
            print("Unable to find the environment name in the configuration file specified. Please check the file and be sure that there is a environmentname field in the general section and try again.")
            sys.exit(0)

    stagesToRun = []
    if doAll:
        # We need to run all the steps in the pipeline.
        stagesToRun = ["cc", "ce", "rj", "de", "dc"]
    else:
        if createControl:
            stagesToRun.append("cc")
        if createEnvironment:
            stagesToRun.append("ce")
        if runJobs:
            stagesToRun.append("rj")
        if deleteEnvironment:
            stagesToRun.append("de")
        if deleteControl:
            stagesToRun.append("dc")
        if deleteFromFile:
            stagesToRun.append("dff")

    # If not creating the Control Resources we need to make sure the DNSName is not None
    if "cc" not in stagesToRun:
        # If the dnsName is None check to see if one is specified in the config file
        if dnsName is None:
            try:
                f = open('infoFile', 'r')
                lines = list(f)
                for x in lines:
                    if "controlDNS=" in x:
                        print("DNS found in file")
                        location = x.index('=')
                        controlDNS = x[location+1:]
                        dnsName = controlDNS.strip()
                        break
                print("dnsName is " + str(dnsName))
                if "controlDNS=" in x:
                    print("Success")
                else:
                    dnsName = configurationFileParameters['General']['dnsname']
            except Exception as e:
                print("Unable to find the DNS name for the Control Resources to be used to fulfill the request. Please check the configuration file and be sure that there is a dnsname field in the general section or specify the DNS name using the -dn commandline argument and try again.")
                sys.exit(0)

    # Need to create different environment objects depending on what we are running.
    if "cc" in stagesToRun:
        # Check and see if the requested environment/cloud type is configured in the conf file
        try:
            controlParameters = configurationFileParameters[str(environmentType) + str(cloudType)]
        except Exception as e:
            print("controlParameters are "+str(controlParameters))
            print("Unable to find the configuration for the " + str(environmentType) + str(cloudType) + " environment type in the configuration file. Please check and make sure there is a " + str(environmentType) + str(cloudType) + " section in the configuration file and try again.")
            sys.exit(0)

        if region is None:
            try:
                region = configurationFileParameters[str(environmentType) + str(cloudType)]['region']
            except Exception as e:
                print("Unable to find the region for the Control Resources. Please check the configuration file and be sure that there is a region field in the " + str(environmentType) + str(cloudType) + " section or specify the region using the -r commandline argument and try again.")
                sys.exit(0)

    if "ce" in stagesToRun:
        # Check and see if the environment name has been configured in the conf file if not passed in
        try:
            ccEnvironmentParameters = configurationFileParameters[str(environmentType) + "Environment"]
        except Exception as e:
            print("Unable to find the environment configuration in the configuration file specified. Please check the file and be sure that there is a " + str(environmentType) + "Environment section in the configuration file and try again.")
            sys.exit(0)

        try:
            ccEnvironmentParameters['templatename']
        except Exception as e:
            print("Unable to find the template name in the configuration file specified. Please check the file and be sure that there is a templatename field in the " + str(environmentType) + "Environment section in the configuration file and try again.")
            sys.exit(0)

    if "rj" in stagesToRun:
        # If the dnsName is None check to see if one is specified in the config file
        if jobsToRun is None:
            try:
                jobsToRun = configurationFileParameters['Computation']
                jobList = []
                for x in jobsToRun:
                    jobList.append({x: jobsToRun[x]})
                jobList = sorted(jobList)
                #print "jobsToRun is "
                #print jobsToRun
            except Exception as e:
                print("Unable to find the jobs to run. Please check the configuration file and be sure that there is a Computation section or specify the jobs to run using the -jr commandline argument and try again.")
                sys.exit(0)

    if "dc" in stagesToRun:
        if "cc" not in stagesToRun:
            if str(cloudType).lower() == "aws":
                if controlResourceName is None:
                    try:
                        controlResourceName = configurationFileParameters['General']['controlresourcename']
                    except Exception as e:
                        print("Unable to find the name for the Control Resources to delete. Please check the configuration file and be sure that there is a controlresourcename field in the General section or specify the name using the -crn commandline argument and try again.")
                        sys.exit(0)

        if region is None:
            try:
                region = configurationFileParameters[str(environmentType) + str(cloudType)]['region']
            except Exception as e:
                print("Unable to find the region for the Control Resources. Please check the configuration file and be sure that there is a region field in the " + str(environmentType) + str(cloudType) + " section or specify the region using the -r commandline argument and try again.")
                sys.exit(0)

    if "dff" in stagesToRun:
        if region is None:
            try:
                region = configurationFileParameters[str(environmentType) + str(cloudType)]['region']
            except Exception as e:
                print("Unable to find the region for the Control Resources. Please check the configuration file and be sure that there is a region field in the " + str(environmentType) + str(cloudType) + " section or specify the region using the -r commandline argument and try again.")
                sys.exit(0)

    # First we need to create the Environment Object that we will be using for the resource/environment/job creation
    kwargs = {"environmentType": str(environmentType), "name": str(environmentName), "cloudType": cloudType, "userName": userName, "password": password, "controlParameters": controlParameters, "ccEnvironmentParameters": ccEnvironmentParameters, "generalParameters": generalParameters, "dnsName": dnsName, "controlResourceName": controlResourceName, "region": region, "profile": profile, "firstName": firstName, "lastName": lastName, "pempath": pempath}

    # Load the module (ex: import cloudycluster)
    environmentClass = __import__(str(environmentType).lower())

    # Get the actual class that we need to instantiate (ex: from cloudycluster import CloudyCluster)
    myClass = getattr(environmentClass, environmentType)

    # Instantiate the class with the required parameters
    environment = myClass(**kwargs)
    # print parameters defined in the class
    #attrs = vars(environment)
    #print ', '.join("%s: %s" % item for item in attrs.items())

    if "cc" in stagesToRun:
        if os.path.isfile('infoFile'):
            os.remove('infoFile')
        if str(cloudType).lower() == "aws":
            resourceName = str(environment.name) + "ControlResources-" + str(uuid.uuid4())[:4]
        elif str(cloudType).lower() == "gcp":
            resourceName = str(environment.name) + "-" + str(uuid.uuid4())[:4]
        environment.controlResourceName = resourceName
        if str(cloudType).lower() == "aws":
            f = open('infoFile', 'w')
            f.write("controlResources="+str(resourceName)+"\n")
            f.close()

        # Had to make an alternate path right here for aws and gcp.  The AWS path creates a Cloud Formation Stack using a CFT.  Currently, we don't use anything anagalous to the CFT with GCP, therefore we only need to summon a Control Node.

        if str(cloudType).lower() == "aws":
            print("Now creating the Control Resources. The Control Resources will be named: " + str(resourceName))
            kwargs = {"templateLocation": environment.controlParameters['templatelocation'], "resourceName": resourceName}
            values = environment.createControl(**kwargs)
            if values['status'] != "success":
                moosage = "There was an error creating the Control Resources"; print(moosage)
                try:
                    error = values['payload']['error']; print(error)
                except Exception as e:
                    error = "N/A"
                try:
                    traceb = values['payload']['traceback']; print(traceb)
                except Exception as e:
                    traceb = "N/A"
                if emailParams:
                    missive = moosage + "\n\n\n" + "Your Error was:  \n\n" + error + "Your Traceback was:  \n\n" + traceb + "\n\n\n"
                    response = tidings.main(emailParams['sender'], emailParams['smtp'], emailParams['sendpw'], emailParams['email'], missive)
                sys.exit(0)
            else:
                print("Finished creating the Control Resources, the new DNS address is: " + values['payload'] + ". You may now log in with the username/password that were provided in the configuration file in the UserInfo section.")
                f = open('infoFile', 'a')
                f.write('controlDNS='+str(environment.dnsName)+"\n")
                f.close()
        elif str(cloudType).lower() == "gcp":
            #  Just need instance type and image ID for Google Cloud (JCE)
            print("Now creating the Control Node for Google Cloud")
            kwargs = {"templateLocation": None, "resourceName": resourceName}
            values = environment.createControl(**kwargs)
            if values['status'] != "success":
                moosage = "There was an error creating the Control Node"; print(moosage)
                try:
                    error = values['payload']['error']; print(error)
                except Exception as e:
                    error = "N/A"
                try:
                    traceb = values['payload']['traceback']; print(traceb)
                except Exception as e:
                    traceb = "N/A"
                if emailParams:
                    missive = moosage + "\n\n\n" + "Your Error was:  \n\n" + error + "Your Traceback was:  \n\n" + traceb + "\n\n\n"
                    response = tidings.main(emailParams['sender'], emailParams['smtp'], emailParams['sendpw'], emailParams['email'], missive)
                sys.exit(0)

    if "ce" in stagesToRun:
        print("Getting session to Control Resource.")
        if environment.sessionCookies is None:
            environment.getSession()
        print("Now creating the Environment named: " + str(environmentName) + ".")
        values = environment.createEnvironment()
        print("VALUES ARE")
        print(values)
        if values['status'] != "success":
            moosage = "There was an error creating the Environment."; print(moosage)
            try:
                error = values['error']; print(error)
            except Exception as e:
                error = "N/A"
            try:
                traceb = values['traceback']; print(traceb)
            except Exception as e:
                traceb = "N/A"
            if emailParams:
                missive = moosage + "\n\n\n" + "Your Error was:  \n\n" + error + "Your Traceback was:  \n\n" + traceb + "\n\n\n"
                response = tidings.main(emailParams['sender'], emailParams['smtp'], emailParams['sendpw'], emailParams['email'], missive)
            sys.exit(0)
        else:
            print("Successfully finished creating the Environment named: " + str(environment.name) + ".")
            f = open('infoFile', 'a')
            f.write("envName="+str(environment.name)+"\n")
            f.close()

        environmentName = environment.name

    if "rj" in stagesToRun:
        print("Getting session to Control Resource.")
        if environment.sessionCookies is None:
            environment.getSession()

        if environmentName is None or str(environmentName) == "":
            print("In order to execute job scripts or workflows on the Environment properly the full Environment name is required. This looks like <environment_name>-XXXX, please specify the full Environment name using the -en commandline argument or by specifying the environmentName field in the General section of the configuration file.")
            sys.exit(0)

        if "-" not in str(environmentName):
            print("In order to execute job scripts or workflows on the Environment properly the full Environment name is required. This looks like <environment_name>-XXXX, please specify the full Environment name using the -en commandline argument or by specifying the environmentName field in the General section of the configuration file.")
            sys.exit(0)

        for x in range(len(jobList)):
            for jobToRun in jobList[x]:
                tempObj = {}
                if "workflow" in jobToRun:
                    print("Running workflow")
                    try:
                        tempObj = json.loads(jobList[x][jobToRun])
                    except Exception as e:
                        print("The configuration of the workflow is not in a valid format. Please check the format and try again.")
                        sys.exit(0)
                    workflowType = tempObj['type']

                    # Create the scheduler object that can be used by the workflows
                    try:
                        schedulerModule = __import__(str(tempObj['options']['schedulerType']).lower())
                        # Get the actual class that we need to instantiate (ex: from cloudycluster import CloudyCluster)
                        schedulerClass = getattr(schedulerModule, str(tempObj['options']['schedulerType'][0].upper() + tempObj['options']['schedulerType'][1:]))
                        kwargs = {"schedType": tempObj['options']['schedulerType']}
                        scheduler = schedulerClass(**kwargs)
                    except Exception as e:
                        print("Unable to create an instance of the scheduler class for the schedulerType: " + str(tempObj['schedulerType']) + ". Please make sure the schedulerType is specified properly.")
                        print("The traceback is: " + ''.join(traceback.format_exc()))
                        sys.exit(0)

                    # Create CCQ scheduler object if requsted by workflow
                    ccqScheduler = None
                    if str(tempObj['options']['useCCQ']).lower() == "true":
                        schedType = "ccq"
                        try:
                            ccqSchedulerModule = __import__(schedType)
                            # Get the actual class that we need to instantiate (ex: from cloudycluster import CloudyCluster)
                            ccqSchedulerClass = getattr(ccqSchedulerModule, str(schedType[0].upper() + schedType[1:]))
                            kwargs = {"schedType": schedType}
                            ccqScheduler = ccqSchedulerClass(**kwargs)
                        except Exception as e:
                            print("Unable to create an instance of the scheduler class for the schedulerType: " + str(tempObj['options']['schedulerType']) + ". Please make sure the schedulerType is specified properly.")
                            print("The traceback is: " + ''.join(traceback.format_exc()))
                            sys.exit(0)

                    # It is a workflow that we will run via the script in the WorkflowTemplates directory
                    kwargs = {"name": tempObj['name'], "wfType": workflowType, "options": tempObj['options'], "schedulerType": tempObj['options']['schedulerType'], "environment": environment, "scheduler": scheduler, "ccq": ccqScheduler}
                    try:
                        module = __import__(str(workflowType))
                        workflowClass = getattr(module, str(workflowType[0].upper() + workflowType[1:]))
                        workflow = workflowClass(**kwargs)
                    except Exception as e:
                        print("Unable to create an instance of the workflow class for the workflow type: " + str(workflowType) + ". Please make sure the workflowType is specified properly.")
                        print("The traceback is: " + ''.join(traceback.format_exc()))
                        sys.exit(0)

                    values = workflow.run()
                    if values['status'] != "success":
                        moosage = "The execution of the workflow: " + str(jobToRun) + " failed."; print(moosage)
                        try:
                            error = values['payload']['error']; print(error)
                        except Exception as e:
                            error = "N/A"
                        try:
                            traceb = values['payload']['traceback']; print(traceb)
                        except Exception as e:
                            traceb = "N/A"
                        if emailParams:
                            missive = moosage + "\n\n\n" + "Your Error was:  \n\n" + error + "Your Traceback was:  \n\n" + traceb + "\n\n\n"
                            response = tidings.main(emailParams['sender'], emailParams['smtp'], emailParams['sendpw'], emailParams['email'], missive)
                    else:
                        # The return from the run() method should provide a payload field that provides the arguments for the monitor method
                        values = workflow.monitor(**values['payload'])
                        if values['status'] != "success":
                            moosage = "The monitoring of the workflow: " + str(jobToRun) + " failed."; print(moosage)
                            try:
                                error = values['payload']['error']; print(error)
                            except Exception as e:
                                error = "N/A"
                            try:
                                traceb = values['payload']['traceback']; print(traceb)
                            except Exception as e:
                                traceb = "N/A"
                            if emailParams:
                                missive = moosage + "\n\n\n" + "Your Error was:  \n\n" + error + "Your Traceback was:  \n\n" + traceb + "\n\n\n"
                                response = tidings.main(emailParams['sender'], emailParams['smtp'], emailParams['sendpw'], emailParams['email'], missive)

                elif "jobscript" in jobToRun:
                    print("Running jobScript")
                    tempObj = {}
                    try:
                        tempObj = json.loads(jobList[x][jobToRun])
                    except Exception as e:
                        print("The configuration of the workflow is not in a valid format. Please check the format and try again.")
                        sys.exit(0)

                    try:
                        schedulerType = tempObj['options']['schedulerType']
                        schedulerOptions = ""
                        if str(schedulerType).lower() not in environment.supportedSchedulers:
                            for scheduler in environment.supportedSchedulers:
                                schedulerOptions += str(scheduler)
                            return {"status": "error", "payload": {"error": "The scheduler type specified is not supported. Please choose one of the following scheduler types: " + str(schedulerOptions)}}
                    except Exception as e:
                        tempObj['options']['schedulerType'] = "ccq"

                    kwargs = {"name": tempObj['name'], "options": tempObj['options'], "schedulerType": tempObj['options']['schedulerType'], "environment": environment}
                    import jobScript
                    newJobScript = jobScript.JobScript(**kwargs)
                    values = newJobScript.processJobScript()
                    if values['status'] != "success":
                        jobName = values['jobId']
                        enviroName = values['environment']
                        moosage = "Your Environment: " + enviroName + "\nYour job ID: " + jobName + "\nThe execution of the jobscript : " + str(jobToRun) + " failed."; print(moosage)
                        try:
                            error = values['payload']['error']; print(error)
                        except Exception as e:
                            error = "N/A"
                        try:
                            traceb = values['payload']['traceback']; print(traceb)
                        except Exception as e:
                            traceb = "N/A"
                        if emailParams:
                            missive = moosage + "\n\n\n" + "Your Error was:  \n\n" + error + "Your Traceback was:  \n\n" + traceb + "\n\n\n"
                            response = tidings.main(emailParams['sender'], emailParams['smtp'], emailParams['sendpw'], emailParams['email'], missive)
                    else:
                        print(values)
                else:
                    print("No workflow or jobScript found in conf file")
                    sys.exit(0)

    if "de" in stagesToRun:
        print("Getting session to Control Resource.")
        if environment.sessionCookies is None:
            environment.getSession()

        print("Deleting the Environment named " + str(environmentName) + ".")
        values = environment.deleteEnvironment()
        if values['status'] != "success":
            moosage = "There was an issue deleting the environment: " + environmentName; print(moosage)
            try:
                error = values['payload']['error']; print(error)
            except Exception as e:
                error = "None"
            try:
                traceb = values['payload']['traceback']; print(traceb)
            except Exception as e:
                traceb = "None"
            if emailParams:
                missive = moosage + "\n\n\n" + "Your Error was:  \n\n" + error + "Your Traceback was:  \n\n" + traceb + "\n\n\n"
                response = tidings.main(emailParams['sender'], emailParams['smtp'], emailParams['sendpw'], emailParams['email'], missive)
            sys.exit(0)
        else:
            print("The Environment named " + str(environment.name) + " have been successfully deleted.")

    if "dc" in stagesToRun:
        print("Getting session to Control Resource.")
        if environment.sessionCookies is None:
            environment.getSession()
        print("Deleting the Control Resources named " + str(environment.controlResourceName) + ".")
        values = environment.deleteControl()
        if values['status'] != "success":
            moosage = "There was an issue deleting the Control Resource: " + environment.controlResourceName; print(moosage)
            try:
                error = values['payload']['error']; print(error)
            except Exception as e:
                error = "None"
            try:
                traceb = values['payload']['traceback']; print(traceb)
            except Exception as e:
                traceb = "None"
            if emailParams:
                missive = moosage + "\n\n\n" + "Your Error was:  \n\n" + error + "Your Traceback was:  \n\n" + traceb + "\n\n\n"
                response = tidings.main(emailParams['sender'], emailParams['smtp'], emailParams['sendpw'], emailParams['email'], missive)
        else:
            if str(cloudType).lower() == "aws":
                print("The Control Resources named " + str(environment.controlResourceName) + " have been successfully deleted.")
            elif str(cloudType).lower() == "gcp":
                print("The Control Node was succesfully deleted.")

    if "dff" in stagesToRun:
        if str(cloudType).lower() != "aws":
            print("Delete from file is not currently implemented for this cloud service.")
            sys.exit(0)
        print("Deleting the Environment and Control Resource")
        environment.name = None
        f = open('infoFile', 'r')
        lines = list(f)
        for x in lines:
            if "controlResources=" in x:
                location = x.index('=')
                environment.controlResourceName = x[location+1:].strip()
                print("controlResourcename is \n"+str(environment.controlResourceName))
            ### Ask BP about this.
            # if "controlDNS=" in x:
            #     location = x.index('=')
            #     controlDNS = x[location+1:]
            #     environment.dnsName = controlDNS
            if "envName=" in x:
                location = x.index('=')
                environment.name = x[location+1:].strip()
                environmentName = environment.name
        if environment.sessionCookies is None:
            environment.getSession()
        print(environment.name)
        if environment.name != None:
            print("Deleting the Environment named " + str(environmentName) + ".")
            values = environment.deleteEnvironment()
            if values['status'] != "success":
                moosage = "There was an error deleting the Environment: " + environmentName; print(moosage)
                try:
                    error = values['payload']['error']; print(error)
                except Exception as e:
                    error = "None"
                try:
                    traceb = values['payload']['traceback']; print(traceb)
                except Exception as e:
                    error = "None"
                if emailParams:
                    missive = moosage + "\n\n\n" + "Your Error was:  \n\n" + error + "Your Traceback was:  \n\n" + traceb + "\n\n\n"
                    response = tidings.main(emailParams['sender'], emailParams['smtp'], emailParams['sendpw'], emailParams['email'], missive)
                sys.exit(0)
            else:
                print("The Environment named " + str(environmentName) + " have been successfully deleted.")

        if environment.controlResourceName:
            print("Deleting the Control Resources named " + str(environment.controlResourceName) + ".")
            values = environment.deleteControl()
            if values['status'] != "success":
                moosage = "There was an issue deleting the control resources named: " + str(environment.controlResourceName)
                try:
                    error = values['payload']['error']; print(error)
                except Exception as e:
                    error = "None"
                try:
                    traceb = values['payload']['traceback']; print(traceb)
                except Exception as e:
                    traceb = "None"
                if emailParams:
                    missive = moosage + "\n\n\n" + "Your Error was:  \n\n" + error + "Your Traceback was:  \n\n" + traceb + "\n\n\n"
                    response = tidings.main(emailParams['sender'], emailParams['smtp'], emailParams['sendpw'], emailParams['email'], missive)
            else:
                print("The Control Resources named " + str(environment.controlResourceName) + " have been successfully deleted.")

    sys.exit(0)


main()

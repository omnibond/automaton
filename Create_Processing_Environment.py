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

#import emailScript as tidings
import configparser

sys.path.append(os.path.dirname(os.path.realpath(__file__))+str("/Schedulers"))
sys.path.append(os.path.dirname(os.path.realpath(__file__))+str("/Resources"))
sys.path.append(os.path.dirname(os.path.realpath(__file__))+str("/Environments"))
sys.path.append(os.path.dirname(os.path.realpath(__file__))+str("/WorkflowTemplates"))
sys.path.append(os.path.dirname(os.path.realpath(__file__))+str("/JobScriptTemplates"))

import jobScript

def main():
    parser = argparse.ArgumentParser(description="A utility that users can utilize to setup and create a CloudyCluster Control Node.")
    parser.add_argument('-V', '--version', action='version', version='ccAutomaton (version 1.0)')
    parser.add_argument('-et', '--environmentType', help="The type of environment to create.", default=None)
    parser.add_argument('-all', action='store_true', help="Run the entire process: create Control Resources, create an Environment, submit the specified jobs, and upon job completion delete the Environment and the Control Resources.", default=None)
    parser.add_argument('-cf', '--configFilePath', help="The path to the configuration file to be used by ccAutomaton. The default is the ccAutomaton.conf file in the local directory.", default="ccAutomaton.conf")
    parser.add_argument('-cc', action='store_true', help="If specified, this argument tells ccAutomaton to create new Control Resources.", default=None)
    parser.add_argument('-ce', action='store_true', help="If specified, this argument tells ccAutomaton to create a new Environment.", default=None)
    parser.add_argument('-rj', action='store_true', help="If specified, this argument tells ccAutomaton to run the jobs specified in the configuration file.", default=None)
    parser.add_argument("-nd", action="store_true", help="In combination with -all, does not delete the Environment or the Control Resources.")
    parser.add_argument('-de', action='store_true', help="If specified, this argument tells ccAutomaton to delete the specified Environment.", default=None)
    parser.add_argument('-dc', action='store_true', help="If specified, this argument tells ccAutomaton to delete the specified Control Resources.", default=None)
    parser.add_argument('-dn', '--domainName', help="The domain name of the Control Resources of the Environment you want to use. If requesting to run jobs, delete an Environment or delete Control Resources this argument specifies which Control Resource should be used to perform the requested actions.", default=None)
    parser.add_argument('-jr', '--jobsToRun', help="A list of job scripts or workflow templates (with options specified) to be run on the specified environment.", default=None)
    parser.add_argument('-en', '--environmentName', help="The name of the Environment that you wish to use to fulfill your requests.", default=None)
    parser.add_argument('-crn', '--controlResourceName', help="The name of the Control Resources that you wish to delete.", default=None)
    parser.add_argument('-r', '--region', help="The region where the Control Resources are located.", default=None)
    parser.add_argument('-p', '--profile', help="The profile to use for the Resource API.", default=None)
    parser.add_argument('-dff', '--deleteFromFile', action='store_true', help="Deletes your Environment, Control Node, and Control Resources", default=None)
    args = parser.parse_args()

    environmentType = args.environmentType
    configFilePath = args.configFilePath
    doAll = args.all
    noDelete = args.nd
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
        sys.exit(1)

    if environmentType is None:
        # Check and see if there was an argument passed. If there was then we use that as the environment type
        try:
            environmentType = args[1]
        except Exception as e:
            print("You must specify an environment type when running the ccAutomaton utility. This can be done using the -et argument or by adding the environment type after the command.")
            sys.exit(1)

    # Read in configuration values from the ccAutomaton.conf file from the local directory
    parser = configparser.ConfigParser()
    try:
        parser.read(str(configFilePath))
    except Exception as e:
        print("There was a problem trying to read the configuration file specified.")
        print(''.join(traceback.format_stack()))
        sys.exit(1)

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
        sys.exit(1)

    # Check to see if email is enabled on job fails and cluster fails
    ###TODO Encrypt Password and use username as a key in a seperate file with utility to set it (KBW/JCE)
    #try:
    #    emailParams = {}
    #    emailParams['email'] = configurationFileParameters['General']['email']
    #    emailParams['sender'] = configurationFileParameters['General']['sender']
    #    emailParams['sendpw'] = configurationFileParameters['General']['sendpw']
    #    emailParams['smtp'] = configurationFileParameters['General']['smtp']
    #except Exception as e:
    
    print("Emails disabled\nNow continuing")
    emailParams = None

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
        sys.exit(1)

    try:
        password = configurationFileParameters['UserInfo']['password']
    except Exception as e:
        print("Unable to find the user password in the configuration file specified. Please check the file and be sure that there is a password field in the UserInfo section and try again.")
        sys.exit(1)

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
            sys.exit(1)

    stagesToRun = []
    if doAll and noDelete:
        stagesToRun = ["cc", "ce", "rj"]
    elif doAll and not noDelete:
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
                sys.exit(1)

    # Need to create different environment objects depending on what we are running.
    if "cc" in stagesToRun:
        # Check and see if the requested environment/cloud type is configured in the conf file
        try:
            controlParameters = configurationFileParameters[str(environmentType) + str(cloudType)]
        except Exception as e:
            print("controlParameters are "+str(controlParameters))
            print("Unable to find the configuration for the " + str(environmentType) + str(cloudType) + " environment type in the configuration file. Please check and make sure there is a " + str(environmentType) + str(cloudType) + " section in the configuration file and try again.")
            sys.exit(1)

        if region is None:
            try:
                region = configurationFileParameters[str(environmentType) + str(cloudType)]['region']
            except Exception as e:
                print("Unable to find the region for the Control Resources. Please check the configuration file and be sure that there is a region field in the " + str(environmentType) + str(cloudType) + " section or specify the region using the -r commandline argument and try again.")
                sys.exit(1)

    if "ce" in stagesToRun:
        # Check and see if the environment name has been configured in the conf file if not passed in
        try:
            ccEnvironmentParameters = configurationFileParameters[str(environmentType) + "Environment"]
        except Exception as e:
            print("Unable to find the environment configuration in the configuration file specified. Please check the file and be sure that there is a " + str(environmentType) + "Environment section in the configuration file and try again.")
            sys.exit(1)

        try:
            ccEnvironmentParameters['templatename']
        except Exception as e:
            print("Unable to find the template name in the configuration file specified. Please check the file and be sure that there is a templatename field in the " + str(environmentType) + "Environment section in the configuration file and try again.")
            sys.exit(1)

    if "rj" in stagesToRun:
        # If the dnsName is None check to see if one is specified in the config file
        if jobsToRun is None:
            try:
                jobsToRun = configurationFileParameters['Computation']
                jobList = []
                for x in jobsToRun:
                    jobList.append({x: jobsToRun[x]})
                #print "jobsToRun is "
                #print jobsToRun
            except Exception as e:
                print("Unable to find the jobs to run. Please check the configuration file and be sure that there is a Computation section or specify the jobs to run using the -jr commandline argument and try again.")
                sys.exit(1)

    if "dc" in stagesToRun:
        if "cc" not in stagesToRun:
            if str(cloudType).lower() == "aws":
                if controlResourceName is None:
                    try:
                        controlResourceName = configurationFileParameters['General']['controlresourcename']
                    except Exception as e:
                        print("Unable to find the name for the Control Resources to delete. Please check the configuration file and be sure that there is a controlresourcename field in the General section or specify the name using the -crn commandline argument and try again.")
                        sys.exit(1)

        if region is None:
            try:
                region = configurationFileParameters[str(environmentType) + str(cloudType)]['region']
            except Exception as e:
                print("Unable to find the region for the Control Resources. Please check the configuration file and be sure that there is a region field in the " + str(environmentType) + str(cloudType) + " section or specify the region using the -r commandline argument and try again.")
                sys.exit(1)

    if "dff" in stagesToRun:
        if region is None:
            try:
                region = configurationFileParameters[str(environmentType) + str(cloudType)]['region']
            except Exception as e:
                print("Unable to find the region for the Control Resources. Please check the configuration file and be sure that there is a region field in the " + str(environmentType) + str(cloudType) + " section or specify the region using the -r commandline argument and try again.")
                sys.exit(1)

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
        f = open('infoFile', 'w')
        f.write("controlResources="+str(resourceName)+"\n")
        f.close()

        # Had to make an alternate path right here for aws and gcp.  The AWS path creates a Cloud Formation Stack using a CFT.  Currently, we don't use anything anagalous to the CFT with GCP, therefore we only need to summon a Control Node.

        if str(cloudType).lower() == "aws":
            print("Now creating the Control Resources. The Control Resources will be named: " + str(resourceName))
            kwargs = {"templateLocation": environment.controlParameters['templatelocation'], "resourceName": resourceName}
            values = environment.createControl(**kwargs)
        elif str(cloudType).lower() == "gcp":
            #  Just need instance type and image ID for Google Cloud (JCE)
            print("Now creating the Control Node for Google Cloud")
            kwargs = {"templateLocation": None, "resourceName": resourceName}
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
            #if emailParams:
            #    missive = moosage + "\n\n\n" + "Your Error was:  \n\n" + error + "Your Traceback was:  \n\n" + traceb + "\n\n\n"
            #    response = tidings.main(emailParams['sender'], emailParams['smtp'], emailParams['sendpw'], emailParams['email'], missive)
            sys.exit(1)
        else:
            print("Finished creating the Control Resources, the new DNS address is: " + values['payload'] + ". You may now log in with the username/password that were provided in the configuration file in the UserInfo section.")
            f = open('infoFile', 'a')
            f.write('controlDNS='+str(environment.dnsName)+"\n")
            f.close()

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
            #if emailParams:
            #    missive = moosage + "\n\n\n" + "Your Error was:  \n\n" + error + "Your Traceback was:  \n\n" + traceb + "\n\n\n"
            #    response = tidings.main(emailParams['sender'], emailParams['smtp'], emailParams['sendpw'], emailParams['email'], missive)
            sys.exit(1)
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
            sys.exit(1)

        if "-" not in str(environmentName):
            print("In order to execute job scripts or workflows on the Environment properly the full Environment name is required. This looks like <environment_name>-XXXX, please specify the full Environment name using the -en commandline argument or by specifying the environmentName field in the General section of the configuration file.")
            sys.exit(1)

        jobs = []
        simultaneous_jobs = []
        for x in range(len(jobList)):
            for jobToRun in jobList[x]:
                try:
                    jobs.append((jobToRun, json.loads(jobList[x][jobToRun])))
                except json.decoder.JSONDecodeError:
                    print("The configuration of the job or workflow is not in valid format. Please check the format and try again.")
                    print("%s is not valid json." % jobList[x][jobToRun])
                    sys.exit(1)

        for job in jobs:
            name = job[0]
            job = job[1]

            if "workflow" in name:
                print("Running workflow")
                workflowType = job['type']

                # Create the scheduler object that can be used by the workflows
                try:
                    schedulerModule = __import__(str(job['options']['schedulerType']).lower())
                    # Get the actual class that we need to instantiate (ex: from cloudycluster import CloudyCluster)
                    schedulerClass = getattr(schedulerModule, str(job['options']['schedulerType'][0].upper() + job['options']['schedulerType'][1:]))
                    kwargs = {"schedType": job['options']['schedulerType']}
                    scheduler = schedulerClass(**kwargs)
                except Exception as e:
                    print("Unable to create an instance of the scheduler class for the schedulerType: " + str(job['schedulerType']) + ". Please make sure the schedulerType is specified properly.")
                    print("The traceback is: " + ''.join(traceback.format_exc()))
                    sys.exit(1)

                # Create CCQ scheduler object if requsted by workflow
                ccqScheduler = None
                if str(job['options']['useCCQ']).lower() == "true":
                    schedType = "ccq"
                    try:
                        ccqSchedulerModule = __import__(schedType)
                        # Get the actual class that we need to instantiate (ex: from cloudycluster import CloudyCluster)
                        ccqSchedulerClass = getattr(ccqSchedulerModule, str(schedType[0].upper() + schedType[1:]))
                        kwargs = {"schedType": schedType}
                        ccqScheduler = ccqSchedulerClass(**kwargs)
                    except Exception as e:
                        print("Unable to create an instance of the scheduler class for the schedulerType: " + str(job['options']['schedulerType']) + ". Please make sure the schedulerType is specified properly.")
                        print("The traceback is: " + ''.join(traceback.format_exc()))
                        sys.exit(1)

                # It is a workflow that we will run via the script in the WorkflowTemplates directory
                kwargs = {"name": job['name'], "wfType": workflowType, "options": job['options'], "schedulerType": job['options']['schedulerType'], "environment": environment, "scheduler": scheduler, "ccq": ccqScheduler}
                try:
                    module = __import__(str(workflowType))
                    workflowClass = getattr(module, str(workflowType[0].upper() + workflowType[1:]))
                    workflow = workflowClass(**kwargs)
                except Exception as e:
                    print("Unable to create an instance of the workflow class for the workflow type: " + str(workflowType) + ". Please make sure the workflowType is specified properly.")
                    print("The traceback is: " + ''.join(traceback.format_exc()))
                    sys.exit(1)

                values = workflow.run()
                if values['status'] != "success":
                    print("The execution of the workflow %s failed." % name)
                    try:
                        error = values['payload']['error']; print(error)
                    except Exception as e:
                        error = "N/A"
                    try:
                        traceb = values['payload']['traceback']; print(traceb)
                    except Exception as e:
                        traceb = "N/A"
                    #if emailParams:
                    #    missive = moosage + "\n\n\n" + "Your Error was:  \n\n" + error + "Your Traceback was:  \n\n" + traceb + "\n\n\n"
                    #    response = tidings.main(emailParams['sender'], emailParams['smtp'], emailParams['sendpw'], emailParams['email'], missive)
                else:
                    # The return from the run() method should provide a payload field that provides the arguments for the monitor method
                    values = workflow.monitor(**values['payload'])
                    if values['status'] != "success":
                        print("The execution of the workflow %s failed." % name)
                        try:
                            error = values['payload']['error']; print(error)
                        except Exception as e:
                            error = "N/A"
                        try:
                            traceb = values['payload']['traceback']; print(traceb)
                        except Exception as e:
                            traceb = "N/A"
                        #if emailParams:
                        #    missive = moosage + "\n\n\n" + "Your Error was:  \n\n" + error + "Your Traceback was:  \n\n" + traceb + "\n\n\n"
                        #    response = tidings.main(emailParams['sender'], emailParams['smtp'], emailParams['sendpw'], emailParams['email'], missive)

            elif "jobscript" in name:
                print("Running jobScript")

                try:
                    schedulerType = job['options']['schedulerType']
                    schedulerOptions = ""
                    if str(schedulerType).lower() not in environment.supportedSchedulers:
                        for scheduler in environment.supportedSchedulers:
                            schedulerOptions += str(scheduler)
                        return {"status": "error", "payload": {"error": "The scheduler type specified is not supported. Please choose one of the following scheduler types: " + str(schedulerOptions)}}
                except Exception as e:
                    job['options']['schedulerType'] = "ccq"

                jobMonitor = job["options"]["monitorJob"]
                if "true" in str(jobMonitor).lower():
                    kwargs = {"name": job['name'], "options": job['options'], "schedulerType": job['options']['schedulerType'], "environment": environment}
                    newJobScript = jobScript.JobScript(**kwargs)
                    values = newJobScript.processJobScript()
                    if "jobId" in values and "environment" in values:
                        print("Your Environment:", values["environment"])
                        print("Your job ID:", values["jobId"])
                    if values['status'] != "success":
                        print("The execution of the jobscript: %s failed." % job["name"])
                        try:
                            error = values['payload']['error']
                            print(error)
                        except Exception as e:
                            error = "N/A"
                        try:
                            traceb = values['payload']['traceback']
                            print(traceb)
                        except Exception as e:
                            traceb = "N/A"
                        print(values)
                        #if emailParams:
                        #    missive = moosage + "\n\n\n" + "Your Error was:  \n\n" + error + "Your Traceback was:  \n\n" + traceb + "\n\n\n"
                        #    response = tidings.main(emailParams['sender'], emailParams['smtp'], emailParams['sendpw'], emailParams['email'], missive)
                    else:
                        print("The execution of the jobscript: %s was successful." % job["name"])
                elif "false" in str(jobMonitor).lower():
                    simultaneous_jobs.append(job)

            else:
                print("No workflow or jobScript found in conf file")
                sys.exit(1)

        # at this point simultaneous_jobs is the list of jobs that we submit together
        # so it's time to submit them all
        jobIdDict = {}
        timeoutMax = -1
        timeElapsed = 0
        done = 0
        for job in simultaneous_jobs:
            kwargs = {"name": job['name'], "options": job['options'], "schedulerType": job['options']['schedulerType'], "environment": environment}
            newJobScript = jobScript.JobScript(**kwargs)
            values = newJobScript.processJobScript()
            jobIdDict[values["jobId"]] = newJobScript
            if job["options"]["timeout"] == 0:
                timeoutMax = 0
            if timeoutMax and job["options"]["timeout"] > timeoutMax:
                timeoutMax = job["options"]["timeout"]

        while done < len(simultaneous_jobs):
            if timeoutMax == 0 or timeoutMax > timeElapsed:
                timeElapsed += 120
                time.sleep(120)
                to_remove = []
                for jobId in jobIdDict:
                    values = jobIdDict[jobId].job_state(jobId, environment)
                    if values["status"] != "success":
                        print("job_state returned", values)
                        sys.exit(1)
                    jobState = values["payload"]["jobState"]
                    name = values["payload"]["jobName"]
                    if jobState == "Completed":
                        values = jobIdDict[jobId].download(jobId, name)
                        if values["status"] != "success":
                            print("The job %s encountered an error while downloading" % name)
                            print(values)
                        else:
                            print("%s job is complete." % name)
                        to_remove.append(jobId)
                    elif jobState == "Error":
                        print("%s job in error state." % name)
                        to_remove.append(jobId)
                    else:
                        print("The job %s is in the %s state" % (name, jobState))
                for jobId in to_remove:
                    del jobIdDict[jobId]
                    done += 1
            else:
                print("The time limit has been reached at %s seconds" % (timeElapsed))
                sys.exit(1)

            if done == 1:
                print("%d job is done." % done)
            elif done > 1:
                print("%d jobs are done" % done)
            else:
                print("No jobs are done")


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
            #if emailParams:
            #    missive = moosage + "\n\n\n" + "Your Error was:  \n\n" + error + "Your Traceback was:  \n\n" + traceb + "\n\n\n"
            #    response = tidings.main(emailParams['sender'], emailParams['smtp'], emailParams['sendpw'], emailParams['email'], missive)
            sys.exit(1)
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
            #if emailParams:
            #    missive = moosage + "\n\n\n" + "Your Error was:  \n\n" + error + "Your Traceback was:  \n\n" + traceb + "\n\n\n"
            #    response = tidings.main(emailParams['sender'], emailParams['smtp'], emailParams['sendpw'], emailParams['email'], missive)
        else:
            if str(cloudType).lower() == "aws":
                print("The Control Resources named " + str(environment.controlResourceName) + " have been successfully deleted.")
            elif str(cloudType).lower() == "gcp":
                print("The Control Node was successfully deleted.")

    if "dff" in stagesToRun:
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
                #if emailParams:
                #    missive = moosage + "\n\n\n" + "Your Error was:  \n\n" + error + "Your Traceback was:  \n\n" + traceb + "\n\n\n"
                #    response = tidings.main(emailParams['sender'], emailParams['smtp'], emailParams['sendpw'], emailParams['email'], missive)
                sys.exit(1)
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
                #if emailParams:
                #    missive = moosage + "\n\n\n" + "Your Error was:  \n\n" + error + "Your Traceback was:  \n\n" + traceb + "\n\n\n"
                #    response = tidings.main(emailParams['sender'], emailParams['smtp'], emailParams['sendpw'], emailParams['email'], missive)
            else:
                print("The Control Resources named " + str(environment.controlResourceName) + " have been successfully deleted.")

    sys.exit(0)


main()



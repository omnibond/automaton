# Copyright 2017
#
# Licensed under the Apache License, Version 2.0, <LICENSE-APACHE or
# http://apache.org/licenses/LICENSE-2.0> or the MIT license <LICENSE-MIT or
# http://opensource.org/licenses/MIT> or the LGPL, Version 2.0 <LICENSE-LGPLv2 or
# https://www.gnu.org/licenses/old-licenses/lgpl-2.0.txt>, at your option.
# This file may not be copied, modified, or distributed except according to those terms.


import os
import sys
import traceback
import time
from datetime import datetime
from workflow import Workflow

sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
sys.path.append(os.path.join(os.path.dirname(__file__), '../Schedulers'))


class TopicModelingPipeline(Workflow):
    def __init__(self, **kwargs):
        super(TopicModelingPipeline, self).__init__(**kwargs)

    def createSchedulerClass(self, schedulerType=None):
        try:
            if schedulerType is None:
                schedulerType = self.schedulerType
            schedulerModule = __import__(str(schedulerType).lower())
            # Get the actual class that we need to instantiate (ex: from cloudycluster import CloudyCluster)
            schedulerClass = getattr(schedulerModule, str(schedulerType[0].upper() + schedulerType[1:]))
            kwargs = {"schedType": schedulerType}
            scheduler = schedulerClass(**kwargs)
            return {'status': "success", "payload": scheduler}
        except Exception as e:
            return {"status": "error", "payload": {"error": "Unable to create an instance of the resource class for the schedulerType: " + str(self.schedulerType) + ". Please make sure the schedulerType is specified properly.", "traceback": ''.join(traceback.format_exc())}}

    def run(self):
        startTime = time.time()
        submitTime = str(datetime.now()).replace(":", "-").replace(".", "-").replace(" ", "-")
        splitSubmitTime = submitTime.split("-")
        jobPrefixString = str(splitSubmitTime[1]) + str(splitSubmitTime[2]) + str(splitSubmitTime[3]) + str(splitSubmitTime[4])

        # Check to see if the user specified a submitInstantly tag and if they did not set it to False
        try:
            submitInstantly = self.options['submitInstantly']
            if str(submitInstantly).lower() != "true" and str(submitInstantly).lower() != "false":
                return {"status": "error", "payload": {"error": "Unable to find a valid submitInstantly value in the configuration. Please make sure that if there is a submitInstantly option defined in the configuration that the value is True or False. If this option is not specified the default value is False.", "traceback": ''.join(traceback.format_stack())}}
        except Exception as e:
            self.options['submitInstantly'] = "False"

        try:
            s3BucketName = self.options['s3BucketName']
        except Exception as e:
            return {"status": "error", "payload": {"error": "Unable to find the S3 Bucket name that is required for this workflow. Please make sure that there is an s3Bucket field inside the options object in the workflow configuration and try again.", "traceback": ''.join(traceback.format_stack())}}

        try:
            self.options['sharedFilesystemPath']
        except Exception as e:
            return {"status": "error", "payload": {"error": "Unable to find the shared filesystem path that is required for this workflow. Please make sure that there is an sharedFilesystemPath field inside the options object in the workflow configuration and try again.", "traceback": ''.join(traceback.format_stack())}}
        # Validate all the ccq parameters if we are going to use ccq
        try:
            if str(self.options['useCCQ']).lower() == "true":
                try:
                    self.options['spotPrice']
                except Exception as e:
                    return {"status": "error", "payload": {"error": "In order to utilize Spot Instances you must specify the instance types you wish to use. Please make sure that there is an requestedInstanceTypes field inside the workflow configuration and try again.", "traceback": ''.join(traceback.format_stack())}}
                if self.options['spotPrice'] is not None:
                    try:
                        self.options['requestedInstanceTypes']
                    except Exception as e:
                        return {"status": "error", "payload": {"error": "In order to utilize Spot Instances you must specify the instance types you wish to use. Please make sure that there is an requestedInstanceTypes field inside the workflow configuration and try again.", "traceback": ''.join(traceback.format_stack())}}
                    try:
                        self.options['schedulerToUse']
                    except Exception as e:
                        return {"status": "error", "payload": {"error": "Unable to find the scheduler to use which is required for this workflow. Please make sure that there is an schedulerToUse field in the workflow configuration object and try again.", "traceback": ''.join(traceback.format_stack())}}

                if str(self.environment.environmentType) != "CloudyCluster":
                    return {"status": "error", "payload": {"error": "In order to utilize CCQ you must be using the CloudyCluster environment type. Please check the -et argument specified and try again.", "traceback": ''.join(traceback.format_stack())}}

                try:
                    self.options['useSpotFleet']
                    if self.options['useSpotFleet']:
                        try:
                            self.options['spotFleetTotalSize']
                        except Exception as e:
                            return {"status": "error", "payload": {"error": "In order to utilize Spot Fleet Instances you must specify the total spot fleet size you wish to use. Please make sure that there is an spotFleetTotalSize field inside the options object in the workflow configuration and try again.", "traceback": ''.join(traceback.format_stack())}}

                        try:
                            self.options['spotFleetType']
                        except Exception as e:
                            return {"status": "error", "payload": {"error": "In order to utilize Spot Fleet Instances you must specify the type of spot fleet that you wish to use. Please make sure that there is an spotFleetType field inside the options object in the workflow configuration and try again.", "traceback": ''.join(traceback.format_stack())}}

                        try:
                            self.options['spotFleetWeights']
                        except Exception as e:
                            spotFleetWeights = ""
                            # If no weights are specified then we need to make them all 1 just like ccqsub
                            for instance in self.options['requestedInstanceTypes']:
                                spotFleetWeights += "1,"
                            self.options['spotFleetWeights'] = spotFleetWeights[:len(spotFleetWeights)-1]
                            return {"status": "error", "payload": {"error": "In order to utilize Spot Fleet Instances you must specify the type of spot fleet that you wish to use. Please make sure that there is an spotFleetType field inside the options object in the workflow configuration and try again.", "traceback": ''.join(traceback.format_stack())}}

                except Exception as e:
                    # We are not using Spot Fleet so set the variables to False and None for later
                    self.options['useSpotFleet'] = "false"
                    self.options['spotFleetType'] = "None"
                    self.options['spotFleetTotalSize'] = "None"
                    self.options['spotFleetWeights'] = ""

        except Exception as e:
            # We are not using ccq so we do not need to validate these parameters
            pass

        try:
            self.options['terminateInstantly']
        except Exception as e:
            self.options['terminateInstantly'] = "False"

        try:
            self.options['skipProvisioning']
        except Exception as e:
            self.options['skipProvisioning'] = "False"

        values = self.obtainWorkflowConfiguration()
        if values['status'] != "success":
            return {"status": "error", "payload": values['payload']}
        else:
            experimentConfiguration = values['payload']
            values = self.createJobScript(experimentConfiguration['numNodes'], experimentConfiguration['numCores'], experimentConfiguration['memory'], experimentConfiguration['numGpus'], experimentConfiguration['datasetName'], experimentConfiguration['method'], experimentConfiguration['settingsFileContent'], experimentConfiguration['wallTime'], experimentConfiguration['methodCores'], experimentConfiguration['methodNodes'], experimentConfiguration['executePath'], submitTime, jobPrefixString, s3BucketName)
            if values['status'] != "success":
                return {"status": "error", "payload": values['payload']}
            else:
                jobScriptText = values['payload']['jobScriptText']
                jobScriptLocation = values['payload']['jobScriptLocation']
                jobName = values['payload']['jobName']

                # We need to send the variables to CCQ to generate the ccqParameters for job submission if the workflow is using ccq.
                try:
                    if str(self.options['useCCQ']).lower() == "true":
                        values = self.createSchedulerClass("ccq")
                        if values['status'] != "success":
                            return {"status": "error", "payload": values['payload']}
                        else:
                            ccqScheduler = values['payload']
                            networkTypeRequested = "default"
                            if self.options['spotPrice'] is not None:
                                useSpot = "yes"
                            else:
                                useSpot = "no"
                            values = ccqScheduler.generateCcqSubmitParameters(experimentConfiguration['numNodes'], experimentConfiguration['numCores'], self.options['requestedInstanceTypes'], useSpot, self.options['spotPrice'], networkTypeRequested, self.options['schedulerToUse'], self.schedulerType, jobScriptText, jobScriptLocation, self.options['useSpotFleet'], self.options['spotFleetType'], self.options['spotFleetTotalSize'], self.options['terminateInstantly'], self.options['skipProvisioning'], self.options['submitInstantly'], self.options['spotFleetWeights'])
                            if values['status'] != "success":
                                return {"status": "error", "payload": values['payload']}
                            else:
                                ccOptionsParsed = values['payload']['ccOptionsParsed']
                                jobMD5Hash = values['payload']['jobMD5Hash']
                                values = self.environment.getApiKey()
                                if values['status'] != "success":
                                    return {"status": "error", "payload": values['payload']}
                                else:
                                    apiKey = values['payload']
                                    # This only works for CC but we can only use CCQ if we are using CC so that's ok
                                    values = self.environment.getLoginInstanceDomainName()
                                    if values['status'] != "success":
                                        return {"status": "error", "payload": values['payload']}
                                    else:
                                        loginDomain = values['payload']
                                        print("Made it to submit")
                                        jobObj = {"jobScriptText": jobScriptText, "ccOptionsParsed": ccOptionsParsed, "jobMD5Hash": jobMD5Hash, "jobScriptLocation": jobScriptLocation + str(jobName), "jobName": str(jobName)}
                                        values = ccqScheduler.submitJob(self.environment.sessionCookies, jobObj, apiKey, loginDomain)
                                        if values['status'] != "success":
                                            return {"status": "error", "payload": values['payload']}
                                        else:
                                            jobId = values['payload']['jobId']
                                            print("The job has been successfully submitted to ccq in the CloudyCluster Environments. The new Job Id is: " + str(jobId))
                                            # We have successfully submitted the job to ccq the instances and experiments should be creating/running now. We now need to monitor the job's statuses to see when they finish
                                            jobCompleted = False
                                            print("Now monitoring the status of the CCQ job.")
                                            resourceTime = None
                                            while not jobCompleted:
                                                values = self.environment.monitorJob(jobId, apiKey, self.options['schedulerToUse'], loginDomain, False, jobPrefixString, self.schedulerType)
                                                if values['status'] != "success":
                                                    return {"status": "error", "payload": values['payload']}
                                                else:
                                                    if values['payload'] != "Running" or values['payload'] != "Submitted":
                                                        if resourceTime is None:
                                                            resourceTime = time.time()
                                                        # The job is no longer running and we need to take action accordingly
                                                        if values['payload'] == "Error":
                                                            # TODO print out the error message for the job here
                                                            print("There was an error running the job, the error is:")
                                                            print("Error printing not yet implemented yet.")
                                                            jobCompleted = True
                                                        elif values['payload'] == "Killed":
                                                            print("The job was killed before it completed successfully. This could be due to a spot instance getting killed.")
                                                            jobCompleted = True
                                                        elif values['payload'] == "Completed":
                                                            jobSubmitTime = time.time()
                                                            tempTime = jobSubmitTime - resourceTime
                                                            print("Resource creation took about: " + str(tempTime) + " seconds.")
                                                            print("The CCQ job has successfully completed.")
                                                            jobCompleted = True
                                                        else:
                                                            print("The job is still creating the requested resources, waiting two minutes before checking the status again.")
                                                            time.sleep(120)
                                                    else:
                                                        print("The job is still running, waiting two minutes before checking the status again.")
                                                        time.sleep(120)
                                            # Check the status of the jobs that are submitted by the experiment and exit when they finish properly.
                                            workflowJobsCompleted = False
                                            while not workflowJobsCompleted:
                                                time.sleep(30)
                                                values = self.environment.getJobState("all", apiKey, self.options['schedulerToUse'], loginDomain, True, jobPrefixString, self.schedulerType)
                                                if values['status'] != "success":
                                                    return {"status": "error", "payload": values['payload']}
                                                else:
                                                    if values['payload']:
                                                        workflowJobsCompleted = True
                                                        print("All of the jobs submitted by the workflow have completed.")
                                                    else:
                                                        print("The jobs submitted by the experiment are still running, checking again in 30 seconds.")
                                            endTime = time.time()
                                            tempTime = endTime - startTime
                                            print("Total time elapsed is: " + str(tempTime) + " seconds.")
                                            return {"status": "success", "payload": {}}
                except Exception as e:
                    print(e)
                    # Do not use CCQ and just submit the workflow to the local scheduler
                    pass
                # Need to implement local submit stuff here (don't really have that yet)
                print("Local submit is not yet implemented for this workflow.")
                return {"status": "error", "payload": {"error": "Local submit is not yet implemented for this workflow.", "traceback": ''.join(traceback.format_stack())}}

    def monitor(self):
         return {"status": "success", "payload": "Monitoring of the TopicModeling Custom workflow is implemented in the run method."}

    # Dynamically generate the job script to be submitted to ccq based on the parameters for the experiment
    def createJobScript(self, numNodes, numCores, memory, numGpus, datasetName, method, settingsFileContent, wallTime, methodCores, methodNodes, executePath, submitTime, jobPrefixString, s3BucketName):
        jobFileName = self.options['configFilePath'].split("/")
        if len(jobFileName) == 1:
            jobFileName = jobFileName[0].split("\\")

        jobFileName = jobFileName[len(jobFileName)-1] + "-" + str(submitTime)

        experimentName = jobFileName.split(".")[0] + "-" + str(submitTime)

        jobFileName = str(experimentName) + ".py"

        # Use this for MPICH
        mpiModuleText = "module add mpich/3.2/3.2"

        # Use this for OpenMPI
        #mpiModuleText = "module add openmpi/1.8.4/1.8.4"

        s3ObjectPrefixes = []
        for x in range(1):
            s3ObjectPrefixes.append(str(x) + str(int(x)+1) + str(experimentName))

        # Generate the appropriate scheduler header for the jobs to be submitted
        values = self.createSchedulerClass()
        if values['status'] != "success":
            return {"status": "error", "payload": values['payload']}
        else:
            scheduler = values['payload']
        values = scheduler.generateChildJobScriptHeader(methodNodes, methodCores, wallTime, jobPrefixString, str(self.options['sharedFilesystemPath']))
        if values['status'] != "success":
            return {"status": "error", "payload": values['payload']}
        else:
            baseHeaderText = values['payload']

        headerFileTexts = []
        for x in range(len(s3ObjectPrefixes)):
            headerFileText = ""
            try:
                if str(self.options['pullFromS3']).lower() == "true":
                    headerFileText += str(baseHeaderText) + """\naws s3 cp s3://""" + str(s3BucketName) + """/Job_Tarballs/""" + str(s3ObjectPrefixes[x]) + """/""" + str(experimentName) + """.tar.gz """ + str(self.options['sharedFilesystemPath']) + """\ntar -xzf """ + str(self.options['sharedFilesystemPath']) + """/""" + str(experimentName) + """.tar.gz\n"""
            except Exception as e:
                # If not specified we assume that the job is going to be running on the shared filesystem and does not need to tar up and extract
                pass

            # For now we are just adding in some random sleeps to make sure that not all the jobs hit the S3 object at once
            # This will be replaced later with a version that generates multiple items and then each job will go pull down one of generated items so they are not all pulling down the same one
            headerFileText += """\nr=$(( ( RANDOM % 500 )  + 1 ))\necho \\"Sleeping for \\$r seconds\\"\nsleep \\$r\n"""
            headerFileTexts.append(headerFileText)

        #Append the s3 directory path that we need
        settingsFileContent += "S3_PATH=\\\"s3://" + str(s3BucketName) + "/Datasets/" + str(datasetName) + "/" + str(method) + "/experiments/" + str(experimentName) + "\\\"\n"

        # Dynamically create the job script to pull down the correct data from S3, build the experiments, and then qsub the jobs
        values = scheduler.generateParentJobScriptHeader(numNodes, numCores, "48:00:00")
        if values['status'] != "success":
            return {"status": "error", "payload": values['payload']}
        else:
            jobScriptText = values['payload']

        jobScriptText = str(jobScriptText) + """
    export sharedFilesystem=\"""" + str(self.options['sharedFilesystemPath']) + """\"\n
    if [ ! -d \"$sharedFilesystem\" ]; then\n
    mkdir $sharedFilesystem\n
    fi\n
    cd $sharedFilesystem\n""" + str(mpiModuleText) + """\n
    if [ -d \"TopicModelingPipeline\" ]; then\n
      cd TopicModelingPipeline\n
      git pull https://github.com/groppcw/TopicModelingPipeline.git\n
      cd $sharedFilesystem
    else\n
      git clone https://github.com/groppcw/TopicModelingPipeline.git\n
      mv modifedTopicModelingPipeline TopicModelingPipeline
    fi\n
    if [ -d \"plda\" ]; then\n
      cd $sharedFilesystem/plda\n
      git pull https://github.com/openbigdatagroup/plda.git\n
      make all\n
      cd $sharedFilesystem\n
    else\n
      git clone https://github.com/openbigdatagroup/plda.git\n
      cd $sharedFilesystem/plda\n
      make all\n
      cd $sharedFilesystem\n
    fi\n

    if [ ! -d \"$sharedFilesystem/raw_data/""" + str(datasetName) + """\" ]; then\n
      mkdir -p $sharedFilesystem/raw_data/""" + str(datasetName) + """\n
      aws s3 sync s3://""" + str(s3BucketName) + """/Datasets/""" + str(datasetName) + """/ $sharedFilesystem/raw_data/""" + str(datasetName) + """/ --exclude \"*/*\"\n
    fi

    if [ ! -d \"$sharedFilesystem/methods/""" + str(method) + """/data/""" + str(datasetName) + """\" ]; then\n
      mkdir -p $sharedFilesystem/methods/""" + str(method) + """/data/""" + str(datasetName) + """\n
      aws s3 sync s3://""" + str(s3BucketName) + """/Datasets/""" + str(datasetName) + """/""" + str(method) + """/ $sharedFilesystem/methods/""" + str(method) + """/data/""" + str(datasetName) + """/ --exclude \"*/*\"\n
    fi

    mkdir -p $sharedFilesystem/methods/""" + str(method) + """/execution/descriptors/\n
    mkdir -p $sharedFilesystem/methods/""" + str(method) + """/execution/experiments/\n
    mkdir -p $sharedFilesystem/methods/""" + str(method) + """/execution/experiments/""" + str(experimentName) + """\n
    mkdir -p $sharedFilesystem/methods/""" + str(method) + """/data/""" + str(datasetName) + """\n

    cp $sharedFilesystem/TopicModelingPipeline/method/""" + str(method) + """/defaultSettings.py $sharedFilesystem/methods/""" + str(method) + """/execution/experiments/""" + str(experimentName) + """\n"""

        for x in range(len(s3ObjectPrefixes)):
            # Removing the part where we had it generate multiple header files to pull from different objects because the GA code isn't able to handle that
           jobScriptText += """echo \"""" + str(headerFileTexts[x]) + """\" > $sharedFilesystem/methods/""" + str(method) + """/execution/experiments/""" + str(experimentName) + """/header.sh\n"""# + str(x) + """\n"""

        jobScriptText += """echo \"""" + str(settingsFileContent) + """\" > $sharedFilesystem/methods/""" + str(method) + """/execution/descriptors/""" + str(jobFileName) + """\n
    cd $sharedFilesystem/methods/""" + str(method) + """/execution/\n
    python $sharedFilesystem/TopicModelingPipeline/method/""" + str(method) + """/expand_experiments.py descriptors/""" + str(jobFileName) + """\n"""

        # If the child jobs are going to try and pull from S3 we need to make a tarball and upload it to S3 so they can  get it
        try:
            jobScriptText += """tar -zcf /tmp/""" + str(experimentName) + """.tar.gz -C $sharedFilesystem .\n"""
            for prefix in s3ObjectPrefixes:
                if str(self.options['pullFromS3']).lower() == "true":
                    jobScriptText += """aws s3 cp /tmp/""" + str(experimentName) + """.tar.gz s3://""" + str(s3BucketName) + """/Job_Tarballs/""" + str(prefix) + "/" + str(experimentName) + """.tar.gz\n"""
        except Exception as e:
            # If not specified we assume that the job is going to be running on the shared filesystem and does not need to tar up and extract
            pass

        # After uploading the tarball we need to execute the script to submit all the jobs
        jobScriptText += """chmod +x """ + str(executePath) + """\n"""
        jobScriptText += """loop="true"
while [ "$loop" = "true" ]
do
  OUTPUT="$(sinfo 2>&1)"
  if [[ $OUTPUT == *"sinfo: error"* ]]; then
     sleep 10
  else
    """ + str(executePath) + """
    loop="false"
  fi
done""""""\n"""

        #tempFile = open("awsPipelineGeneratedJobScript.sh", "w")
        #tempFile.write(jobScriptText)
        #tempFile.close()

        # print "EXITED AFTER GENERATING THE JOB SCRIPT. USED FOR DEBUGGING topicModelingPipeline.py!"
        # sys.exit(0)

        jobName = str(datasetName) + "_" + str(method) + ".sh"

        # Return the generated job text and the object we built
        # Random location for jobScript location is so that CCQ doesn't think that the script is already on the local fs
        return {"status": "success", "payload": {"jobScriptText": jobScriptText, "jobScriptLocation": "/notlocal/itsremote/" + str(jobName), "jobName": str(jobName)}}

    # Read in the experiment_settings file and parse out the required information from it
    def obtainWorkflowConfiguration(self):
        numNodes = 0
        numCores = 0
        memory = 0
        numGpus = 0
        datasetName = ""
        method = ""
        wallTime = ""
        settingsFileContent = ""
        methodCores = None
        methodNodes = None
        settingsFile = open(str(self.options['configFilePath']), "r")
        for line in settingsFile:
            settingsFileContent += line.replace("\"", "\\\"")
            line = line.split("=")
            if len(line) > 0:
                if line[0] == "ARCH_NUM_NODES":
                    # We need one more instance than we need for the experiments for the management node that submits the other jobs
                    numNodes = int(line[1])
                elif line[0] == "ARCH_NUM_CORES":
                    numCores = int(line[1])
                # Header number of nodes per experiment and cores per experiment
                elif line[0] == "METHOD_NUM_NODES":
                    methodNodes = int(line[1])
                elif line[0] == "METHOD_NUM_CORES":
                    methodCores = int(line[1])
                elif line[0] == "ARCH_MEM":
                    memory = int(line[1]) * 1000
                elif line[0] == "ARCH_GPU":
                    numGpus = int(line[1])
                elif line[0] == "DATASET_NAME":
                    datasetName = line[1].replace("\n", "").replace("\"", "")
                elif line[0] == "METHOD":
                    method = str(line[1]).replace("\n", "").replace("\"", "")
                elif line[0] == "ARCH_WALLTIME":
                    wallTime = str(line[1]).replace("\n", "").replace("\"", "")
            else:
                pass

        if methodCores is None:
            settingsFileContent += "METHOD_NUM_CORES=" + str(numCores) + "\n"
            methodCores = numCores

        if methodNodes is None:
            settingsFileContent += "METHOD_NUM_NODES=" + str(numNodes) + "\n"
            methodNodes = numNodes

        # Add in shared filesystem info
        settingsFileContent += "FS_HOME=\\\"" + str(self.options['sharedFilesystemPath']) + "\\\"\n"

        # Add in the use spot fleet flag, required for determining if we need to run the code to check the number of processors or not.
        settingsFileContent += "USE_SPOTFLEET=\\\"" + str(self.options['useSpotFleet']) + "\\\"\n"

        # Add in setting to say where to put the script containing all the jobs to submit
        executePath = str(self.options['sharedFilesystemPath']) + "/jobSubmitScript.sh"
        settingsFileContent += "EXECUTE_PATH=\\\"" + str(executePath) + "\\\"\n"

        #Add in scheduler information here
        values = self.createSchedulerClass()
        if values['status'] != "success":
            return {"status": "error", "payload": values['payload']}
        else:
            scheduler = values['payload']
            schedulerCommands = scheduler.getCommands()['payload']
            try:
                settingsFileContent += "SUB_CMD=\\\"" + str(schedulerCommands['submit']) + "\\\"\n"
                settingsFileContent += "SUB_TYPE=\\\"" + str(self.schedulerType[0].upper() + self.schedulerType[1:]) + "\\\"\n"
            except Exception as e:
                return {"status": "error", "payload": {"error": "An unsupported scheduler type was specified.", "traceback": ''.join(traceback.format_exc())}}

        return {"status": "success", "payload": {"numNodes": numNodes, "numCores": numCores, "memory": memory, "numGpus": numGpus, "datasetName": datasetName, "method": method, "settingsFileContent": settingsFileContent, "wallTime": wallTime, "methodCores": methodCores, "methodNodes": methodNodes, "executePath": executePath}}

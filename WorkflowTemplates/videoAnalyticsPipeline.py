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


class VideoAnalyticsPipeline(Workflow):
    def __init__(self, **kwargs):
        super(VideoAnalyticsPipeline, self).__init__(**kwargs)

    def run(self):
        startTime = time.time()
        jobScriptLocation = str(self.options['trafficVisionDir'])
        jobName = "tv_job_generator.sh"

        if str(self.environment.environmentType) != "CloudyCluster":
            return {"status": "error", "payload": {"error": "In order to utilize CCQ you must be using the CloudyCluster environment type. Please check the -et argument specified and try again.", "traceback": ''.join(traceback.format_stack())}}

        # Submit the CCQ job that will create the SLURM jobs as well as create the Preemptible instances to execute those jobs
        values = self.scheduler.generateParentJobScriptHeader(tasksPerNode=1)
        if values['status'] != "success":
            return values
        else:
            headerText = values['payload']

        # Set the base directory for the other arguments
        baseDir = str(self.options['trafficVisionDir'])

        # Here we submit the first job that will run on a non-preemptible machine to ensure that the jobs all get submitted successfully
        # Then we will submit a timelimited job that will run for a maximum of 8 hours or until we kill the job. This will create all the worker instances

        # Generate the job script text that will be submitted to CCQ
        jobScriptText = str(headerText) + "date\npython " + str(baseDir) + str(self.options['jobGenerationScript']) + " " + str(self.options['clip_to_start_on']) + " " + str(self.options['clip_to_end_on']) + " " + str(self.options['trafficVisionDir']) + " " + str(self.options['jobPrefixString']) + " " + str(self.options['bucketListFile']) + " " + str(self.options['generatedJobScriptDir']) + " " + str(self.options['trafficVisionExecutable']) + "\ndate"

        initialJobOptions = {"numberOfInstancesRequested": 1, "requestedInstanceType": self.options['instanceType'], "submitInstantly": self.options['submitInstantly'], "usePreemptible": "False", "schedType": self.schedulerType, "schedulerToUse": self.options['schedulerToUse'], "skipProvisioning": self.options['skipProvisioning'], "maxIdle": "0"}
        values = self.ccq.generateCcqSubmitParameters(self.environment, jobScriptLocation, jobScriptText, initialJobOptions)
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
                    print "Made it to submit"
                    jobObj = {"jobScriptText": jobScriptText, "ccOptionsParsed": ccOptionsParsed, "jobMD5Hash": jobMD5Hash, "jobScriptLocation": jobScriptLocation, "jobName": str(jobName)}
                    values = self.ccq.submitJob(self.environment.sessionCookies, jobObj, apiKey, loginDomain)
                    if values['status'] != "success":
                        return {"status": "error", "payload": values['payload']}
                    else:
                        jobId = values['payload']['jobId']
                        print "The initial spawner job has been successfully submitted to ccq in the CloudyCluster Environments. The new Job Id is: " + str(jobId)
                        # Now we need to wait about 2 minutes before launching the job with the worker instances
                        time.sleep(120)

                        # Submit the worker instance spawner job to CCQ
                        options = {"numberOfInstancesRequested": self.options['numberOfInstances'], "requestedInstanceType": self.options['instanceType'], "submitInstantly": self.options['submitInstantly'], "usePreemptible": self.options['usePreemptibleInstances'], "schedType": self.schedulerType, "maintain": self.options['maintainPreemptibleSize'], "schedulerToUse": self.options['schedulerToUse'], "skipProvisioning": self.options['skipProvisioning'], "maxIdle": "0", "timeLimit": self.options['timeLimit'], "createPInstances": self.options['createPlaceholderInstances']}
                        values = self.ccq.generateCcqSubmitParameters(self.environment, jobScriptLocation, jobScriptText, options)
                        if values['status'] != "success":
                            return {"status": "error", "payload": values['payload']}
                        else:
                            ccOptionsParsed = values['payload']['ccOptionsParsed']
                            jobMD5Hash = values['payload']['jobMD5Hash']
                            jobObj = {"jobScriptText": jobScriptText, "ccOptionsParsed": ccOptionsParsed, "jobMD5Hash": jobMD5Hash, "jobScriptLocation": jobScriptLocation, "jobName": str(jobName)}
                            values = self.ccq.submitJob(self.environment.sessionCookies, jobObj, apiKey, loginDomain)
                            if values['status'] != "success":
                                return {"status": "error", "payload": values['payload']}
                            else:
                                jobId = values['payload']['jobId']
                                print "The worker instance spawner job has been successfully submitted to ccq in the CloudyCluster Environments. The new Job Id is: " + str(jobId)
                                return {"status": "success", "payload": {"jobId": jobId, "apiKey": apiKey, "loginDomain": loginDomain, "jobPrefixString": self.options['jobPrefixString'], "startTime": startTime}}

    def monitor(self, jobId, apiKey, loginDomain, jobPrefixString, startTime):
        # We have successfully submitted the job to ccq the instances and experiments should be creating/running now. We now need to monitor the job's statuses to see when they finish
        jobCompleted = False
        print "Now monitoring the status of the CCQ job."
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
                        print "There was an error running the job, the error is:"
                        print "Error printing not yet implemented yet."
                        jobCompleted = True
                    elif values['payload'] == "Killed":
                        print "The job was killed before it completed successfully. This could be due to a spot instance getting killed."
                        jobCompleted = True
                    elif values['payload'] == "Completed":
                        jobSubmitTime = time.time()
                        tempTime = jobSubmitTime - resourceTime
                        print "Resource creation took about: " + str(tempTime) + " seconds."
                        print "The CCQ job has successfully completed."
                        jobCompleted = True
                    else:
                        print "The job is still creating the requested resources, waiting two minutes before checking the status again."
                        time.sleep(120)
                else:
                    print "The job is still running, waiting two minutes before checking the status again."
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
                    print "All of the jobs submitted by the workflow have completed."
                else:
                    print "The jobs submitted by the experiment are still running, checking again in 30 seconds."
        endTime = time.time()
        tempTime = endTime - startTime
        print "Total time elapsed is: " + str(tempTime) + " seconds."
        return {"status": "success", "payload": "The workflow has successfully completed."}

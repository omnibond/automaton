# Copyright 2017
#
# Licensed under the Apache License, Version 2.0, <LICENSE-APACHE or
# http://apache.org/licenses/LICENSE-2.0> or the MIT license <LICENSE-MIT or
# http://opensource.org/licenses/MIT> or the LGPL, Version 2.0 <LICENSE-LGPLv2 or
# https://www.gnu.org/licenses/old-licenses/lgpl-2.0.txt>, at your option.
# This file may not be copied, modified, or distributed except according to those terms.


import traceback
import paramiko
import socket
import io
import time
import os
import sys
import requests
import subprocess
paramiko.util.log_to_file("paramiko.log")
class JobScript(object):
    def __init__(self, name, options, schedulerType, environment):
        self.name = name
        self.options = options
        self.schedulerType = schedulerType
        self.environment = environment

        # We will set these values later on
        self.loginDNS = None

    def createConnection(self, host, username, password, mfaToken, private_key):
        # TODO Need to implement the automated entry of the MFA token to make sure that this works with MFA but it should handle it.
        ssh_client = None
        self.transport = None
        sock = None
        port = 22
        if ':' in host:
            (host, port) = host.split(':')
            port = int(port)
        try:
            if private_key:

                # Auth the previous way (without MFA and the auth_interactive method)
                private_key = paramiko.rsakey.RSAKey.from_private_key(io.StringIO(private_key))

                ssh_client = paramiko.SSHClient()
                ssh_client.set_missing_host_key_policy(paramiko.client.AutoAddPolicy())

                ssh_client.connect(host, port=port, username=username, password=password, pkey=private_key, look_for_keys=False)
            else:
                # Auth using the auth_interactive method for MFA
                try:
                    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    sock.connect((host, port))
                except Exception as e:
                    print(('Connect failed: ' + str(e)))
                self.transport = paramiko.Transport(sock)
                try:
                    self.transport.start_client()
                except paramiko.SSHException:
                    print('*** SSH negotiation failed.')

                def handler(title, instructions, fields):
                    try:
                        if fields is None or len(fields) <= 0:
                            return []
                        elif "Password" in str(fields[0][0]):
                            return [password]
                        elif "MFA Token" in str(fields[0][0]):
                            return [mfaToken]
                    except Exception:
                        print(traceback.format_exc())

                if not self.transport.is_authenticated():
                    self.transport.auth_interactive(username, handler)
                if not self.transport.is_authenticated():
                    print('*** Authentication failed.')
                    self.transport.close()
        except paramiko.AuthenticationException:
            print("except 1")
            print(traceback.format_exc())
        except socket.error as xxx_todo_changeme:
            (value, message) = xxx_todo_changeme.args
            print("except 2")
            print(message)
        except Exception:
            print("except 3")
            print(traceback.format_exc())
        if not private_key:
            return {'status': "success"}
        else:
            self.transport = ssh_client.get_transport()
            return {'status': "success"}

    def createSftpSession(self):
        try:
            sftpSession = self.transport.open_sftp_client()
            return {"status": "success", "payload": sftpSession}
        except Exception as e:
            return {"status": "error", "payload": {"error": "There was a problem creating the SFTP session.", "traceback": ''.join(traceback.format_exc())}}

    def webDavUpload(self, **kwargs):
        try:
            dns = kwargs['dns']
            sharedDir = kwargs['sharedDir']
            filename = kwargs['filename']
            filepath = kwargs['filepath']
            userName = kwargs['userName']
            password = kwargs['password']
            print(kwargs)
            if '.sh' not in filename:
                filename = str(filename)+'.sh'
            url = "https://"+str(dns)+str(sharedDir)+"/"+str(filename)
            print(url)
            with open(str(filepath), 'rb') as f:
                file = f.read()
            response = requests.request('PUT', url, auth=(userName, password), allow_redirects=False, data=file)
            print(response.text)
        except Exception as e:
            print("Error uploading file with webdav protocol")
            print(e)
            pass

    def executeCommand(self, command):
        channel = self.transport.open_channel("session")
        channel.exec_command(command)
        channel.shutdown_write()
        values = self.getCommandOutput(channel)
        return values

    def getCommandOutput(self, channel):
        receiveWindowSize = 1024
        stdout, stderr = [], []

        try:
            # Until the command exits, read from its stdout and stderr
            channelLength = 1
            while int(channelLength) != 0:
                receivedStdout = channel.recv(receiveWindowSize)
                receivedStderr = channel.recv_stderr(receiveWindowSize)
                stdout.append(receivedStdout.decode())
                stderr.append(receivedStderr.decode())
                channelLength = len(receivedStdout)
            while not channel.exit_status_ready():
                time.sleep(5)
            exitCode = channel.recv_exit_status()
            stdout = ''.join(stdout)
            stderr = ''.join(stderr)
            return {"status": "success", "payload": {"stdout": stdout, "stderr": stderr, "exitCode": exitCode}}
        except Exception as e:
            return {"status": "error", "payload": {"error": "There was a problem getting the output from the command.", "traceback": ''.join(traceback.format_exc())}}

    def closeConnection(self, connection):
        try:
            connection.close()
            return {"status": "success", "payload": "Successfully closed the connection."}
        except Exception as e:
            return {"status": "error", "payload": {"error": "There was a problem closing the connection", "traceback": ''.join(traceback.format_exc())}}

    def monitor(self, jobId, scheduler, environment, schedulerName):
        timeElapsed = 0
        timeout = self.options['timeout']
        print("Now monitoring the status of the CCQ job. Your jobID is " + str(jobId))
        while True:
            print("It has been " + str(int(timeElapsed)/int(60)) + " minutes since the CCQ job launched.")
            values = scheduler.getJobStatus(environment, jobId, schedulerName, self.loginDNS)
            print("The job is in the %s state" % values["payload"]["jobState"])
            if values['status'] != "success":
                return values
            else:
                if values["payload"]["jobState"] != "Running" or values["payload"]["jobState"] != "Submitted":
                    # The job is no longer running and we need to take action accordingly
                    if values["payload"]["jobState"] == "Error":
                        # TODO implement the job error printing
                        return {"status": "error", "payload": {"error": "There was an error encountered when attempting to run the job. Please check the CloudyCluster UI for more information. This information can be found under the Administration Tab -> Errors.", "traceback": ''.join(traceback.format_stack())}}
                    elif values["payload"]["jobState"] == "Killed":
                        return {"status": "error", "payload": {"error": "The job was killed before it completed successfully. This could be due to a spot instance getting killed.", "traceback": ''.join(traceback.format_stack())}}
                    elif values["payload"]["jobState"] == "Completed":
                        return {"status": "success", "payload": "The CCQ job has successfully completed.", "jobName": values["payload"]["jobName"]}
                    else:
                        if timeout == 0 or timeElapsed < timeout:
                            timeElapsed += 120
                            time.sleep(120)
                            print("The job is still creating the requested resources, waiting two minutes before checking the status again.")
                        else:
                            print("The time limit has been reached at %s in the state %s" % (timeElapsed, values["payload"]["jobState"]))
                            sys.exit(1)

                else:
                    print("The job is still running, waiting one minute before checking the status again.")
                    timeElapsed += 60
                    time.sleep(60)

    def job_state(self, jobId, environment):
        return self.scheduler.getJobStatus(environment, jobId, self.schedulerName, self.loginDNS)

    def upload(self):
        if self.options['uploadProtocol'] == "sftp":
            # Do stuff for uploading via sftp
            # TODO Currently we don't support the PrivateKey or MFA for upload, we will need to do this later.

                # Create the sftp session for uploading via sftp
                values = self.createSftpSession()
                if values['status'] != "success":
                    return values
                else:
                    sftpSession = values['payload']
                    # Upload the job script to the server
                    try:
                        sftpSession.put(self.options['localPath'], self.options['remotePath'])
                        return {"status": "success", "payload": "The job script was successfully uploaded to the remote system."}
                    except Exception as e:
                        return {"status": "error", "payload": {"error": "There was a problem trying to upload the job script to the remote system.", "traceback": ''.join(traceback.format_exc())}}
        elif str(self.options['uploadProtocol']).lower() == "webdav":
            kwargs = {'userName': self.environment.userName, 'password': self.environment.password, 'dns':self.loginDNS, 'filepath': self.options['localPath'], 'remotepath': self.options['remotePath'], 'filename': self.name, 'sharedDir': self.options['executeDirectory']}
            #print "self.name is "+str(self.name)
            self.webDavUpload(**kwargs)
            return {"status": "success", "payload": "The job script was successfully uploaded to the remote system"}
        return {"status": "error", "payload": "Base JobScript Class method upload not implemented for JobScripts."}

    def submit(self):
        return {"status": "error", "payload": "Base JobScript Class method submit not implemented for JobScripts."}

    def validateJobScriptOptions(self):
        try:
            uploadScript = self.options['uploadScript']
            if str(uploadScript).lower() != "true" and str(uploadScript).lower() != "false":
                return {"status": "error", "payload": {"error": "Invalid option specified for the uploadScript parameter of the job script. Valid values are \"True\" and \"False\".", "traceback": ''.join(traceback.format_stack())}}
        except Exception:
            uploadScript = True

        if str(uploadScript).lower() == "true":
            try:
                localPath = self.options['localPath']
            except Exception:
                # The user didn't specify the location of the script so assume it is in the current directory
                currentDirectory = os.getcwd()
                localPath = str(currentDirectory) + str(self.name)
            self.options['localPath'] = localPath

            try:
                remotePath = self.options['remotePath']
            except Exception:
                # Default to the user's home directory if they do not specify an upload location
                remotePath = "/home/" + str(self.environment.userName)
            self.options['remotePath'] = remotePath

            try:
                uploadProtocol = self.options['uploadProtocol']
                if str(uploadProtocol).lower() != "sftp" and str(uploadProtocol).lower() != "webdav":
                    return {"status": "error", "payload": {"error": "Invalid upload protocol specified. The valid entries are \"sftp\" and \"webdav\".", "traceback": traceback.format_stack()}}
            except Exception:
                # Default to the user's home directory if they do not specify an upload location
                uploadProtocol = "sftp"
            self.options['uploadProtocol'] = uploadProtocol

        try:
            monitorJob = self.options['monitorJob']
            if str(monitorJob).lower() != "true" and str(monitorJob).lower() != "false":
                return {"status": "error", "payload": {"error": "Invalid option specified for the monitorJob parameter of the job script. Valid values are \"True\" and \"False\".", "traceback": ''.join(traceback.format_stack())}}
        except Exception:
            # If the user does not specify an option we assume that they want to monitor the job
            monitorJob = True

        try:
            executeDirectory = self.options['executeDirectory']
        except Exception:
            executeDirectory = "/home/" + str(self.environment.userName)

        # Update the options based upon the the defaults
        self.options['uploadScript'] = uploadScript
        self.options['executeDirectory'] = executeDirectory
        self.options['monitorJob'] = monitorJob

        return {"status": "success", "payload": "Successfully checked the job script parameters."}

    def download(self, jobId, jobName):
        # TODO Currently we don't support the PrivateKey or MFA for upload, we will need to do this later.
        # Create the sftp session for uploading via sftp
        values = self.createSftpSession()
        if values['status'] != "success":
            return values
        else:
            sftpSession = values['payload']
            # Download Output's .e and .o files to current directory
            # Create a wait loop to check if the files are in the current directory
            try:
                remote = jobName + jobId + ".e"
                local = self.options["directory"] + "/" + remote
                sftpSession.get(remote, local)
                print(f"Downloading {local} for job {jobName}")

                remote = jobName + jobId + ".o"
                local = self.options["directory"] + "/" + remote
                sftpSession.get(remote, local)
                print(f"Downloading {local} for job {jobName}")

                return {"status": "success", "payload": "The job script was successfully uploaded to the remote system."}
            except Exception:
                return {"status": "error", "payload": {"error": "There was a problem trying to download the job script to the remote system.", "traceback": ''.join(traceback.format_exc())}}


    def processJobScript(self):
        print("Now processing the job script: " + str(self.name))
        values = self.validateJobScriptOptions()
        if values['status'] != "success":
            return values

        # We will need to obtain the Login Instance's DNS name in order to submit the job via the web or commandline
        if self.loginDNS is None:
            values = self.environment.getJobSubmitDns()
            if values['status'] != "success":
                return values
            self.loginDNS = values['payload']
        
        values = self.createConnection(self.loginDNS, self.environment.userName, self.environment.password, None, None)
        if values['status'] != "success":
            return values
        
        # We have validated the parameters and retrieved the Login Instance DNS name. Moving on to actually uploading and submitting the job script.
        if not self.options['uploadScript']:
            return
        values = self.upload()
        if values['status'] != "success":
            return values

        # We successfully uploaded the file now we need to create a scheduler object based on the type of scheduler we are submitting to.
        values = self.environment.createSchedulerClass(self.options['schedulerType'])
        if values['status'] != "success":
            return values
        scheduler = values['payload']
        values = scheduler.getOrGenerateApiKey(self.environment)
        if values['status'] != "success":
            return values

        # Now that we have the correct authorization api key we can create the connection to the login instance and submit the job via the commandline or the web interface.
        values = scheduler.submitJobCommandLine(self.options['remotePath'], self)
        if values['status'] != "success":
            return values
        # We have successfully submitted the job, now we need to monitor the job if specified by the user
        print(values['payload'])
        jobId = values['payload']['jobId']
        schedulerName = values['payload']['schedulerName']

        self.scheduler = scheduler
        self.schedulerName = schedulerName
        # Now we monitor the job unless the user expressly states they do not want to monitor the job.
        if str(self.options['monitorJob']).lower() != "true":
            # The user chose not to monitor the job so we declare success and move on to processing the next jobscript
            values = {"status": "success", "payload": "The jobscript has been successfully submitted to the environment."}
            values['jobId'] = jobId
            values['environment'] = self.environment
            return values

        else:
            # We need to monitor the job and check for it's completion
            values = self.monitor(jobId, scheduler, self.environment, schedulerName)
            if values['status'] != "success":
                return values

            self.download(jobId, values["jobName"])
            # The jobscript has been submitted and completed so we just return the values of the monitoring function
            values['jobId'] = jobId
            values['environment'] = self.environment
            return values


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
        transport = None
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
                transport = paramiko.Transport(sock)
                try:
                    transport.start_client()
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
                    except Exception as e:
                        print(e.message)

                if not transport.is_authenticated():
                    transport.auth_interactive(username, handler)
                if not transport.is_authenticated():
                    print('*** Authentication failed.')
                    transport.close()
        except paramiko.AuthenticationException as e:
            print("except 1")
            print(e.message)
        except socket.error as xxx_todo_changeme:
            (value, message) = xxx_todo_changeme.args
            print("except 2")
            print(message)
        except Exception as e:
            print("except 3")
            print(e.message)
        if not private_key:
            return {'status': "success", "payload": transport}
        else:
            transport = ssh_client.get_transport()
            return {'status': "success", "payload": transport}

    def createSftpSession(self, transport):
        try:
            sftpSession = transport.open_sftp_client()
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

    def executeCommand(self, transport, command):
        channel = transport.open_channel("session")
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
        jobCompleted = False
        timeElapsed = 0
        print("Now monitoring the status of the CCQ job. Your jobID is " + str(jobId))
        while not jobCompleted:
            print("It has been " + str(int(timeElapsed)/int(60)) + " minutes since the CCQ job launched.")
            values = scheduler.getJobStatus(environment, jobId, schedulerName, self.loginDNS)
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
                        print("The job is still creating the requested resources, waiting two minutes before checking the status again.")
                        timeElapsed += 120
                        time.sleep(120)
                else:
                    print("The job is still running, waiting one minute before checking the status again.")
                    timeElapsed += 60
                    time.sleep(60)

    def upload(self):
        if self.options['uploadProtocol'] == "sftp":
            # Do stuff for uploading via sftp
            # TODO Currently we don't support the PrivateKey or MFA for upload, we will need to do this later.
            values = self.createConnection(self.loginDNS, self.environment.userName, self.environment.password, None, None)
            if values['status'] != "success":
                return values
            else:
                transport = values['payload']

                # Create the sftp session for uploading via sftp
                values = self.createSftpSession(transport)
                if values['status'] != "success":
                    return values
                else:
                    sftpSession = values['payload']
                    # Upload the job script to the server
                    try:
                        fileInfo = sftpSession.put(self.options['localPath'], self.options['remotePath'])
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
        values = self.createConnection(self.loginDNS, self.environment.userName, self.environment.password, None, None)
        if values['status'] != "success":
            return values
        else:
            transport = values['payload']

            # Create the sftp session for uploading via sftp
            values = self.createSftpSession(transport)
            if values['status'] != "success":
                return values
            else:
                sftpSession = values['payload']
                # Download Output's .e and .o files to current directory
                # Create a wait loop to check if the files are in the current directory
                try:
                    fileName = jobName + jobId + ".e"
                    fileInfo = sftpSession.get(fileName, fileName)
                    fileName = jobName + jobId + ".o"
                    fileInfo = sftpSession.get(fileName, fileName)
                    return {"status": "success", "payload": "The job script was successfully uploaded to the remote system."}
                except Exception as e:
                    return {"status": "error", "payload": {"error": "There was a problem trying to upload the job script to the remote system.", "traceback": ''.join(traceback.format_exc())}}


    def processJobScript(self):
        print("Now processing the job script: " + str(self.name))
        values = self.validateJobScriptOptions()
        if values['status'] != "success":
            return values
        else:
            # We will need to obtain the Login Instance's DNS name in order to submit the job via the web or commandline
            if self.loginDNS is None:
                values = self.environment.getJobSubmitDns()
                if values['status'] != "success":
                    return values
                else:
                    loginDns = values['payload']
                    self.loginDNS = loginDns

            # We have validated the parameters and retrieved the Login Instance DNS name. Moving on to actually uploading and submitting the job script.
            if self.options['uploadScript']:
                values = self.upload()
                if values['status'] != "success":
                    return values
                else:
                    # We successfully uploaded the file now we need to create a scheduler object based on the type of scheduler we are submitting to.
                    values = self.environment.createSchedulerClass(self.options['schedulerType'])
                    if values['status'] != "success":
                        return values
                    else:
                        scheduler = values['payload']
                        values = scheduler.getOrGenerateApiKey(self.environment)
                        if values['status'] != "success":
                            return values
                        else:
                            # Now that we have the correct authorization api key we can create the connection to the login instance and submit the job via the commandline or the web interface.
                            values = self.createConnection(self.loginDNS, self.environment.userName, self.environment.password, None, None)
                            if values['status'] != "success":
                                return values
                            else:
                                transport = values['payload']
                                values = scheduler.submitJobCommandLine(transport, self.options['remotePath'], self)
                                if values['status'] != "success":
                                    return values
                                else:
                                    # We have successfully submitted the job, now we need to monitor the job if specified by the user
                                    print(values['payload'])
                                    jobId = values['payload']['jobId']
                                    schedulerName = values['payload']['schedulerName']

                                    # Now we monitor the job unless the user expressly states they do not want to monitor the job.
                                    if str(self.options['monitorJob']).lower() == "true":
                                        # We need to monitor the job and check for it's completion
                                        values = self.monitor(jobId, scheduler, self.environment, schedulerName)
                                        self.download(jobId, values["jobName"])
                                        #Transfer output files to local if option is selected
                                        ### ********************** ############
                                        # try:
                                        #     if str(self.options['getOutput']).lower() == "true":
                                        #         # need ssh key key = 
                                        #         # need to scp files back
                                        #         # need jobid
                                        #         # need file path
                                        #         # need full command line to run locally
                                        #         commandline = "scp -i " + str(keyPath) + " " + str(self.environment.userName) + "@" + str(ipAddress) + ":~/" + str(outputName) + " /Output/"
                                        #         response = subprocess.check_output(commandline, shell=True)
                                        # except Exception as e:
                                        #     print "There was an error sending the output file back"
                                        #     print e

                                        # The jobscript has been submitted and completed so we just return the values of the monitoring function
                                        values['jobId'] = jobId
                                        values['environment'] = self.environment
                                        return values
                                    else:
                                        # The user chose not to monitor the job so we declare success and move on to processing the next jobscript
                                        return {"status": "success", "payload": "The jobscript has been successfully submitted to the environment."}

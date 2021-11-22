# Copyright 2017
#
# Licensed under the Apache License, Version 2.0, <LICENSE-APACHE or
# http://apache.org/licenses/LICENSE-2.0> or the MIT license <LICENSE-MIT or
# http://opensource.org/licenses/MIT> or the LGPL, Version 2.0 <LICENSE-LGPLv2 or
# https://www.gnu.org/licenses/old-licenses/lgpl-2.0.txt>, at your option.
# This file may not be copied, modified, or distributed except according to those terms.


import botocore
import os
import botocore.session
import time
import traceback
import sys
from resources import Resource
import boto3

sys.path.append(os.path.join(os.path.dirname(__file__), '..'))


class AwsResources(Resource):
    def __init__(self, **kwargs):
        super(AwsResources, self).__init__(**kwargs)

    def createBotocoreClient(self, service):
        try:
            session = botocore.session.Session(profile=self.profile)
            client = session.create_client(str(service), region_name=str(self.region))
            return {"status": "success", "payload": client}
        except Exception as e:
            print("Trying second method of getting a Botocore Session")
            pass
        try:
            session = botocore.session.get_session()
            client = session.create_client(str(service), region_name=str(self.region))
            return {"status": "success", "payload": client}
        except Exception as e:
            return {"status": "error", "payload": {"error": "There was an exception encountered when trying to obtain a Botocore session to" + str(service) + ".", "traceback": ''.join(traceback.format_exc())}}

    def getStartupKey(self, instance, options):
        try:
            client = self.createBotocoreClient("cloudformation")["payload"]
            correct_key = None
            counter = 0
            response = client.describe_stacks(StackName=self.stackId)
            for item in response["Stacks"]:
                for output in item["Outputs"]:
                    if "InstanceID" in output["OutputKey"]:
                        instance = output["OutputValue"]
            client = self.createBotocoreClient("ec2")["payload"]
            while not correct_key and counter < 5:
                request = client.describe_tags(Filters=[{"Name": "resource-id", "Values": [instance]}])
                for item in request["Tags"]:
                    if "startup_key" in item["Key"]:
                        return {"status": "success", "payload": item["Value"]}
                time.sleep(20)
                counter += 1
            if not correct_key:
                return {"status": "error", "payload": {"error": "startup_key not found", "traceback": "".join(traceback.format_stack())}}
        except Exception as e:
            return {"status": "error", "payload": {"error": "There was an error trying to get the startup key.", "traceback": ''.join(traceback.format_exc())}}

    def createControlResources(self, templateLocation, resourceName, options):
        #Create Cloud Formation Session
        client = None
        cftBody = ""
        print("About to get those parameters")
        parameters = [{'ParameterKey': 'KeyName', 'ParameterValue': str(options['keyname'])}, {'ParameterKey': 'InstanceType', 'ParameterValue': str(options['instancetype'])}, {'ParameterKey': 'NetworkCIDR', 'ParameterValue': str(options['networkcidr'])}, {'ParameterKey': 'vpc', 'ParameterValue': str(options['vpc'])}, {'ParameterKey': 'PublicSubnet', 'ParameterValue': str(options['publicsubnet'])}]
        capabilities = str(options['capabilities']).split(",")

        values = self.createBotocoreClient("cloudformation")
        if values['status'] != "success":
            return {"status": "error", "payload": values['payload']}
        else:
            client = values['payload']

        # Read in the CFT from the local filesystem to pass to Botocore
        try:
            with open(templateLocation, 'r') as myfile:
                cftBody = myfile.read().replace('\n', '')
        except Exception as e:
            return {"status": "error", "payload": {"error": "There was a problem trying to read the Cloud Formation Template from the provided location.", "traceback": ''.join(traceback.format_exc())}}

        if client is not None:
            try:
                response = client.create_stack(StackName=resourceName, TemplateBody=cftBody, Parameters=parameters, Capabilities=capabilities)
                print("The Cloud Formation Stack is now creating.")
                # Get the stack ID for use in getting the events of the stack
                for i in response:
                    if i == 'StackId':
                        self.stackId = response[i]
                return {"status": "success", "payload": self.stackId}
            except Exception as e:
                return {"status": "error", "payload": {"error": "Encountered an error when attempting to create the Cloud Formation Stack.", "traceback": ''.join(traceback.format_exc())}}
        else:
            return {"status": "error", "payload": {"error": "There was an exception encountered when trying to obtain a Botocore client to CloudFormation.", "traceback": ''.join(traceback.format_stack())}}

    def deleteControlResources(self, resourceId):
        print("RESOURCE Id is: " + str(resourceId))
        values = self.createBotocoreClient("cloudformation")
        if values['status'] != "success":
            return {"status": "error", "payload": values['payload']}
        else:
            client = values['payload']

        try:
            client.delete_stack(StackName=resourceId)
        except Exception as e:
            return {"status": "error", "payload": {"error": "There was an exception encountered when trying to delete the Cloud Formation Stack.", "traceback": ''.join(traceback.format_exc())}}

        values = self.monitorControlResources(resourceId, "deletion")
        if values['status'] != "success":
            return {"status": "error", "payload": values['payload']}
        else:
            return {"status": "success", "payload": "Successfully deleted the Cloud Formation Stack."}

    def monitorControlResources(self, resourceId, stateToFind):
        # If we successfully got the stackId
        status = None
        counter = 0
        resourceStatus = None
        resourceType = None
        maxTimeToWait = 600
        timeElapsed = 0
        timeToWait = 60
        done = False

        values = self.createBotocoreClient("cloudformation")
        if values['status'] != "success":
            return {"status": "error", "payload": values['payload']}
        else:
            client = values['payload']

        # Keep tracking the state until the Stack creation has either Completed or Failed.
        while not done:
            try:
                stackEvents = client.describe_stack_events(StackName=resourceId)
                stackDict = stackEvents['StackEvents'][0]
                resourceStatus = stackDict['ResourceStatus']
                resourceType = stackDict['ResourceType']
                try:
                    for dict in stackEvents["StackEvents"]:
                        if "ResourceStatusReason" in dict:
                            resourceStatusReason = dict["ResourceStatusReason"]
                except Exception as e:
                    resourceStatusReason = ""
                    print(traceback.format_exc())
                if resourceType == 'AWS::CloudFormation::Stack':
                    status = resourceStatus
                print("ResourceStatusReason 1 is ")
                print(resourceStatusReason)
                # If waiting for create we need to monitor the state of the Stack, if waiting for deletion we need to wait until the stack is gone
                if stateToFind == "creation":
                    if status == "CREATE_COMPLETE":
                        print("The Cloud Formation Stack has been created successfully.")
                        return {"status": "success", "payload": "The Cloud Formation Stack has been created successfully."}
                    elif status == "ROLLBACK_COMPLETE" or status == "ROLLBACK_FAILED":
                        print("ResourceStatusReason 2 is ")
                        print(resourceStatusReason)
                        return {"status": "error", "payload": {"error": "The Cloud Formation Template failed to launch properly. The error associated with the Cloud Formation Template is: " + str(resourceStatusReason), "traceback": ''.join(traceback.format_stack())}}
                    elif status == "CREATE_FAILED":
                        return {"status": "error", "payload": {"error": "The Cloud Formation Template failed to launch properly. The error associated with the Cloud Formation Template is: " + str(resourceStatusReason), "traceback": ''.join(traceback.format_stack())}}

                elif stateToFind == "deletion":
                    if status == "DELETE_COMPLETE":
                        return {"status": "success", "payload": "The Cloud Formation Stack has been deleted successfully."}
                    elif status == "DELETE_FAILED":
                        return {"status": "error", "payload": {"error": "The Cloud Formation Template failed to delete properly. The error associated with the Cloud Formation Template is: " + str(resourceStatusReason), "traceback": ''.join(traceback.format_stack())}}

            except Exception as e:
                print(traceback.format_exc())
                # If we are monitoring for the delete of the Stack then when it deletes we will get the stack not found exception and then we can return success. Otherwise it is an error and should be returned as such
                if stateToFind == "deletion":
                    if "Stack [" + str(resourceId) + "] does not exist" in ''.join(traceback.format_exc()):
                        print("The Cloud Formation Stack has been deleted successfully.")
                        return {"status": "success", "payload": "The Cloud Formation Stack has been deleted successfully."}

                return {"status": "error", "payload": {"error": "Encountered an error when attempting to monitor the Cloud Formation Stack.", "traceback": ''.join(traceback.format_exc())}}

            print("You have waited " + str(counter) + " minutes for the Control Resources to enter the requested state.")
            counter += 1
            if maxTimeToWait < timeElapsed:
                done = True
            time.sleep(timeToWait)
            timeElapsed += timeToWait
        if done:
            # We ran out of time waiting for the stack to come up so we print the error and exit
            return {"status": "error", "payload": {"error": "Encountered an error when attempting to monitor the Cloud Formation Stack. The Cloud Formation Stack did not reach the desired state before the timeout.", "traceback": ''.join(traceback.format_stack())}}

    def getValue(self, valueToGet, resourceId):
        #Get the output value from the Cloud Formation Stack Outputs sections
        #requestedValue = "InstanceIP"

        values = self.createBotocoreClient("cloudformation")
        if values['status'] != "success":
            return {"status": "error", "payload": values['payload']}
        else:
            client = values['payload']

        try:
            response = client.describe_stacks(StackName=resourceId)
            requestedValue = None
            y = response['Stacks'][0]['Outputs']
            for i in y:
                if valueToGet in i["OutputKey"]:
                    requestedValue = i['OutputValue']
                    return {"status": "success", "payload": requestedValue}
        except Exception as e:
            return {"status": "error", "payload": {"error": "Encountered an error when attempting to retrieve the value from the Cloud Formation Stack.", "traceback": ''.join(traceback.format_exc())}}

    def writeObjectsToDatabase(self, lookupTableObjectList, objectTableObjectList, lookupTableName, objectTableName):
        client = None
        lookupTable = None
        objectTable = None

        try:
            session = boto3.Session(profile_name=self.profile)
            client = session.resource('dynamodb', region_name=str(self.region))
        except Exception as e:
            return {"status": "success", "payload": {"error": "There was a problem obtaining the connection to DynamoDB.", "traceback": ''.join(traceback.format_exc())}}

        try:
            lookupTable = client.Table(str(lookupTableName))
            objectTable = client.Table(str(objectTableName))
        except Exception as e:
            return {"status": "success", "payload": {"error": "There was a problem connecting to the DynamoDB tables.", "traceback": ''.join(traceback.format_exc())}}

        try:
            with lookupTable.batch_writer() as batch:
                for item in lookupTableObjectList:
                    batch.put_item(Item=item)
        except Exception as e:
            return {"status": "success", "payload": {"error": "There was a problem adding the provided data to the Lookup DynamoDB table.", "traceback": ''.join(traceback.format_exc())}}

        try:
            with objectTable.batch_writer() as batch:
                for item in objectTableObjectList:
                    batch.put_item(Item=item)
        except Exception as e:
            return {"status": "success", "payload": {"error": "There was a problem adding the provided data to the Object DynamoDB table.", "traceback": ''.join(traceback.format_exc())}}

        return {"status": "success", "payload": "Successfully pre-populated the Lookup and Object database tables with the provided information."}

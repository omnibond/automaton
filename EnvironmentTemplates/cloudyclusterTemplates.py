# Copyright 2017
#
# Licensed under the Apache License, Version 2.0, <LICENSE-APACHE or
# http://apache.org/licenses/LICENSE-2.0> or the MIT license <LICENSE-MIT or
# http://opensource.org/licenses/MIT> or the LGPL, Version 2.0 <LICENSE-LGPLv2 or
# https://www.gnu.org/licenses/old-licenses/lgpl-2.0.txt>, at your option.
# This file may not be copied, modified, or distributed except according to those terms.


import os
import sys
import uuid
import ast
import traceback
import copy
import subprocess
import uuid
import math
from random import randint
from environmentTemplates import EnvironmentTemplate
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))


class CloudyClusterTemplate(EnvironmentTemplate):
    def __init__(self, **kwargs):
        super(CloudyClusterTemplate, self).__init__(**kwargs)

    def get(self):
        try:
            # Load the module (ex: import cloudycluster)
            sys.path.append(os.path.join(os.path.dirname(__file__), str(self.environmentType)))
            module = __import__(self.templateName)

            # Get the actual class that we need to instantiate (ex: from cloudycluster import CloudyCluster)
            template = module.template
            description = module.description
            self.template = template
            return {"status": "success", "payload": {"template": template, "description": description}}
        except Exception as e:
            return {"status": "error", "payload": {"error": "Unable to get the template specified.", "traceback": ''.join(traceback.format_exc())}}

    def create(self, cloudType):
        # Add the generic objects to the template and add the reminders to get default values from the user
        newTemplate = {'clusterError': 'none', 'clusterNumber': 1, 'RecType': 'Cluster', 'clusterSpunUp': 'false', 'rollback': {'status': 'none'}, 'ofa': '0.0.0.0/0', 'completed': 'true', 'hash_key': "<<CLUSTER_UUID>>", 'name': "<<CLUSTER_UUID>>", 'cid': "<<CLUSTER_UUID>>", 'pagesViewed': {'welcome': 'true', 'advanced': 'true', 'finalReview': 'true'}, 'clusterAction': {'status': 'none'}, 'roadTraveled': ['welcome', 'advanced', 'finalReview'], "clusterName": "<<CLUSTER_NAME>>", "efsEncryption": "true", 'schedulers': [], 's3': [], 'efs': [], 'computeGroups': [], 'webDavs': [], 'workingGroups': [], 'ccVersion': 'Current Version', "sharedHomeDirEnabled": "false", "Region": "<<REGION>>", "k": "<<KEY_NAME>>", "instanceAvailabilityZone": "<<INSTANCE_AVAILABILITY_ZONE>>"}

        #Instance specific objects so that they can be referenced separately
        validNatParameters = {"instanceType": "nit", "accessFrom": "naf", "volumeType": "VolumeType"}

        validClusterParameters = {"keyname": "k", "vpccidr": "vc", "az": "instanceAvailabilityZone", "region": "Region", "createAllEFSMountPoints": "createAllEFSMountPoints", "fschoice": "fsChoice"}

        validSchedulerParameters = {"instanceType": "sit", "ccq": "scalingType", "volumeType": "VolumeType", "name": "schedName", "type": "schedType", "schedAllocationType": "schedAllocationType", "fsChoice": "fsChoice"}

        validWebDavParameters = {"instanceType": "wdit", "name": "accessName", "volumeType": "VolumeType", "fsChoice": "fsChoice"}

        validFilesystemParameters = {"numberOfInstances": "ofs", "port": "op", "name": "fn", "filesystemId": "fid", "numberOfStandbyInstances": "fo", "filesystemSizeGB": "ebs", "storageVolumesPerInstance": "ebsNumber", "instanceType": "ofit", "volumeType": "VolumeType", "inputOutputOperationsPerSecond": 'iops', "encrypted": "enableEBSEncryption", "storageVolumeType": "storageVolumeType", "orangeFSIops": "orangeFSIops", "instanceIops": "instanceIops", "fsChoice": "fsChoice"}

        validComputeGroupParameters = {"numberOfInstances": "wfs", "instanceType": "wit", "name": "cgn", "volumeType": "VolumeType"}

        validEfsParameters = {"type": "type", "name": "efsName"}

        validS3Parameters = {"name": "s3Name", "encrypt": "s3Encryption"}

        validSchedulerTypes = ["Slurm", "Torque"]

        # Required attributes for each object type
        requiredNatParameters = {"instanceType", "accessFrom"}
        requiredClusterParameters = {"vpccidr"}
        requiredSchedulerParameters = {"instanceType", "name", "type", "fsChoice"}
        requiredWebDavParameters = {"instanceType", "name", "fsChoice"}
        requiredFilesystemParameters = {"numberOfInstances", "instanceType", "name", "filesystemSizeGB", "fsChoice"}
        requiredComputeGroupParameters = {"numberOfInstances", "instanceType", "name"}
        requiredEfsParameters = {"type"}
        requiredS3Parameters = {"name"}

        # Build the variable map of all the objects
        variableMap = {"Cluster": validClusterParameters, "schedulers": validSchedulerParameters, "webDavs":  validWebDavParameters, "workingGroups": validFilesystemParameters, "computeGroups": validComputeGroupParameters, "efs": validEfsParameters, "s3": validS3Parameters, "nat": validNatParameters}

        # Valid categories
        validCategories = ["scheduler", "login", "computegroup", "filesystem", "nat", "efs", "s3", "Cluster", "createAllEFSMountPoints"]

        # Check to see if createAllEFSMountpoints exists.  Needs to default to a string lower case false for GCP. 
        if "createAllEFSMountPoints" not in self.parameters:
            self.parameters['createAllEFSMountPoints'] = "false"

        # Here we need to take in the parameters specified in the ccAutomaton and parse them into the right format for Environment creation
        for param in self.parameters:
            # Check the parameters specified to make sure they are in the valid values list
            attrsToCheck = None
            targetCategory = ""
            if "scheduler" in param:
                category = "schedulers"
                targetCategory = "scheduler"
                attrsToCheck = validSchedulerParameters
            elif "login" in param:
                category = "webDavs"
                targetCategory = "login"
                attrsToCheck = validWebDavParameters
            elif "computegroup" in param:
                category = "computeGroups"
                targetCategory = "computegroup"
                attrsToCheck = validComputeGroupParameters
            elif "filesystem" in param:
                category = "workingGroups"
                targetCategory = "filesystem"
                attrsToCheck = validFilesystemParameters
            elif "nat" in param:
                category = "nat"
            elif "efs" in param:
                category = "efs"
                targetCategory = "efs"
                attrsToCheck = validEfsParameters
            elif "s3" in param:
                category = "s3"
                targetCategory = "s3"
                attrsToCheck = validS3Parameters
            else:
                category = "Cluster"
            try:
                if category == "Cluster" or category == "nat":
                    if category == "nat":
                        # If the object is a NAT instance then we need to treat it differently then the other objects because its attributes sit at the top level
                        newTemplate["hasNAT"] = "true"
                        tempObj = ast.literal_eval(self.parameters[param])
                        fixedObj = {}

                        # Check if the parameters required for NAT Instance are in the configuration.
                        if category == "nat":
                            for reqVar in requiredNatParameters:
                                if reqVar not in tempObj:
                                    print("The " + str(reqVar) + " attribute is required when specifying a NAT Instance. Please add the " + str(reqVar) + " to your NAT Instance configuration and try again.")
                                    sys.exit(1)

                        for item in tempObj:
                            if item in variableMap[category]:
                                fixedObj[variableMap[category][item]] = tempObj[item]
                            else:
                                # Only need to allow for entries that are in the map, shouldn't allow any arbitrary value to be added
                                validAttributes = ""
                                for entry in validNatParameters:
                                    validAttributes += str(entry) + ", "
                                print("The attribute: " + str(item) + " is not supported for the NAT Instance. The valid attributes for a NAT Instance configuration are: " + str(validAttributes[:-2]) + ".")
                                sys.exit(1)
                                #fixedObj[item] = tempObj[item]
                        for thing in fixedObj:
                            if thing in variableMap[category]:
                                newTemplate[variableMap[category][thing]] = fixedObj[thing]
                            else:
                                newTemplate[thing] = fixedObj[thing]

                        if "VolumeType" not in newTemplate:
                            if str(cloudType).lower() == "aws":
                                #newTemplate['VolumeType'] = "SSD"
                                newTemplate['VolumeType'] = "SSD"
                            elif str(cloudType).lower() == "gcp":
                                #newTemplate['VolumeType'] = "pd-ssd"
                                newTemplate['VolumeType'] = "pd-ssd"
                    else:
                        # If the attribute is a Cluster attribute then it is on the top level as well
                        if param in variableMap[category]:
                            newTemplate[variableMap[category][param]] = self.parameters[param]
                        else:
                            if param != "description":
                                # Only need to allow for entries that are in the map, shouldn't allow any arbitrary value to be added
                                validAttributes = ""
                                for entry in validClusterParameters:
                                    validAttributes += str(entry) + ", "
                                print("The attribute: " + str(param) + " is not supported for the Cluster configuration. The valid attributes for a Cluster configuration are: " + str(validAttributes[:-2]) + ".")
                                sys.exit(1)
                                #newTemplate[param] = self.parameters[param]

                else:
                    # The other objects Scheduler/Login/EFS/S3/Filesystem/Compute are all lists of dictionaries and we need to put the translated dictionaries into the appropriate list. But only if the dictionary is not empty

                    tempObj = ast.literal_eval(self.parameters[param])
                    for attr in tempObj:
                        if attr not in attrsToCheck:
                            # Only need to allow for entries that are in the map, shouldn't allow any arbitrary value to be added
                            validAttributes = ""
                            for entry in attrsToCheck:
                                validAttributes += str(entry) + ", "
                            print("The attribute: " + str(attr) + " is not supported for a " + str(targetCategory) + " configuration. The valid attributes for a " + str(targetCategory) + " configuration are: " + str(validAttributes[:-2]) + ".")
                            sys.exit(1)

                    fixedObj = {}
                    for item in tempObj:
                        if item == "ccq":
                            if str(tempObj[item]).lower() == "true":
                                # Use CCQ
                                fixedObj['scalingType'] = "autoscaling"
                            else:
                                fixedObj['scalingType'] = "fixed"
                        else:
                            if item in variableMap[category]:
                                fixedObj[variableMap[category][item]] = tempObj[item]
                            else:
                                fixedObj[item] = tempObj[item]

                    # Need to make sure the minimum object requirements are met
                    if category == "schedulers":
                        for reqVar in requiredSchedulerParameters:
                            if reqVar not in tempObj:
                                print("The " + str(reqVar) + " attribute is required when specifying a Scheduler Instance. Please add the " + str(reqVar) + " to your Scheduler Instance configuration and try again.")
                                sys.exit(1)

                    if category == "webDavs":
                        for reqVar in requiredWebDavParameters:
                            if reqVar not in tempObj:
                                print("The " + str(reqVar) + " attribute is required when specifying a Login Instance. Please add the " + str(reqVar) + " to your Login Instance configuration and try again.")
                                sys.exit(1)

                    if category == "computeGroups":
                        for reqVar in requiredComputeGroupParameters:
                            if reqVar not in tempObj:
                                print("The " + str(reqVar) + " attribute is required when specifying a Compute Group. Please add the " + str(reqVar) + " to your Compute Group configuration and try again.")
                                sys.exit(1)

                    if category == "workingGroups":
                        for reqVar in requiredFilesystemParameters:
                            if reqVar not in tempObj:
                                print("The " + str(reqVar) + " attribute is required when specifying a Filesystem. Please add the " + str(reqVar) + " to your Filesystem configuration and try again.")
                                sys.exit(1)

                    if category == "efs":
                        for reqVar in requiredEfsParameters:
                            if reqVar not in tempObj:
                                print("The " + str(reqVar) + " attribute is required when specifying an EFS filesystem. Please add the " + str(reqVar) + " to your EFS filesystem configuration and try again.")
                                sys.exit(1)

                    if category == "s3":
                        for reqVar in requiredS3Parameters:
                            if reqVar not in tempObj:
                                print("The " + str(reqVar) + " attribute is required when specifying an S3 bucket. Please add the " + str(reqVar) + " to your S3 Bucket configuration and try again.")
                                sys.exit(1)

                    if len(fixedObj) > 0:
                        # Set the default volume type to be SSD(AWS) or pd-ssd(GCP) for these types if not specified
                        if category == "schedulers" or category == "computeGroups" or category == "workingGroups" or category == "webDavs":
                            if "VolumeType" not in fixedObj:
                                if str(cloudType).lower() == "aws":
                                    fixedObj['VolumeType'] = "SSD"
                                elif str(cloudType).lower() == "gcp":
                                    fixedObj['VolumeType'] = "pd-ssd"
                            # Making sure GCP is getting the proper name for the ssd if someone forgets
                            if "VolumeType" in fixedObj and str(cloudType) == "gcp":
                                if fixedObj['VolumeType'] == "SSD":
                                    fixedObj['VolumeType'] = "pd-ssd"
                        if category == "workingGroups":
                            if "storageVolumeType" not in fixedObj:
                                if str(cloudType).lower() == "aws":
                                    fixedObj['storageVolumeType'] = "SSD"
                                elif str(cloudType).lower() == "gcp":
                                    fixedObj['storageVolumeType'] = "pd-ssd"
                            if "storageVolumeType" in fixedObj and str(cloudType) == "gcp":
                                if fixedObj['storageVolumeType'] == "SSD":
                                    fixedObj['storageVolumeType'] = "pd-ssd"
                        # Populate defaults for the different categories
                        if category == "efs":
                            fixedObj['filesystemId'] = "pending"
                            if "type" in fixedObj:
                                if fixedObj['type'] == "sharedHome":
                                    newTemplate['sharedHomeDirEnabled'] = "true"
                                    fixedObj['efsName'] = "home"
                                elif fixedObj['type'] == "ssw":
                                    if "efsName" not in fixedObj:
                                        fixedObj['efsName'] = "efsapps"
                                    newTemplate['sswName'] = fixedObj['efsName']
                                elif fixedObj['type'] == "common":
                                    if "efsName" not in fixedObj:
                                        fixedObj['efsName'] = "efsdata"
                                    newTemplate['efsName'] = fixedObj['efsName']
                                else:
                                    print("Unsupported EFS type specified, the allowed values are: common, ssw, and sharedHome. Please correct your configuration file and try again.")
                                    sys.exit(1)
                            else:
                                # Default to shared storage if not specified
                                fixedObj['type'] = "common"
                                newTemplate['efsName'] = fixedObj['efsName']

                        if category == "computeGroups":
                            fixedObj['wmfs'] = fixedObj['wfs']
                            fixedObj['computeID'] = "<<COMPUTE_GROUP_ID>>"

                        if category == "schedulers":
                            if str(fixedObj['schedType']).lower() == "slurm":
                                fixedObj['schedType'] = "Slurm"
                            elif str(fixedObj['schedType']).lower() == "torque" or str(fixedObj['schedType']).lower() == "torque (pbs)":
                                fixedObj['schedType'] = "Torque"
                            else:
                                validSchedTypes = ""
                                for sched in validSchedulerTypes:
                                    validSchedTypes += str(sched) + ", "
                                print("Unsupported Schedule Type specified. The valid schedulers are: " + str(validSchedTypes[:-2]) + ".")
                                sys.exit(1)

                        if category == "workingGroups":
                            if 'ebsNumber' not in fixedObj:
                                fixedObj['ebsNumber'] = 1
                            # Need to calculate the size to the nearest GB for the EBS Volume size
                            fixedObj['ebs'] = int(math.ceil(float(fixedObj['ebs'])/(float(fixedObj['ebsNumber'])*float(fixedObj['ofs']))))
                            if "omfs" not in fixedObj:
                                fixedObj['omfs'] = fixedObj['ofs']
                            if "op" not in fixedObj:
                                fixedObj['op'] = 3334
                            if 'fo' not in fixedObj:
                                if str(cloudType).lower() == "aws":
                                    #fixedObj['fo'] = int(math.ceil(0.10*float(fixedObj['ofs'])))
                                    fixedObj['fo'] = 0
                                elif str(cloudType).lower() == "gcp":
                                    fixedObj['fo'] = 0
                            if 'fid' not in fixedObj:
                                filesystemGeneratedId = ""
                                fsidNums = [randint(0, 9) for p in range(0, 8)]
                                for digit in fsidNums:
                                  filesystemGeneratedId += str(digit)
                                fixedObj['fid'] = filesystemGeneratedId
                            if 'inputOutputOperationsPerSecond' not in fixedObj or 'instanceIops' not in fixedObj:
                                #fixedObj['iops'] = 0
                                fixedObj['instanceIops'] = 0
                            if "enableEBSEncryption" not in fixedObj:
                                fixedObj['enableEBSEncryption'] = 'false'  #Does this need to be a string lower false? JCE TODO

                        if category == "s3":
                            fixedObj['clusterName'] = "<<CLUSTER_NAME>>"
                            if "type" not in fixedObj:
                                fixedObj['type'] = "common"
                            if "s3Encryption" not in fixedObj:
                                fixedObj['s3Encryption'] = "false"
                            fixedObj['s3NameDisplay'] = str(fixedObj['s3Name'])

                        if category == "createAllEFSMountPoints":
                            if fixedObj['createAllEFSMountPoints'] != "true" or fixedObj['createAllEFSMountpoints'] != "false":
                                fixedObj['createAllEFSMountPoints'] = "false"
                        # Add the fixed object to the template
                        newTemplate[category].append(fixedObj)
            except Exception as e:
                return {"status": "error", "payload": {"error": "The template configuration defined in the configuration file is invalid. Please check the configuration and try again.", "traceback": ''.join(traceback.format_exc())}}

            # Associate the created compute groups with the schedulers and the schedulers with the compute groups
            cgNames = []
            schedName = ""
            for cg in newTemplate['computeGroups']:
                cgNames.append(cg['cgn'])
            for scheduler in newTemplate['schedulers']:
                scheduler['schedGroups'] = cgNames
                schedName = scheduler['schedName']

            for cg in newTemplate['computeGroups']:
                cg['schedName'] = schedName

            # Associate any created filesystems with the Login Instances and vice versa
            fsNames = []
            for fs in newTemplate['workingGroups']:
                fsNames.append(fs['fn'])
            logins = []
            for login in newTemplate['webDavs']:
                login['fn'] = fsNames
                logins.append(login['accessName'])

            for fs in newTemplate['workingGroups']:
                fs['accessInstances'] = logins

            # The initial Creation Wizard we are using to create the environments was designed to do 1 of each type per creation
            # return the user an error if they specify more than one of each type.
            if len(newTemplate['workingGroups']) > 1:
                print("The current iteration of ccAutomaton and CloudyCluster only supports creating one Filesystem per environment. Please modify your configuration file accordingly and try again.")
                sys.exit(1)

            if len(newTemplate['computeGroups']) > 1:
                print("The current iteration of ccAutomaton and CloudyCluster only supports creating one Compute Group during the initial environment creation. You can add more Compute Groups afterwards through the CloudyCluster UI. Please modify your configuration file accordingly and try again.")
                sys.exit(1)

            if len(newTemplate['schedulers']) > 1:
                print("The current iteration of ccAutomaton and CloudyCluster only supports creating one Scheduler during the initial environment creation. You can add more Schedulers afterwards through the CloudyCluster UI. Please modify your configuration file accordingly and try again.")
                sys.exit(1)

            if len(newTemplate['webDavs']) > 1:
                print("The current iteration of ccAutomaton and CloudyCluster only supports creating one Access Instance during the initial environment creation. You can add more Access Instances afterwards through the CloudyCluster UI. Please modify your configuration file accordingly and try again.")
                sys.exit(1)

            # Check to see if the user tried to create a fixed compute group with a CCQ scheduler
            if len(newTemplate['computeGroups']) > 0:
                for scheduler in newTemplate['schedulers']:
                    if scheduler['scalingType'] != "fixed":
                        print("You cannot create a CCQ scheduler and a fixed compute group during initial environment creation. A fixed compute group requires a non CCQ enabled scheduler to function properly. Please modify your configuration file accordingly and try again.")
                        sys.exit(1)

        # Write out template to the environmentType directory for later storage
        newTemplateFile = open(os.path.join(os.path.dirname(__file__), str(self.environmentType))+"/"+str(self.templateName)+".py", "w")
        newTemplateFile.write("template = " + str(newTemplate) + "\n")
        try:
            newTemplateFile.write("\ndescription = \""+str(self.parameters['description']) + "\"\n")
        except Exception as e:
            newTemplateFile.write("\ndescription = \"Template autogenerated by the ccAutomaton Template Generator.\"\n")

        newTemplateFile.close()

        return {"status": "success", "payload": "Successfully generated the " + str(self.templateName) + " template."}

    def delete(self):
        # Need to delete the template file
        try:
            os.remove(os.path.join(os.path.dirname(__file__), str(self.environmentType))+"/"+str(self.templateName)+".py")
        except Exception as e:
            return {"status": "error", "payload": {"error": "There was an error encountered when attempting to delete the " + str(self.templateName) + " file.", "traceback": ''.join(traceback.format_exc())}}

    def populate(self, environmentName, cloudType):
        clusterUuid = str(uuid.uuid4())
        clusterNameUuid = str(clusterUuid)[:4]
        part1 = uuid.uuid4()
        part2 = uuid.uuid4()
        computeGroupID = str(part1)[:4] + "-" + str(part2)[:4]

        clusterName = environmentName + "-" + str(clusterNameUuid)

        # Check to see if the user has provided the required information
        requiredInfo = ["region", "keyname", "az"]
        inputInfo = {}
        missingInfo = False
        returnString = ""
        requiredInfoMapping = {"<<REGION>>": "region", "<<KEY_NAME>>": "keyname", "<<INSTANCE_AVAILABILITY_ZONE>>": "az", "<<CLUSTER_UUID>>": clusterUuid, "<<CLUSTER_NAME>>": str(clusterName), "<<COMPUTE_GROUP_ID>>": computeGroupID}
        try:
            for thing in requiredInfo:
                if thing not in self.parameters:
                    returnString += "In order to use this template you must specify a " + str(thing) + " in the Config file.\n"
                    missingInfo = True
                else:
                    inputInfo[thing] = self.parameters[thing]

            if missingInfo:
                return {"status": "error", "payload": {"error": str(returnString), "traceback": ''.join(traceback.format_stack())}}
            else:

                for entry in requiredInfoMapping:
                    if requiredInfoMapping[entry] in inputInfo:
                        requiredInfoMapping[entry] = inputInfo[requiredInfoMapping[entry]]

                tempTemplate = copy.deepcopy(self.template)
                for attr in tempTemplate:
                    if str(self.template[attr]) in requiredInfoMapping:
                        self.template[attr] = requiredInfoMapping[str(self.template[attr])]
                    if type(self.template[attr]) is list:
                        # Loop through the list and make sure there is nothing that needs to be populated in the entries of the list
                        for entry in self.template[attr]:
                            # print entry
                            if type(entry) is dict:
                                for item in entry:
                                    # print item
                                    if str(entry[item]) in requiredInfoMapping:
                                        # print "Replacing: " + str(entry[item]) + " with: " + str(requiredInfoMapping[str(entry[item])])
                                        entry[item] = requiredInfoMapping[str(entry[item])]

                generatedCidrNumber = randint(0, 255)
                generatedVpcCidr = '10.' + str(generatedCidrNumber) + '.0.0/16'
                self.template['vc'] = str(generatedVpcCidr)
                if str(cloudType).lower() == "aws":
                    if str(self.template["Region"]) not in str(self.template['instanceAvailabilityZone']):
                        return {"status": "error", "payload": "The Availability Zone specified in the Configuration file is not located within the Region specified in the Configuration file. Please fix your Configuration file so that the Availability Zone is located in the Region specified and try again."}
                    else:
                        return {"status": "success", "payload": {"template": self.template, "environmentName": clusterName}}
                elif str(cloudType).lower() == "gcp":
                    #TODO Figure out a way to implement a check
                    return {"status": "success", "payload": {"template": self.template, "environmentName": clusterName}}
        except Exception as e:
            return {"status": "error", "payload": {"error": "There was a problem encountered when trying to populate the template from the values provided in the Configuration file.", "traceback": ''.join(traceback.format_exc())}}

    def listTemplates(self):
        try:
            templateList = {}
            # Load the module (ex: import cloudycluster)
            sys.path.append(os.path.join(os.path.dirname(__file__), str(self.environmentType)))

            for file in os.listdir(os.path.join(os.path.dirname(__file__), str(self.environmentType))):
                splitFile = str(file).split(".")
                try:
                    if splitFile[1] == "py":
                        module = __import__(splitFile[0])
                        templateList[splitFile[0]] = str(module.description)
                except IndexError:
                    print(f"{file} isn't a python file")
                    pass
            return {"status": "success", "payload": templateList}
        except Exception as e:
            return {"status": "error", "payload": {"error": "Unable to get the template specified.", "traceback": ''.join(traceback.format_exc())}}


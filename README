Licensed under either of:
    Apache License, Version 2.0, (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0)
    MIT License (LICENSE-MIT or http://opensource.org/licenses/MIT)
    LGPL License, Version 2.0 (LICENSE-LGPLv2 or https://www.gnu.org/licenses/old-licenses/lgpl-2.0.txt)
at your option.

The Automaton Project or academically referenced as PAW (Provisioning And Workflow) is a management tool is an tool designed to automate the steps required to dynamically provisioning a large scale cluster environment in the cloud, executing a set of jobs or a custom workflow, and after the jobs have completed de-provisioning the cluster environment in a single operation. For more details on the technical implementation and design please read the following paper located at: https://tigerprints.clemson.edu/computing_pubs/38.

It is driven by a single configuration file that defines all of the parameters required to create a fully functional HPC Environment in the Cloud. It is designed to be modular and pluggable to allow it to support a variety of HPC Schedulers, environment types, workflows, and cloud providers. This initial implementation of PAW utilizes CloudyCluster and AWS to perform the dynamic provisioning, workflow execution, and automated de-provisioning of the HPC Environment. The sections of the configuration file and their parameters are discussed further on in this document.

#########################
#  Template Generation  #
#########################
Environment creation within ccAutomaton is driven by templates. These templates define what resources are to be created within the Environment. PAW includes a template generator that can generate templates defined within a ccAutomaton configuration file. The exact specifications of what a template can contain and how to format it can within a ccAutomaton configuration file can be found in the Configuration File section of this document.

ccAutomaton Template Generator Arguments (these can also be found by using the -h argument):
-et <environmentType> The type of environment to create the template for.
-cf <configFilePath>  The path to the configuration file that contains your configuration files.
-lt                   Print out the list of templates available for the specified Environment Type.
-dt                   Delete the specified template file if it exists.
-tn <templateName>    The name of the template you wish to generate. This name should be the same as the section in the configuration file that contains the configuration for the Environment.
-h                    Print help.

Running the ccAutomaton template generator can be done utilizing the following commands:
Create a new template: python CreateEnvironmentTemplate.py -et CloudyCluster -cf <myConfigurationFile> -tn <templateName>
List currently created templates: python CreateEnvironmentTemplate.py -et CloudyCluster -lt
Delete created template: python CreateEnvironmentTemplate.py -et CloudyCluster -dt -tn <templateName>

#########################
#      Running ccAutomaton      #
#########################
ccAutomaton is driven by a single configuration file that defines all the actions it needs to take from creating control resources, creating an environment, running jobs/workflows, deleting the environment, and deleting the control resources. PAW has the ability to do all of these steps with one command, or the user can run only the parts of the process that they require. All of the actions can be run separately but some of the actions then require the user to input some extra parameters if all the steps are not run at the same time. For example, if a user just wants to delete an environment they will need to provide the DNS name of the Control Instance and the full name of the environment they wish to delete.

ccAutomaton Arguments:
-et <environmentType> The type of environment to create.
-all                  Run the entire process: create Control Resources, create an Environment, submit the specified jobs, and upon job completion delete the Environment and the Control Resources.
-cf <configFilePath>  The path to the configuration file to be used by ccAutomaton. The default is the ccAutomaton.conf file in the local directory.
-cc                   If specified, this argument tells ccAutomaton to create new Control Resources.
-ce                   If specified, this argument tells ccAutomaton to create a new Environment.
-rj                   If specified, this argument tells ccAutomaton to run the jobs specified in the configuration file.
-de                   If specified, this argument tells ccAutomaton to delete the specified Environment.
-dc                   If specified, this argument tells ccAutomaton to delete the specified Control Resources.
-dn <domainName>      The domain name of the Control Resources of the Environment you want to use. If requesting to run jobs, delete an Environment or delete Control Resources this argument specifies which Control Resource should be used to perform the requested actions.
-jr <jobsToRun>       A list of job scripts or workflow templates (with options specified) to be run on the specified environment.
-en <environmentName> The name of the Environment that you wish to use to fulfill your requests.
-crn <controlResourceName> The name of the Control Resources that you wish to delete.
-r <region>          The region where the Control Resources are located.
-p <profile>         The profile to use for the Resource API.
-h                   Print help.

Running ccAutomaton with all stages: python Create_Processing_Environment.py -et CloudyCluster -cf ConfigurationFiles/ccAutomaton.conf -all

Running ccAutomaton with just delete control and delete environment: Create_Processing_Environment.py -et CloudyCluster -cf ConfigurationFiles/ccAutomaton.conf -dc -dn <domainName, ex: curlewbrotulatopaz.cloudycluster.com> -de -en <environmentName, ex: ccAutomaton-0135> -crn <controlResourceName, ex:arn:aws:cloudformation:eu-west-1:939964386746:stack/ccAutomatonControlResources-85a5/3f748c40-01f8-11e8-8626-50a68642b229>
#########################
#  Configuration File   #
#########################
The Configuration file is composed of six different sections two of which are optional. The six sections are: UserInfo, General, CloudyClusterAws, CloudyClusterEnvironment, Computation, <TemplateName>. The Computation and <TemplateName> sections are optional. A summary of the available parameters and their purpose is included below. Example configuration files can be found in the ConfigurationFiles directory.

    UserInfo:
       ****NOTE: Parameters designated with an * are required****
       Description: Contains the parameters required to create a user within the CloudyCluster environment

       Valid Section Parameters: userName*, password*, firstName*, lastName*, pempath*
           userName: the username that will be used to login to CloudyCluster via the ControlNode UI and the username that jobs/workflows will be run under (ex: bobby)

           password: the password for the username specified above. This is required to login to the ControlNode and to SSH to the other instances (ex: password)

           firstName: the first name of the user being created, used for identification within the CloudyCluster UI (ex: Bobby)

           lastname: the last name of the user being created, used for identification in the CloudyCluster UI (ex: Sue)

           pempath: the full absolute path the SSH keyfile that will be used to launch the EC2 instances within AWS. If you do not have a key pair created in AWS you must do so before using ccAutomaton (ex: /home/myuser/my-key.pem)

    General:
        ****NOTE: Parameters designated with an * are required****
        Description: Contains general parameters about the cloud type to be used and the name of the environment to be created.

        Valid Section Parameters: environmentName*, cloudType*
            environmentName: the name of the CloudyCluster environment that will be created by ccAutomaton (ex: myTestEnvironment)

            cloudType: the type of resource provider to be used when creating the CloudyCluster environment. For the current iteration of ccAutomaton the only valid value is: aws. (ex: aws)

    CloudyClusterAws:
        ****NOTE: Parameters designated with an * are required****
        ****NOTE: This is a dynamically named section. The first part of the section name is the Environment Type to be provisioned and the second part of the name is the resource provider to be used. In this initial release of ccAutomaton the only valid section name is CloudyClusterAws.****

        Description: This section contains all of the parameters required to launch CloudyCluster on AWS.

        Valid Section Parameters: profile, keyName*, instanceType*, networkCidr*, vpc*, publicSubnet*, capabilities*, region*, templateLocation*
            profile: optional argument that tells Boto3 and Botocore to use a specific credential profile specified in the .aws/credentials file. If not specified it uses the default profile. (ex: myprofile)

            keyName: the name of the SSH key pair that ccAutomaton will use to launch the CloudyCluster Control Instance. **NOTE** This should be a valid AWS key pair and NOT contain the .pem extension. (ex: my-key)

            instanceType: the AWS instance type of the CloudyCluster Control Instance to be created by ccAutomaton. A full list of EC2 instance types can be found at: https://aws.amazon.com/ec2/instance-types/ (ex: t2.small)

            networkCidr: the CIDR of the network that you can access the CloudyCluster Control Instance from. If you want to restrict access to a certain network you can enter that here, if not you can leave it as 0.0.0.0/0 to allow access from anywhere on the Internet. (ex: 0.0.0.0/0)

            vpc: the VPC ID of the AWS VPC you want to launch the CloudyCluster Control Node into. This can be obtained by going to the AWS VPC Service from the Management Console and selecting VPCs from the sidebar. You then will see a list of default VPCS, these generally have CIDRs that start with 172.x.x.x, use the VPC ID which will be of the form vpc-xxxxxxxx (ex: vpc-c6fa13ae)

            publicSubnet: the Subnet ID of the AWS VPC Subnet you want to launch the CloudyCluster Control Node into. This can be obtained by going to the AWS VPC Service from the Management Console and selecting Subnets from the sidebar. You then will see a list of subnets created for the VPCs in your account. You need to make sure that the subnet selected is located in the same VPC that you specified using the vpc directive. Use the Subnet ID which will be of the form subnet-xxxxxxxx (ex: subnet-3fe21654)

            capabilities: this specifies the capabilities required by AWS CloudFormation to launch the CloudyCluster Control Node. CloudyCluster must be allowed to create IAM policies in order to work. Changing this argument to anything but CAPABILITY_IAM will result in errors. (ex: CAPABILITY_IAM)

            region: the AWS region that you want to launch the CloudyCluster Control Instance into. CloudyCluster Control Instances can only create environments in the region they are created in. This needs to be the AWS name not the Plain English name. ****NOTE AWS uses Human readable names to reference regions in the console (ex: US East Ohio). These WILL NOT WORK you need to use the API names, these can be found at https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/using-regions-availability-zones.html#concepts-available-regions**** (ex: us-east-2)

            templateLocation: this specifies the location of the CloudFormation Template used by AWS CloudFormation to launch the CloudyCluster Control Instance. This template is included with ccAutomaton and the location can be left as the default. (ex: cloudyClusterCloudFormationTemplate.json)

    CloudyClusterEnvironment:
        ****NOTE: Parameters designated with an * are required****
        Description: Contains the parameters required to create a CloudyCluster Environment

        Valid Section Parameters: templateName*, keyName*, region*, az*
            templateName: specifies the name of a CloudyCluster Environment Template that was generated using the ccAutomaton Environment Template Generator. The ccAutomaton Environment Template Generator is documented further down in this document. These templates contain the resources that will be created within the CloudyCluster Environment. (ex: ccqEnvironment2)

            keyName: the name of the SSH key pair that ccAutomaton will use to launch the CloudyCluster Control Instance. **NOTE** This should be a valid AWS key pair and NOT contain the .pem extension. (ex: my-key)

            region: the AWS region that you want to launch the CloudyCluster Environment into. CloudyCluster Environments live within a specific region. This needs to be the AWS API name not the Plain English name. (ex: us-east-2) ****NOTE AWS uses Human readable names to reference regions in the console (ex: US East Ohio) these WILL NOT WORK you need to use the API names, these can be found at https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/using-regions-availability-zones.html#concepts-available-regions****

            az: the Availability Zone within the AWS region that you want to launch the CloudyCluster Environment into. CloudyCluster Environments live within a specific Availability Zone within a specific AWS Region. The Availability Zone chosen MUST be in the same AWS region as specified in the region parameter. (ex: us-east-2a)

    Computation:
        ****NOTE: Parameters designated with an * are required****
        Description: Contains the workflows/jobs that ccAutomaton can execute on the provisioned CloudyCluster Environment. ****NOTE: There can be more than one job or workflow specified in this section, they just need to be of the format: jobScript1, jobScript2, workflow1, workflow2. These jobs/workflows will run in the order they are specified in the configuration file.****

        ***NOTE: There is an example custom TopicModeling Workflow included with ccAutomaton, the Options and how to run this custom workflow is described in the Experiments/NIPS_Topic_Modeling_Experiment folder in the ccAutomaton source code.****

        Valid Section Parameters: jobScript, workflow
            jobScript: specifies that ccAutomaton should run this particular job script after the creation of the environment.
                Valid JobScript parameters: name, options
                    name: the name of the job to be executed

                    options:  the parameters that are required to run the jobscript. These are specified as a key-value dictionary
                        Valid options parameters: uploadProtocol, uploadScript, localPath, remotePath, executeDirectory
                        uploadProtocol: the protocol to use when uploading the jobscript to the environment. Currently the only valid value is "sftp". (ex: sftp)

                        localPath: required if uploading a jobscript from the local machine, the absolute path to the jobscript on the local machine (ex: /home/myuser/test.sh)

                        remotePath: the path where the uploaded jobscript is to be put on the environment, usually the shared filesystem. Must be the absolute path to the shared filesystem, all CloudyCluster shared filesystems are mounted under the /mnt directory as the name of the filesystem. (ex: /mnt/efsdata)

                        executeDirectory: the full path to where the jobscript should be executed from on the CloudyCluster Environment. (ex: /mnt/efsdata)

            workflow: specifies that ccAutomaton should run the custom workflow specified by the user after the creation of the environment. Custom workflows can be created by users to allow users to run their workflows quickly and efficiently.

                Valid Workflow Parameters: name*, type*, schedulerType*, options
                    name: the name of the workflow for identification use (ex: myWorkflow)

                    type: the type of workflow to be executed, this argument MUST match the name of the Python file the workflow methods are defined in under the Workflow Templates directory. (ex: topicModelingPipeline)

                    schedulerType: the type of scheduler that the workflow will run on. Valid values are Torque or Slurm (ex: Slurm)

                    options: this parameter can contain any number of parameters required for the execution of the custom workflow. This argument is specified as a key-value dictionary. (ex: {"key": "value", "key1": "value1"}

    <Template_Name>:
        ****NOTE: This is a dynamically named section. The name of the section will be the name of the CloudyCluster Environment Template generated by the ccAutomaton CloudyCluster Environment Template Generator.****
        ****NOTE: All section parameters key-value dictionaries MUST have "" around the keys and values.****

        Description: this section contains the definitions of the resources that will be created within the CloudyCluster Environment

        Valid Section Parameters: description, vpcCidr, scheduler, efs, s3, login, nat, filesystem, computegroup
            ****NOTE: Parameters designated with an * are required****

            description: a simple text description of the environment that the template will create (ex: Creates a CloudyCluster Environment that contains a single t2.small CCQ enabled Slurm Scheduler, a t2.small Login instance, EFS backed shared home directories, a EFS backed shared filesystem, and a t2.micro NAT instance.)

            vpcCidr*: this is the CIDR of the VPC that will be created to hold the newly created environment (ex: 10.0.0.0/16)

            scheduler:
                Description: The Scheduler is the instance that users can submit jobs to and what schedules the jobs on the Compute Instance. Currently supported Schedulers are Torque and Slurm, these can be augmented with CloudyCluster Queue (CCQ) which is a meta-scheduler that allows for job based autoscaling. See the CloudyCluster Documentation for more information on CCQ.

                Valid Scheduler Parameters: instanceType*, ccq, volumeType, name*, type*
                    instanceType*: the AWS Instance type of the Scheduler (ex: t2.small)

                    name*: the name of the Scheduler as it will appear in the CloudyCluster UI (ex: mySlurmScheduler)

                    type*: the type of Scheduler that will be created. The current valid scheduler types are Torque, and Slurm. (ex: Slurm)

                    ccq: specifies if CloudyCluster should create a CCQ enabled Scheduler. CCQ is CloudyCluster's meta-scheduler that allows for job based autoscaling. See the CloudyCluster documentation for more details. Valid values are true and false, the default value is false. (ex: true)

                    volumeType: specifies the Volume Type of the Scheduler. The default value is SSD but can also be Magnetic. (ex: SSD)

            efs:
                ****NOTE: You can configure multiple EFS filesystems during creation by adding them to the configuration file as efs1, efs2, etc.****

                Description: A shared filesystem that is backed by AWS's Elastic Filesystem Service (EFS). EFS is only supported in specific regions so this option will only work in regions that support EFS. There are 3 different EFS types that can be created by CloudyCluster: common, ssw, sharedHome. The common type EFS is a standard shared filesystem, the ssw type is meant to be utilized for shared software and module files, and the sharedHome type enables shared home directories for all users of the environment. All EFS mounts are mounted on all Compute Groups, Scheduler, and Login instances under the /mnt directory.

                Valid EFS Parameters: type*, name
                type: the type of EFS filesystem to be created. The valid values are ssw, common, and sharedHome. SSW is a shared software mount where you can add module files for software that you install and is mounted across all the compute instances. Common is a standard clean shared filesystem across all compute instances and sharedHome enables shared home directories across all compute instances.

                name: the name of the EFS filesystem. The default value for the common type is efsdata, for ssw it is efsapps, for sharedHome it is home. When specifying sharedHome you cannot specify a name. All EFS filesystems will be mounted at /mnt/<name>

            login:
                Description: The Login Instance serves at the public facing instance into the CloudyCluster Environment. It has a public IP address and an associated domain name for file transfer and ssh access to the internal Compute Groups and Scheduler instances. The Login instance can also have VNC enabled for graphical access to the Login Instance for visualization, it also supports WebDAV file transfers from created OrangeFS filesystems and EFS filesystems.

                Valid Login Parameters: instanceType*, name*, volumeType
                    instanceType: the AWS instance type of the Login Instance (ex: t2.small)

                    name: the name of the Login Instance as it will appear in the CloudyCluster UI (ex: myLogin)

                    volumeType: specifies the Volume Type of the Login. The default value is SSD but can also be Magnetic. (ex: SSD)

            nat:
                Description: The NAT instance is required in order for the internal instances (Scheduler, Filesystem, Compute) to access the Internet and to be able to download files.

                Valid NAT Parameters: instanceType*, accessFrom*, volumeType
                    instanceType: the AWS instance type of the Login Instance (ex: t2.small)

                    accessFrom: the CIDR from which the CloudyCluster environment will be accessible from. This can be the company or campus network to limit access to the resources to users who are connected to those networks. Or it can be set to 0.0.0.0/0 to allow users to access it from anywhere. (ex: 0.0.0.0/0)

                    volumeType: specifies the Volume Type of the NAT. The default value is SSD but can also be Magnetic. (ex: SSD)

            computegroup:
                Description: A fixed compute group contains a set number of instances that are registered with the Scheduler so that they can run jobs submitted to the Scheduler. These instances tend to have more compute power then the other instances in the Environment.

                Valid Compute Group Parameters: numberOfInstances*, instanceType*, name*, volumeType
                    numberOfInstances: the number of Compute Instance you want to have in the Compute Group.  (ex: 5)

                    instanceType: the AWS instance type of the  Compute Instances in the Compute Group (ex: t2.small)

                    name: the name of the Compute Group as shown in the CloudyCluster UI (ex: myComputeGroup)

                    volumeType: specifies the Volume Type of the Compute Group. The default value is SSD but can also be Magnetic. (ex: SSD)

            filesystem:
                Description: An OrangeFS parallel filesystem that is running over multiple EC2 instances and backed by EBS storage. Comes by default in a High Availability configuration complete with failover protection via a "hot-spare" that can take over in case of issues with one of the Filesystem Instances encounter issues.

                Valid Filesystem Parameters: numberOfInstances*, instanceType*, name*, filesystemSizeGB*, port, filesystemId, numberOfStandbyInstances, storageVolumesPerInstance, volumeType, inputOutputOperationsPerSecond, encrypted
                    numberOfInstances: the number of EC2 instances that the Filesystem will be spread over (ex: 4)

                    instanceType: the AWS instance type of the Filesystem instances (ex: t2.small)

                    name: the name of the filesystem. This is the name that it will be mounted as in /mnt on all the compute instances. (ex: orangefs)

                    filesystemSizeGB: the size of the Filesystem in GB. If the number of GB specified is not evenly divisible by the number of instances and volumes per instance specified, the size will be increased to be evenly divisible. It will never be smaller than the specified value. (ex: 100)

                    port: the port which OrangeFS uses to communicate. The default port is 3334. (ex: 3334)

                    filesystemId: the ID of the OrangeFS filesystem. This must be a 8 digit number, it is randomly generated as default. (ex: 85362145)

                    numberOfStandbyInstances: the number of "hot spares" available in case of Filesystem instance failure. The default is 10% of the number of requested filesystem instances. (ex: 1)

                    storageVolumesPerInstance: the number of EBS volumes per Filesystem Instance. The default is 1. (ex: 1)

                    volumeType: specifies the Volume Type of the Filesystem Instances. The default value is SSD but can also be Magnetic. (ex: SSD)

                    inputOutputOperationsPerSecond: specifies that each EBS volume should have this number of IOPS. Default is 0 which sets the value to the default IOPS for the specified AWS Volume Type. (ex: 0)

                    encrypted: specifies that each EBS volume should have encryption turned on. The default is false. (ex: true)
            s3:
                Description: S3 is an object store and this creates an S3 bucket where jobs or users can store their files. This bucket is created and deleted with the Environment.

                Valid S3 Parameters: name*, encrypt
                    name: the name of the S3 bucket to be created. All S3 bucket names must be unique so if the name you specified is not available it will add a 1 to the end and increment from there. Also CloudyCluster has to add a cc. in front of the name as well to be able to access it. See the AWS S3 naming restrictions for the requirements of this name. (ex: mybucket)

                    encrypt: specifies that S3 encryption should be turned on for the bucket being created. The default value is false. (ex: true)

# Automaton Quickstart

This guide is meant to help users get started using Automaton!

## Environment Setup

### Python Setup

Install Python3 and Pip3.

Install the required packages with `pip install botocore boto3 google-api-python-client paramiko requests`

### GCP Setup

To enable IAM/APIs, create a service account, and add an SSH key to your project, follow the [GCP Prep Documentation](http://docs.gcp.cloudycluster.com/gcp-quickstart-deployment-guide/gcp-prep/). 

Also be sure to have `gcloud` installed locally and configured!

### VM Image

You will also need a valid CloudyCluster image in your project to test and modify.

The current release of CloudyCluster is publically stored at `projects/public-marketplace-cc/global/images/cloudycluster-v3-1-2-release`.

To copy the image to your project, run: 

```
gcloud compute --project=<YOUR_PROJECT> images create cloudycluster-v3-1-2-release \ 
  --source-image=cloudycluster-v3-1-2-release --source-image-project=public-marketplace-cc
```

Note the image url in the form `projects/<YOUR_PROJECT>/global/images/cloudycluster-v3-1-2-release` for configuration.

## Configuration

To start configuring Automaton, first clone the repo to your local machine with `git clone https://github.com/omnibond/automaton.git`.

Enter the directory with `cd automaton`.

### tester.config

Copy the file `tester.config.example`: `cp tester.config.example tester.config`

Comment out the appropriate lines and add the parameters, including:

 - the local paths to your key files
 - the name of the service account you created
 - the image url

Here is an example of a configured file:

```
[tester]
;the username for the created cluster
username = cole
;set cloudType as aws or gcp
cloudType = gcp
;KeyName is for aws only
;KeyName = YOUR KEYPAIR NAME
;project_name is for gcp only
project_name = cloudyclusterfirebasedev
;sourceimage for gcp
sourceimage = projects/cloudyclusterfirebasedev/global/images/cloudycluster-v3-1-2-release
;sourceimage for aws
;sourceimage = ami-IMAGE
;service_account for gcp only
service_account = cole-sa@cloudyclusterfirebasedev.iam.gserviceaccount.com
ssh_private_key = /home/cole/.ssh/automaton
ssh_public_key = /home/cole/.ssh/automaton.pub
;make sure CloudyCluster and Automaton are in the same directory
;set to true if sourceimage is a dev or prod image or set to false if sourceimage is a userapps image which will make a new build
dev_image = true
;configuration file for the specified jobs
job_config = jobtest.config
;set to true to delete the cluster even if it fails
delete_on_failure = true
output_part1 = /home/cole/
output_part2 = %%Y%%m%%d-%%H%%M
email_flag = false
;leave unchanged if email is set to false
;smtp_port = smtp-relay.gmail.com
;port = 587
;from_addr = tester@omnibond.com
;to_addr = TO
;output_url = OUTPUT_URL
```

### jobtest.config

Copy the file `jobtest.config.example`: `cp jobtest.config.example jobtest.config`

Name and configure your jobs. Here is an example of a configured file:

```
;in the brackets put the name of each of your jobs
[MPI_PRE]
;job_type is always required
;the first job_type needs to be MPIPreliminaryJob
job_type = MPIPreliminaryJob

[MPI_2_2]
job_type = MPIJob
nodes = 2
processes = 2
;below are optional
instance_type = "c2-standard-4"
;example: "c2-standard-4"
;preemptible is always set to False
preemptible = False

;for gpu or orangefs jobs only instance_type is required
;[YOUR_JOB_NAME]
;job_type = GPUJob/OrangeFSJob
```

## Deployment

To deploy, simply run `python3 tester.py`
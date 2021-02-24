import configparser
import os
import select
import signal
import sys
import termios
import time

import googleapiclient.discovery

def run(args, timeout=0, die=True):
    print("running command %s" % args)
    start = time.time()
    # Use a pty so that commands which call isatty don't change behavior.
    pid, fd = os.forkpty()
    if pid == 0:
        try:
            os.execlp(args[0], *args)
        except OSError as e:
            print(e)
        sys.exit(1)
    else:
        t = termios.tcgetattr(fd)
        t[1] = t[1] & ~termios.ONLCR
        termios.tcsetattr(fd, termios.TCSANOW, t)
    buffer = b""
    expired = False
    while True:
        # A pty master returns EIO when the slave is closed.
        try:
            rlist, wlist, xlist = select.select([fd], [], [], 5)
            if len(rlist):
                new = os.read(fd, 1024)
            else:
                if timeout and time.time() > start + timeout:
                    expired = True
                else:
                    continue
        except OSError:
            new = b""
        if expired or len(new) == 0:
            break
        sys.stdout.buffer.write(new)
        sys.stdout.flush()
        buffer = buffer + new
    if expired:
        print(f"time limit of {timeout} expired")
    # This will also send SIGHUP to the child process.
    os.close(fd)
    pid, status = os.waitpid(pid, 0)
    end = time.time()
    final_time = end - start
    if os.WIFEXITED(status):
        status = os.WEXITSTATUS(status)
        print(f"process returned {status} after {final_time} seconds")
    else:
        status = os.WTERMSIG(status)
        print(f"process died from signal {status} after {final_time} seconds")
    if die and (status != 0 or expired):
        sys.exit(1)
    buffer = buffer.decode()
    return buffer

def main():
    if len(sys.argv) > 1:
        filename = sys.argv[1]
    else:
        filename = "tester.config"

    try:
        os.stat(filename)
    except FileNotFoundError:
        print(f"configuration file {filename} not found")
        sys.exit(1)

    cp = configparser.ConfigParser()
    cp.read(filename)

    try:
        username = cp.get("tester", "username")
        project_name = cp.get("tester", "project_name")
        sourceimage = cp.get("tester", "sourceimage")
        service_account = cp.get("tester", "service_account")
        ssh_private_key = cp.get("tester", "ssh_private_key")
        ssh_public_key = cp.get("tester", "ssh_public_key")
    except configparser.NoSectionError:
        print("missing configuration section")
        sys.exit(1)
    except configparser.NoOptionError:
        print("missing configuration option")
        sys.exit(1)

    job_path = os.getcwd() + "/test.sh"

    os.chdir("..")

    os.chdir("CloudyCluster/Build")
    current_build = run(["git", "describe", "--always"]).strip()
    compute = googleapiclient.discovery.build("compute", "v1")
    images = compute.images().list(project=project_name).execute()
    image_id = None
    for image in images["items"]:
        if ("%stest" % username) in image["name"] and current_build in image["name"]:
            image_id = image["name"]

    if image_id:
        image = image_id
        print("Using image %s" % (image))
    else:
        f = open("test.yaml", "w")
        f.write(f"""- start:
  - local: false
  - sshkeyname: builderdash
  - sshkeyuser: builderdash
# ssh-keygen -m pem -f builderdash.pem -C builderdash
  - sshkey: {ssh_private_key}
  - pubkeypath: {ssh_public_key}
  - spot: no
  - cloudservice: gcp
  - instancetype: n1-standard-32
  - region: us-east1-b
  - ostype: centos
  - instancename: {username}test-hpc
  - sourceimage: {sourceimage}
  - buildtype: dev
  - subnet: ''
  - bucketname: {project_name}.appspot.com
  - projectname: {project_name}
  - projectid: {project_name}
  - customtags:
    - packages
    - save
    - delete

- build:
  - builderdash:
    - build.yaml
""")
        f.close()
        build = run(["python3", "builderdash.py", "-c", "test.yaml"], timeout=900)
        build = build.split("\n")
        image = None
        for line in build:
            if line.startswith("the instance we're going to delete is"):
                image = line.split(":")[1][1:]
        if not image:
            print("There's an error!")
            sys.exit(1)

    os.chdir("../..")

    ready = False
    while not ready:
        compute_client = googleapiclient.discovery.build("compute", "v1")
        request = compute_client.images().get(project=project_name, image=image)
        res = request.execute()
        if res["status"] != "READY":
            time.sleep(30)
        else:
            ready = True

    f = open(job_path, "w")
    f.write("""#!/bin/sh
#SBATCH -N 1
date
hostname
""")
    f.close()

    password = os.urandom(16).hex()
    print("cluster username", username)
    print("cluster password", password)

    f = open("automaton/ConfigurationFiles/gcp_tester.conf", "w")
    f.write(f"""[UserInfo]
userName: {username}
password: {password}
firstName: {username}
LastName:
pempath: {ssh_private_key}

[General]
environmentName: {username}
cloudType: gcp
email:
sender:
sendpw: 
smtp: 

[CloudyClusterGcp]
keyName: {username}
instanceType: g1-small
networkCidr: 0.0.0.0/0
region: us-east1
zone: us-east1-b
pubkeypath: {ssh_public_key}
sshkeyuser: {username}
sourceimage: projects/{project_name}/global/images/{image}


projectId: {project_name}
serviceaccountemail: {service_account}

[CloudyClusterEnvironment]
templateName: tester_template
keyName: {username}
region: us-east1
az: us-east1-b

[Computation]
# workflow1: {{"name": "gcpLargeRun", "type": "videoAnalyticsPipeline", "options": {{"instanceType": "c2-standard-4", "numberOfInstances": "2", "submitInstantly": "True", "usePreemptibleInstances": "true", "maintainPreemptibleSize": "true", "trafficVisionDir": "/software/trafficvision/", "bucketListFile": "list-us-east1", "generatedJobScriptDir": "generated_job_scripts", "trafficVisionExecutable": "process_clip.py", "jobGenerationScript": "generateJobScriptsFromBucketListFile.py", "jobPrefixString": "tv_processing_", "clip_to_start_on": "0", "clip_to_end_on": "100", "useCCQ": "true", "schedulerType": "Slurm", "schedulerToUse": "slurm", "skipProvisioning": "true", "timeLimit": "28800", "createPlaceholderInstances": "True"}}}}

#workflow2: {{"name": "gcpLargeRun", "type": "videoAnalyticsPipeline", "options": {{"instanceType": "c2-standard-16", "numberOfInstances": "2", "submitInstantly": "True", "usePreemptibleInstances": "true", "maintainPreemptibleSize": "true", "trafficVisionDir": "/software/trafficvision/", "bucketListFile": "bucket.list", "generatedJobScriptDir": "generated_job_scripts", "trafficVisionExecutable": "process_clip.py", "jobGenerationScript": "generateJobScriptsFromBucketListFile.py", "jobPrefixString": "tv_processing_", "clip_to_start_on": "0", "clip_to_end_on": "1000000", "useCCQ": "true", "schedulerType": "Slurm", "schedulerToUse": "slurm", "skipProvisioning": "true", "timeLimit": "28800", "createPlaceholderInstances": "True"}}}}

jobScript1: {{"name": "testScript1", "options": {{"uploadProtocol": "sftp", "monitorJob": "true", "timeout": 600, "uploadScript": "true", "localPath": "{job_path}", "remotePath": "/mnt/orangefs/test.sh", "executeDirectory": "/mnt/orangefs"}}}}

jobScript2: {{"name": "testScript2", "options": {{"uploadProtocol": "sftp", "monitorJob": "false", "timeout": 600, "uploadScript": "true", "localPath": "{job_path}", "remotePath": "/mnt/orangefs/test.sh", "executeDirectory": "/mnt/orangefs"}}}}

jobScript3: {{"name": "testScript3", "options": {{"uploadProtocol": "sftp", "monitorJob": "true", "timeout": 600, "uploadScript": "true", "localPath": "{job_path}", "remotePath": "/mnt/orangefs/test.sh", "executeDirectory": "/mnt/orangefs"}}}}

jobScript4: {{"name": "testScript4", "options": {{"uploadProtocol": "sftp", "monitorJob": "false", "timeout": 600, "uploadScript": "true", "localPath": "{job_path}", "remotePath": "/mnt/orangefs/test.sh", "executeDirectory": "/mnt/orangefs"}}}}

[tester_template]
description: Creates a CloudyCluster Environment that contains a single g1-small CCQ enabled Slurm Scheduler, a g1-small Login instance, a 100GB OrangeFS Filesystem, and a g1-small NAT instance.
vpcCidr: 10.0.0.0/16
scheduler1: {{'type': 'Slurm', 'ccq': 'true', 'instanceType': 'g1-small', 'name': 'slurm', 'schedAllocationType': 'cons_res'}}
filesystem1: {{"numberOfInstances": 4, "instanceType": "g1-small", "name": "orangefs", "filesystemSizeGB": "20", "storageVolumeType": "SSD", "orangeFSIops": 0, "instanceIops": 0}}
login1: {{'name': 'login', 'instanceType': 'g1-small'}}
nat1: {{'instanceType': 'g1-small', 'accessFrom': '0.0.0.0/0'}}
""")
    f.close()

    os.chdir("automaton")

    creating_templates = run(["python3", "CreateEnvironmentTemplates.py", "-et", "CloudyCluster", "-cf", "ConfigurationFiles/gcp_tester.conf", "-tn", "tester_template"], timeout=30)
    print("created template:", creating_templates)

    running_automaton = run(["python3", "Create_Processing_Environment.py", "-et", "CloudyCluster", "-cf", "ConfigurationFiles/gcp_tester.conf", "-all"])
    print("automaton run:", running_automaton)

if __name__ == "__main__":
    main()

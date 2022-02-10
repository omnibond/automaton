import configparser
import email.utils
import logging
import os
import re
import select
import signal
import smtplib
import ssl
import sys
import tempfile
import termios
import time
import json

import googleapiclient.discovery

logger = logging.getLogger("tester")

class Job:
    def __init__(self, name, output_dir, monitor=True):
        self.name = name
        self.output_dir = output_dir
        self.monitor = monitor

        self.job_filename = f"{self.name}.sh"
        self.job_file = tempfile.NamedTemporaryFile(mode="w", delete=False)
        self.job_path = self.job_file.name
        self.success = True

    def __repr__(self):
        return f"<{self.__class__.__name__} {self.name}>"

    def save_job(self, cloudType, scheduler):
        self.job_text(self.job_file, cloudType, scheduler)
        self.job_file.close()

    def job_text(self, f, cloudType, scheduler):
        raise Exception("job_text undefined")

    def config(self, n, cloudType):
        if self.monitor:
            monitor = "true"
        else:
            monitor = "false"
        if cloudType == "gcp":
            return f"""jobScript{n}: {{"name": "{self.name}", "options": {{"uploadProtocol": "sftp", "monitorJob": "{monitor}", "timeout": 0, "uploadScript": "true", "localPath": "{self.job_path}", "remotePath": "/mnt/orangefs/{self.job_filename}",
            "directory": "{self.output_dir}", "executeDirectory": "/mnt/orangefs"}}}}"""

        if cloudType == "aws":
            return f"""jobScript{n}: {{"name": "{self.name}", "options": {{"uploadProtocol": "sftp", "monitorJob": "{monitor}", "timeout": 0, "uploadScript": "true", "localPath": "{self.job_path}", "remotePath": "/mnt/orangefs/{self.job_filename}", "directory": "{self.output_dir}", "executeDirectory": "/mnt/orangefs"}}}}"""

    def output(self, output, error):
        pass

    def parameters(self):
        ""
    
    def cleanup_job(self):
        os.unlink(self.job_path)

class MPIPreliminaryJob(Job):
    def job_text(self, f, cloudType, scheduler):
        if scheduler == "Slurm":
            sched_type = "#SBATCH -N 1"
        elif scheduler == "Torque":
            sched_type = "#PBS -l nodes=1"
        if cloudType == "gcp":
            f.write(f"""#!/bin/sh
{sched_type}
cp -Rp /software/samplejobs /mnt/orangefs
cd /mnt/orangefs/samplejobs/mpi/GCP
sh mpi_prime_compile.sh
""")

        else:
            f.write(f"""#!/bin/sh
{sched_type}
cp -Rp /software/samplejobs /mnt/orangefs
cd /mnt/orangefs/samplejobs/mpi/AWS
sh mpi_prime_compile.sh
""")

    def output(self, output, error):
        if error == None or output == None:
            logger.error("Error: %s does not have the required files for checking output" % self.name)
            self.success = False
        f = open(f"{self.output_dir}/automaton.log", "r")
        for line in f:
            if line.startswith(f"The execution of the jobscript: {self.name} was successful."):
                s = open(output, "w")
                s.write(f"Preliminary job {self.name} was successful.")
                s.close()
            elif line.startswith(f"The execution of the jobscript: {self.name} failed."):
                s = open(error, "w")
                s.write(f"Preliminary job {self.name} failed.")
                s.close
                self.success = False
        f.close()
        

class MPIJob(Job):
    def __init__(self, name, output_dir, nodes, processes, instance_type=None, preemptible=False, expected_fail=False, count=1):
        self.nodes = nodes
        self.processes = processes
        self.instance_type = instance_type
        self.preemptible = preemptible
        self.expected_fail = expected_fail
        self.count = count

        super().__init__(name, output_dir, monitor=False)

    def job_text(self, f, cloudType, scheduler):
        if scheduler == "Slurm":
            f.write(f"""#!/bin/sh
#SBATCH -N {self.nodes}
#SBATCH --ntasks-per-node={self.processes}
""")
        elif scheduler == "Torque":
            f.write(f"""#!/bin/sh
#PBS -l nodes={self.nodes}:ppn={self.processes}
""")
        if cloudType == "gcp":
            if self.instance_type:
                f.write(f"#CC -gcpit {self.instance_type}\n")
            if self.preemptible:
                f.write("#CC -gcpup\n")

        f.write(f"""export SHARED_FS_NAME=/mnt/orangefs
module add openmpi/3.0.0
cd $SHARED_FS_NAME/samplejobs/mpi
""")

        for i in range(self.count):
            f.write(f"""mpirun -np {self.nodes*self.processes} $SHARED_FS_NAME/samplejobs/mpi/mpi_prime
""")

    def output(self, output, error):
        error_flag = False
        unexpected_output = False
        if error == None or output == None:
            logger.error(f"Error: {self.name} does not have the required files for checking output")
            error_flag = True
        else:
            f = open(output, "r")
            string = f.read()
            f.close()
            r = "^"
            for num in range(self.count):
                r = r + r"Using [0-9]+ tasks to scan [0-9]+ numbers\nDone. Largest prime is [0-9]+ Total primes [0-9]+\nWallclock time elapsed: ([0-9]+(|\.[0-9]+)) seconds\n"
            r = r + "$"
            m = re.search(r, string)
            if m:
                logger.info(f"The job {self.name} was a success")
                x = float(m.group(1))
                logger.info(f"match {x:.2f} seconds")
            else:
                unexpected_output = True

            f = open(error, "r")
            lines = list(f)
            if len(lines) != 0:
                logger.error(f"There was an error in the {error} file")
                error_flag = True
            else:
                logger.info(f"There were no errors found in the {error} file")
            f.close()

            if self.expected_fail:
                if string.startswith("Sorry - this exercise requires an even number of tasks.") and not error_flag:
                    logger.info(f"The test {self.name} failed as expected")
                else:
                    logger.error(f"The test {self.name} did not fail as expected")

        if error_flag or (unexpected_output and not self.expected_fail):
            self.success = False
            logger.error("There was a problem with the job. Please check the output files")

    def parameters(self):
        return ("%2d, %2d" % (self.nodes, self.processes))

class GPUJob(Job):
    def job_text(self, f, cloudType, scheduler):
        if scheduler == "Slurm":
            sched = "#SBATCH -N 1"
        elif scheduler == "Torque":
            sched = "#PBS -l nodes=1"
        if cloudType == "gcp":
            ccq = """#CC -gcpgpu
#CC -gcpgpusp 1:nvidia-tesla-p100
#CC -gcpit n1-standard-1"""
        elif cloudType == "aws":
            ccq = "#CC -it g3.4xlarge"
        f.write(f"""#!/bin/sh
{sched}
{ccq}
[ $? -eq 0 ] && echo NVIDIA-SMI successful
""")

    def output(self, output, error):
        if error == None or output == None:
            logger.error("Error: %s does not have the required files for checking output" % self.name)
            self.success = False
        else:
            f = open(output, "r")
            string = f.read()
            if "NVIDIA-SMI successful" in string:
                logger.info("The job %s was a success" % self.name)
            else:
                logger.error(f"There was a problem with the job. Please check the file {output}")
                self.success = False
            f.close()

class OrangeFSJob(Job):
    def job_text(self, f, cloudType, scheduler):
        if scheduler == "Slurm":
            sched_type = "#SBATCH -N 1"
        elif scheduler == "Torque":
            sched_type = "#PBS -l nodes=1"
        f.write(f"""#!/bin/sh
{sched_type}
pvfs2-ping -m /mnt/orangefs
dd if=/dev/zero of=/mnt/orangefs/test bs=1048576 count=1024
sleep 30
dd if=/mnt/orangefs/test of=/dev/null bs=1048576
""")

    def output(self, output, error):
        if error == None or output == None:
            logger.error("Error: %s does not have the required files for checking output" % self.name)
            self.success = False
        else:
            f = open(error, "r")
            string = f.read()
            f.close
            i = 0
            s = []
            for thing in string.split(" "):
                s.append(thing)
                i += 1
            r = r"^1073741824 bytes (1.1 GB) copied, ([0-9]+(|\.[0-9]+)) s, [0-9]+ MB/s\n1024+0 records in\n1024+0 records out\n1073741824 bytes (1.1 GB) copied, ([0-9]+(|\.[0-9]+)) s, ([0-9]+(|\.[0-9]+)) MB/s$"
            m = re.search(r, string)
            if m:
                logger.info("The job %s was a success" % self.name)
                logger.info(f"It took {s[9]} s at {s[11]} MB/s to read.\nIt took {s[21]} s at {s[23]} MB/s to write.")
            else:
                logger.error(f"Error: the file for {self.name} had an unexpected value. Please check {error} for more information.")

class ClusterCheckerJob(Job):
    def job_text(self, f, cloudtype, scheduler):
        pass

def run(args, timeout=0, die=True, output=None):
    must_close = False
    if output:
        if type(output) == str:
            output = open(output, "a")
            must_close = True
    logger.info("running command %s" % args)
    sys.stdout.flush()
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
        if output:
            output.buffer.write(new)
            output.flush()
        buffer = buffer + new
    if expired:
        logger.error(f"time limit of {timeout} expired")
    # This will also send SIGHUP to the child process.
    os.close(fd)
    pid, status = os.waitpid(pid, 0)
    end = time.time()
    final_time = end - start
    if os.WIFEXITED(status):
        status = os.WEXITSTATUS(status)
        logger.info(f"process returned {status} after {final_time} seconds")
    else:
        status = os.WTERMSIG(status)
        logger.error(f"process died from signal {status} after {final_time} seconds")
    if die and (status != 0 or expired):
        sys.exit(1)
    elif not die and (status != 0 or expired):
        fail = True
    else:
        fail = False
    buffer = buffer.decode()
    if must_close:
        output.close()
    return buffer, fail

def main():
    if len(sys.argv) > 1:
        filename = sys.argv[1]
    else:
        filename = "tester.config"

    try:
        os.stat(filename)
    except FileNotFoundError:
        logger.critical(f"configuration file {filename} not found")
        sys.exit(1)

    cp = configparser.ConfigParser()
    cp.read_file(open(filename))

    try:
        username = cp.get("tester", "username")
        cloudType = cp.get("tester", "cloudType")
        sourceimage = cp.get("tester", "sourceimage")
        ssh_private_key = cp.get("tester", "ssh_private_key")
        ssh_public_key = cp.get("tester", "ssh_public_key")
        dev_image = cp.get("tester", "dev_image")
        job_config = cp.get("tester", "job_config")
        delete_on_failure = cp.get("tester", "delete_on_failure")
        email_flag = cp.get("tester", "email_flag")
        region = cp.get("tester", "region")
        az = cp.get("tester", "az")
        scheduler = cp.get("tester", "scheduler")
    except configparser.NoSectionError:
        logger.critical("missing configuration section")
        sys.exit(1)
    except configparser.NoOptionError as e:
        logger.critical("missing configuration option: %s", e.option)
        sys.exit(1)

    if cloudType == "gcp":
        project_name = cp.get("tester", "project_name")
        service_account = cp.get("tester", "service_account")
        confFile = "gcp_tester.conf"
    else:
        confFile = "aws_tester.conf"
        KeyName = cp.get("tester", "KeyName")
        vpc_id = cp.get("tester", "vpc_id")
        subnet_id = cp.get("tester", "subnet_id")

    try:
        output_part1 = cp.get("tester", "output_part1")
        output_part2 = cp.get("tester", "output_part2")
    except configparser.NoSectionError:
        logger.critical("missing configuration section")
        sys.exit(1)
    except configparser.NoOptionError:
        logger.critical("Error: missing options in config file")
        sys.exit(1)

    output_part2 = time.strftime(output_part2)
    output_dir = output_part1 + output_part2
    start = time.time()
    os.mkdir(output_dir)

    if dev_image == "true":
        dev_image = True
    elif dev_image == "false":
        dev_image = False
    else:
        logger.critical("dev_image not set to true or false")
        sys.exit(1)

    if delete_on_failure == "true":
        delete_on_failure = True
    elif delete_on_failure == "false":
        delete_on_failure = False
    else:
        logger.critical("delete_on_failure not set to true or false")
        sys.exit(1)

    lower_sched = scheduler.lower()

    if email_flag == "true":
        email_flag = True
        smtp_port = cp.get("tester", "smtp_port")
        port = cp.get("tester", "port")
        from_addr = cp.get("tester", "from_addr")
        to_addr = cp.get("tester", "to_addr")
        output_url = cp.get("tester", "output_url")
    elif email_flag == "false":
        email_flag = False
    else:
        logger.critical("email not set to true or false")
        sys.exit(1)

    stdout_handler = logging.StreamHandler(sys.stdout)
    logging.root.addHandler(stdout_handler)

    file_handler = logging.FileHandler(f"{output_dir}/tester.log", "a", "utf-8")
    formatter = logging.Formatter("%(asctime)s>%(levelname)s:%(module)s:%(funcName)s-%(message)s")
    file_handler.setFormatter(formatter)
    logging.root.addHandler(file_handler)

    logging.root.setLevel(logging.INFO)
    
    logger.info(f"The start time is: {output_part2}")

    
    if not dev_image:
        os.chdir("../CloudyCluster")
        output, fail = run(["git", "pull", "--ff-only"], die=False)
        if fail and "fatal: Could not read from remote repository" in output:
            logger.warning("could not update CloudyCluster; continuing anyway")
        os.chdir("Build")
        current_build = run(["git", "describe", "--always"])[0].strip()
        compute = googleapiclient.discovery.build("compute", "v1")
        images = compute.images().list(project=project_name).execute()
        image_id = None
        for image in images["items"]:
            if ("%stest" % username) in image["name"] and current_build in image["name"]:
                image_id = image["name"]

        if image_id:
            image = image_id
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
            build = run(["python3", "builderdash.py", "-c", "test.yaml"], timeout=900, output=output_dir + "/builderdash.log")[0]
            build = build.split("\n")
            image = None
            for line in build:
                if line.startswith("the instance we're going to delete is"):
                    image = line.split(":")[1][1:]
            if not image:
                logger.critical("there was an error creating the image")
                sys.exit(1)

        os.chdir("../../automaton")

        ready = False
        while not ready:
            compute_client = googleapiclient.discovery.build("compute", "v1")
            request = compute_client.images().get(project=project_name, image=image)
            res = request.execute()
            if res["status"] != "READY":
                time.sleep(30)
            else:
                ready = True

        testimage = f"projects/{project_name}/global/images/{image}"
    
    else:
        testimage = sourceimage

    password = os.urandom(16).hex()
    logger.info(f"cluster username: {username}")
    logger.info(f"cluster password: {password}")
    logger.info(f"Using image {testimage}")

    config = configparser.ConfigParser()

    config.read_file(open(job_config))
    sections = config.sections()

    jobs = []
    for section in sections:
        d = {}
        s = config[section]["job_type"]
        d["name"] = section
        d["output_dir"] = output_dir
        for key in config[section]:
            if key != "job_type":
                d[key] = eval(config[section][key])
        c = eval(s)
        jobs.append(c(**d))

    job_config = ""
    i = 0
    for job in jobs:
        job.save_job(cloudType, scheduler)
        job_config = job_config + job.config(i, cloudType) + "\n"
        i = i + 1

    if cloudType == "aws":
        f = open(f"ConfigurationFiles/{confFile}", "w")
        f.write(f"""[UserInfo]
userName: {username}
password: {password}
firstName: {username}
lastName:
pempath: {ssh_private_key}

[General]
environmentName: {username}
cloudType: aws

[CloudyClusterAws]
# Specifies which AWS credentials profile to use from the ~/.aws/credentials file
#profile: myprofile
keyName: {KeyName}
instanceType: t2.small
networkCidr: 0.0.0.0/0
vpc: {vpc_id}
publicSubnet: {subnet_id}
capabilities: CAPABILITY_IAM
region: {region}
templateLocation: cloudyClusterCloudFormationTemplate.json

# Can use a pre-created template if the user doesn't want to do the advanced stuff
# This is the section that will be run when spinning up a new environment
[CloudyClusterEnvironment]
templateName: tester_template
keyName: {KeyName}
region: {region}
az: {az}

[Computation]
#jobScript1: {{"name": "testScript", "options": {{"uploadProtocol": "sftp", "uploadScript": "true", "localPath": "/home/path/test.sh", "remotePath": "/mnt/efsdata", "executeDirectory": "/mnt/efsdata"}}}}
#workflow1: {{"name": "myWorkflow", "type": "topicModelingPipeline", "options": {{"configFilePath": "/home/path/sample_experiment.py", "sharedFilesystemPath": "/home/path", "pullFromS3": "true", "s3BucketName": "testbucket"}}, "useCCQ": "true", "spotPrice": "0.60", "requestedInstanceTypes": "c4.8xlarge,c4.4xlarge", "schedulerType": "{scheduler}", "schedulerToUse": "{scheduler}"}}

{job_config}

# Template definitions
[tester_template]
description: Creates a CloudyCluster Environment that contains a single t2.small CCQ enabled {scheduler} Scheduler, a t2.small Login instance, EFS backed shared home directories, a EFS backed shared filesystem, and a t2.micro NAT instance.
vpcCidr: 10.0.0.0/16
fsChoice: OrangeFS
scheduler1: {{'type': '{scheduler}', 'ccq': 'true', 'instanceType': 't2.small', 'name': 'my{scheduler}', "fsChoice": "OrangeFS"}}
filesystem1: {{"numberOfInstances": 4, "instanceType": "t2.small", "name": "orangefs", "filesystemSizeGB": "20", "storageVolumeType": "SSD", "orangeFSIops": 0, "instanceIops": 0, 'fsChoice': 'OrangeFS'}}
efs1: {{"type": "common"}}
login1: {{'name': 'Login', 'instanceType': 't2.small', "fsChoice": "OrangeFS"}}
nat1: {{'instanceType': 't2.micro', 'accessFrom': '0.0.0.0/0'}}
""")
        f.close()

        f = open("cloudyClusterCloudFormationTemplate.json", "r+")

        file_contents = json.loads(f.read())
        f.close()
        file_contents["Mappings"]["AWSRegionArch2AMI"][region]["64"] = sourceimage

        f = open("cloudyClusterCloudFormationTemplate.json", "w")
        f.write(json.dumps(file_contents, indent=2))
        f.close()

    else:
        f = open(f"ConfigurationFiles/{confFile}", "w")
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
region: {region}
zone: {az}
pubkeypath: {ssh_public_key}
sshkeyuser: {username}
sourceimage: {testimage}


projectId: {project_name}
serviceaccountemail: {service_account}

[CloudyClusterEnvironment]
templateName: tester_template
keyName: {username}
region: {region}
az: {az}

[Computation]
# workflow1: {{"name": "gcpLargeRun", "type": "videoAnalyticsPipeline", "options": {{"instanceType": "c2-standard-4", "numberOfInstances": "2", "submitInstantly": "True", "usePreemptibleInstances": "true", "maintainPreemptibleSize": "true", "trafficVisionDir": "/software/trafficvision/", "bucketListFile": "list-us-east1", "generatedJobScriptDir": "generated_job_scripts", "trafficVisionExecutable": "process_clip.py", "jobGenerationScript": "generateJobScriptsFromBucketListFile.py", "jobPrefixString": "tv_processing_", "clip_to_start_on": "0", "clip_to_end_on": "100", "useCCQ": "true", "schedulerType": "{scheduler}", "schedulerToUse": "{lower_sched}", "skipProvisioning": "true", "timeLimit": "28800", "createPlaceholderInstances": "True"}}}}

#workflow2: {{"name": "gcpLargeRun", "type": "videoAnalyticsPipeline", "options": {{"instanceType": "c2-standard-16", "numberOfInstances": "2", "submitInstantly": "True", "usePreemptibleInstances": "true", "maintainPreemptibleSize": "true", "trafficVisionDir": "/software/trafficvision/", "bucketListFile": "bucket.list", "generatedJobScriptDir": "generated_job_scripts", "trafficVisionExecutable": "process_clip.py", "jobGenerationScript": "generateJobScriptsFromBucketListFile.py", "jobPrefixString": "tv_processing_", "clip_to_start_on": "0", "clip_to_end_on": "1000000", "useCCQ": "true", "schedulerType": "{scheduler}", "schedulerToUse": "{lower_sched}", "skipProvisioning": "true", "timeLimit": "28800", "createPlaceholderInstances": "True"}}}}

{job_config}

[tester_template]
description: Creates a CloudyCluster Environment that contains a single g1-small CCQ enabled {scheduler} Scheduler, a g1-small Login instance, a 100GB OrangeFS Filesystem, and a g1-small NAT instance.
vpcCidr: 10.0.0.0/16
fsChoice: OrangeFS
scheduler1: {{'type': '{scheduler}', 'ccq': 'true', 'instanceType': 'g1-small', 'name': '{lower_sched}', 'schedAllocationType': 'cons_res', 'fsChoice': 'OrangeFS'}}
filesystem1: {{"numberOfInstances": 4, "instanceType": "g1-small", "name": "orangefs", "filesystemSizeGB": "20", "storageVolumeType": "SSD", "orangeFSIops": 0, "instanceIops": 0, 'fsChoice': 'OrangeFS'}}
login1: {{'name': 'login', 'instanceType': 'g1-small', 'fsChoice': 'OrangeFS'}}
nat1: {{'instanceType': 'g1-small', 'accessFrom': '0.0.0.0/0'}}
""")
        f.close()

    run(["python3", "CreateEnvironmentTemplates.py", "-et", "CloudyCluster", "-cf", f"ConfigurationFiles/{confFile}", "-tn", "tester_template"], timeout=30, output=output_dir + "/template.log")

    running_automaton, fail = run(["python3", "Create_Processing_Environment.py", "-et", "CloudyCluster", "-cf", f"ConfigurationFiles/{confFile}", "-all", "-nd"], timeout=7200, die=False, output=output_dir + "/automaton.log")

    for job in jobs:
        job.cleanup_job()

    files = {}
    for line in running_automaton.split("\n"):
        if line.startswith("Downloading"):
            if line.split(" ")[4] not in files:
                files[line.split(" ")[4]] = {}
            if line.split(" ")[1].endswith(".o"):
                files[line.split(" ")[4]]["output"] = line.split(" ")[1]
            elif line.split(" ")[1].endswith(".e"):
                files[line.split(" ")[4]]["error"] = line.split(" ")[1]


    for job in jobs:
        if job.job_filename not in files:
            output = None
            error = None
        else:
            if "output" in files[job.job_filename]:
                output = files[job.job_filename]["output"]
            else:
                output = None
            if "error" in files[job.job_filename]:
                error = files[job.job_filename]["error"]
            else:
                error = None
        job.output(output, error)


    success_count = 0
    fail_count = 0
    status = None
    for job in jobs:
        logger.info(f"job: {job}")
        if not job.success:
            logger.info("%-20s %-20s %-20s" % (job, job.parameters, "failed"))
            fail_count += 1
        else:
            logger.info("%-20s %-20s %-20s" % (job, job.parameters, "succeeded"))
            success_count += 1

    if fail_count != 0:
        logger.info(f"Status: Failure count of {fail_count}. Success count of {success_count}")
        status = f"{fail_count} out of {success_count + fail_count} jobs failed"
    else:
        logger.info("Status: Success")
        status = "succeeded"

    if dev_image == True:
        image = f"Used the dev image: {testimage}"
    else:
        image = f"Used the userapps image: {sourceimage}.\nCreated dev image: {testimage}"

    if email_flag:
        message = f"""From: {from_addr}
To: {to_addr}
Subject: CloudyCluster: {success_count} of {success_count + fail_count} jobs successful
Date: {email.utils.formatdate()}
Message-Id: {email.utils.make_msgid()}

{image}.

Full output is available at {output_url}{output_part2}.
"""

        context = ssl.create_default_context()

        try:
            server = smtplib.SMTP(smtp_port, port)
            server.starttls(context=context)
            server.sendmail(from_addr, to_addr, message)
        except Exception as e:
            logger.error(e)
        finally:
            server.quit()
    
    if "failed" in status:
        if delete_on_failure:
            logger.error("There was a problem with the last run of automaton. Initiating a cleanup.")
            fail = run(["python3", "Create_Processing_Environment.py", "-et", "CloudyCluster", "-cf", f"ConfigurationFiles/{confFile}", "-dff"], timeout=3600, die=False)[1]

            if fail:
                logger.critical("Could not cleanup. You will have to manually delete the created resources.")
                sys.exit(1)

    elif "succeeded" in status:
        run(["python3", "Create_Processing_Environment.py", "-et", "CloudyCluster", "-cf", f"ConfigurationFiles/{confFile}", "-dff"], timeout=3600, die=False)

    end = time.strftime("%Y%m%d-%H%M")
    logger.info(f"The end time is: {end}")

    finish = time.time()

    final_time = finish - start
    logger.info(f"It took {final_time} seconds to complete the Automaton run")


if __name__ == "__main__":
    main()


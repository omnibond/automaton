import configparser
import os
import select
import signal
import sys
import termios
import time
import re

import googleapiclient.discovery

class Job:
    def __init__(self, name, monitor=True):
        self.name = name
        self.monitor = monitor

        self.job_filename = f"{self.name}.sh"
        self.job_path = f"{os.getcwd()}/{self.job_filename}"
        self.success = True

    def __repr__(self):
        return f"<{self.__class__.__name__} {self.name}>"

    def save_job(self):
        f = open(self.job_path, "w")
        self.job_text(f)
        f.close()

    def job_text(self, f):
        raise Exception("job_text undefined")

    def config(self, n):
        if self.monitor:
            monitor = "true"
        else:
            monitor = "false"
        return f"""jobScript{n}: {{"name": "{self.name}", "options": {{"uploadProtocol": "sftp", "monitorJob": "{monitor}", "timeout": 0, "uploadScript": "true", "localPath": "{self.job_path}", "remotePath": "/mnt/orangefs/{self.job_filename}", "executeDirectory": "/mnt/orangefs"}}}}"""

    def output(self, output, error):
        pass
    
    def cleanup_job(self):
        os.unlink(self.job_path)

class MPIPreliminaryJob(Job):
    def job_text(self, f):
        f.write("""#!/bin/sh
#SBATCH -N 1
cp -Rp /software/samplejobs /mnt/orangefs
cd /mnt/orangefs/samplejobs/mpi/GCP
sh mpi_prime_compile.sh
""")

class MPIJob(Job):
    def __init__(self, name, nodes, processes, instance_type=None, preemptible=False, expected_fail=False):
        self.nodes = nodes
        self.processes = processes
        self.instance_type = instance_type
        self.preemptible = preemptible
        self.expected_fail = expected_fail

        super().__init__(name, monitor=False)

    def job_text(self, f):
        f.write(f"""#!/bin/sh
#SBATCH -N {self.nodes}
#SBATCH --ntasks-per-node={self.processes}
""")

        if self.instance_type:
            f.write(f"#CC -gcpit {self.instance_type}\n")
        if self.preemptible:
            f.write("#CC -gcpup\n")

        f.write(f"""export SHARED_FS_NAME=/mnt/orangefs
module add openmpi/3.0.0
cd $SHARED_FS_NAME/samplejobs/mpi
mpirun -np {self.nodes*self.processes} $SHARED_FS_NAME/samplejobs/mpi/mpi_prime
""")

    def output(self, output, error):
        if error == None or output == None:
            print("Error: %s does not have the required files for checking output" % self.name)
            self.success = False
        else:
            f = open(output, "r")
            string = f.read()
            print("string:", repr(string))
            r = r"^Using [0-9]+ tasks to scan [0-9]+ numbers\nDone. Largest prime is [0-9]+ Total primes [0-9]+\nWallclock time elapsed: ([0-9]+(|\.[0-9]+)) seconds\n$"
            m = re.search(r, string)
            if m:
                print("The job %s was a success" % self.name)
                x = float(m.group(1))
                print("match %f seconds" % x)
            else:
                print(f"There was a problem with the job. Please check the file {output}")
                self.success = False
            f.close()

            f = open(error, "r")
            lines = list(f)
            print("lines:", lines)
            if len(lines) != 0:
                print(f"There was an error in the {error} file")
                self.success = False
            else:
                print(f"There were no errors found in the {error} file")
            f.close()

            if self.expected_fail:
                self.success = not self.success
                if not self.success:
                    print("The test %s did not fail as expected" % self.name)
                else:
                    print("The test %s failed as expected" % self.name)

class GPUJob(Job):
    def job_text(self, f):
        f.write("""#!/bin/sh
#SBATCH -N 1
#CC -gcpgpu
#CC -gcpgpusp 1:nvidia-tesla-p100
#CC -gcpit n1-standard-1
nvidia-smi
[ $? -eq 0 ] && echo NVIDIA-SMI successful
""")

    def output(self, output, error):
        if error == None or output == None:
            print("Error: %s does not have the required files for checking output" % self.name)
            self.success = False
        else:
            f = open(output, "r")
            string = f.read()
            print("string:", repr(string))
            if "NVIDIA-SMI successful" in string:
                print("The job %s was a success" % self.name)
            else:
                print(f"There was a problem with the job. Please check the file {output}")
                self.success = False
            f.close()

class OrangeFSJob(Job):
    def job_text(self, f):
        f.write("""#!/bin/sh
#SBATCH -N 1
pvfs2-ping -m /mnt/orangefs
dd if=/dev/zero of=/mnt/orangefs/test bs=1048576 count=1024
sleep 30
dd if=/mnt/orangefs/test of=/dev/null bs=1048576
""")

    def output(self, output, error):
        pass

def run(args, timeout=0, die=True, output=None):
    must_close = False
    if output:
        if type(output) == str:
            output = open(output, "a")
            must_close = True
    else:
        output = sys.stdout
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
        output.buffer.write(new)
        output.flush()
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
        dev_image = cp.get("tester", "dev_image")
        auto_delete = cp.get("tester", "auto_delete")
    except configparser.NoSectionError:
        print("missing configuration section")
        sys.exit(1)
    except configparser.NoOptionError:
        print("missing configuration option")
        sys.exit(1)

    if dev_image == "true":
        dev_image = True
    elif dev_image == "false":
        dev_image = False
    else:
        print("dev_image not true or false")
        sys.exit(1)

    if auto_delete == "true":
        auto_delete = True
    elif auto_delete == "false":
        auto_delete = False
    else:
        print("auto_delete not true or false")
        sys.exit(1)

    os.chdir("..")

    if not dev_image:
        os.chdir("CloudyCluster/Build")
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
            build = run(["python3", "builderdash.py", "-c", "test.yaml"], timeout=900)[0]
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

        testimage = f"projects/{project_name}/global/images/{image}"
    
    else:
        testimage = sourceimage

    password = os.urandom(16).hex()
    print("cluster username", username)
    print("cluster password", password)
    print("Using image", testimage)

    jobs = [
        MPIPreliminaryJob("test1"),
        MPIJob("test2", 2, 2),
        MPIJob("test3", 2, 2),
        MPIJob("test4", 4, 2),
        MPIJob("test5", 2, 2),
        MPIJob("test6", 10, 2),
        MPIJob("test7", 4, 4, instance_type="c2-standard-4"),
        MPIJob("test8", 4, 4, preemptible=True),
        GPUJob("test9"),
        MPIJob("test10", 4, 2),
        OrangeFSJob("test11")
    ]

    job_config = ""
    i = 0
    for job in jobs:
        job.save_job()
        job_config = job_config + job.config(i) + "\n"
        i = i + 1

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
sourceimage: {testimage}


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

{job_config}

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

    creating_templates = run(["python3", "CreateEnvironmentTemplates.py", "-et", "CloudyCluster", "-cf", "ConfigurationFiles/gcp_tester.conf", "-tn", "tester_template"], timeout=30)[0]
    print("created template:", creating_templates)

    running_automaton, fail = run(["python3", "Create_Processing_Environment.py", "-et", "CloudyCluster", "-cf", "ConfigurationFiles/gcp_tester.conf", "-all"], timeout=7200, die=False)
    print("automaton run:", running_automaton)

    if fail and auto_delete:
        print("There was a problem with the last run of automaton. Initiating a cleanup.")
        cleanup_automaton, fail = run(["python3", "Create_Processing_Environment.py", "-et", "CloudyCluster", "-cf", "ConfigurationFiles/gcp_tester.conf", "-dff"], timeout=3600, die=False)
        print("automaton cleanup:", cleanup_automaton)

        if fail:
            print("Could not cleanup. You will have to manually delete the created resources.")
            sys.exit(0)

    for job in jobs:
        job.cleanup_job()

    files = {}
    for line in running_automaton.split("\n"):
        if line.startswith("Downloading"):
            print(line.split(" "))
            if line.split(" ")[4] not in files:
                files[line.split(" ")[4]] = {}
            if line.split(" ")[1].endswith(".o"):
                files[line.split(" ")[4]]["output"] = line.split(" ")[1]
            elif line.split(" ")[1].endswith(".e"):
                files[line.split(" ")[4]]["error"] = line.split(" ")[1]
    print("files:", files)

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
    for job in jobs:
        print("job:", job)
        if not job.success:
            print("fail")
            fail_count += 1
        elif job.success:
            print("succeed")
            success_count += 1
        else:
            print("other")

    if fail_count != 0:
        print(f"Status: Failure count of {fail_count}. Success count of {success_count}")
    else:
        print("Status: Success")
    

if __name__ == "__main__":
    main()

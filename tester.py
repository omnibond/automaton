import configparser
import os
import select
import signal
import sys
import termios
import time
import re
import email.utils
import smtplib
import ssl
import logging

logger = logging.getLogger("tester")

import googleapiclient.discovery

class Job:
    def __init__(self, name, output_dir, monitor=True):
        self.name = name
        self.output_dir = output_dir
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
        return f"""jobScript{n}: {{"name": "{self.name}", "options": {{"uploadProtocol": "sftp", "monitorJob": "{monitor}", "timeout": 0, "uploadScript": "true", "localPath": "{self.job_path}", "remotePath": "/mnt/orangefs/{self.job_filename}",
        "directory": "{self.output_dir}", "executeDirectory": "/mnt/orangefs"}}}}"""

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
    def __init__(self, name, output_dir, nodes, processes, instance_type=None, preemptible=False, expected_fail=False):
        self.nodes = nodes
        self.processes = processes
        self.instance_type = instance_type
        self.preemptible = preemptible
        self.expected_fail = expected_fail

        super().__init__(name, output_dir, monitor=False)

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
        if error == None or output == None:
            print("Error: %s does not have the required files for checking output" % self.name)
            self.success = False
        

def run(args, timeout=0, die=True, output=None):
    must_close = False
    if output:
        if type(output) == str:
            output = open(output, "a")
            must_close = True
    print("running command %s" % args)
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
    logger.info(buffer)
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
    cp.read(filename)

    try:
        username = cp.get("tester", "username")
        project_name = cp.get("tester", "project_name")
        sourceimage = cp.get("tester", "sourceimage")
        service_account = cp.get("tester", "service_account")
        ssh_private_key = cp.get("tester", "ssh_private_key")
        ssh_public_key = cp.get("tester", "ssh_public_key")
        dev_image = cp.get("tester", "dev_image")
        delete_on_failure = cp.get("tester", "delete_on_failure")
        email_flag = cp.get("tester", "email_flag")
    except configparser.NoSectionError:
        logger.critical("missing configuration section")
        sys.exit(1)
    except configparser.NoOptionError as e:
        logger.critical("missing configuration option: %s", e.option)
        sys.exit(1)

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
        logger.critical("dev_image not true or false")
        sys.exit(1)

    if delete_on_failure == "true":
        delete_on_failure = True
    elif delete_on_failure == "false":
        delete_on_failure = False
    else:
        logger.critical("delete_on_failure not true or false")
        sys.exit(1)

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
        logger.critical("email not true or false")
        sys.exit(1)

    logging.basicConfig(filename=f"{output_dir}/tester.log", level=logging.INFO)
    
    statement = f"The start time is: {output_part2}"
    print(statement)
    logger.info(statement)

    os.chdir("../CloudyCluster")
    run(["git", "pull"])[0]
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
            build = run(["python3", "builderdash.py", "-c", "test.yaml"], timeout=900, output=output_dir + "/builderdash.log")[0]
            build = build.split("\n")
            image = None
            for line in build:
                if line.startswith("the instance we're going to delete is"):
                    image = line.split(":")[1][1:]
            if not image:
                logger.critical("there was an error creating the image")
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
    statement = f"cluster username: {username}"
    print(statement)
    logger.info(statement)
    statement = f"cluster password: {password}"
    print(statement)
    logger.info(statement)
    statement = f"Using image {testimage}"
    print(statement)
    logger.info(statement)

    jobs = [
        MPIPreliminaryJob("test1", output_dir),
        MPIJob("test2", output_dir, 2, 2),
        MPIJob("test3", output_dir, 3, 3, expected_fail=True),
        MPIJob("test4", output_dir, 4, 2),
        MPIJob("test5", output_dir, 3, 3, expected_fail=True),
        MPIJob("test6", output_dir, 10, 2),
        MPIJob("test7", output_dir, 4, 4, instance_type="c2-standard-4"),
        MPIJob("test8", output_dir, 4, 4, preemptible=True),
        GPUJob("test9", output_dir),
        MPIJob("test10", output_dir, 4, 2),
        OrangeFSJob("test11", output_dir)
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

    run(["python3", "CreateEnvironmentTemplates.py", "-et", "CloudyCluster", "-cf", "ConfigurationFiles/gcp_tester.conf", "-tn", "tester_template"], timeout=30, output=output_dir + "/template.log")[0]

    running_automaton, fail = run(["python3", "Create_Processing_Environment.py", "-et", "CloudyCluster", "-cf", "ConfigurationFiles/gcp_tester.conf", "-all", "-nd"], timeout=7200, die=False, output=output_dir + "/automaton.log")

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
        statement = f"job: {job}"
        print(statement)
        logger.info(statement)
        if not job.success:
            statement = "fail"
            print(statement)
            logger.info(statement)
            fail_count += 1
        else:
            statement = "succeed"
            print(statement)
            logger.info(statement)
            success_count += 1

    if fail_count != 0:
        statement = f"Status: Failure count of {fail_count}. Success count of {success_count}"
        print(statement)
        logger.info(statement)
        status = f"{fail_count} out of {success_count + fail_count} jobs failed"
    else:
        statement = "Status: Success"
        print(statement)
        logger.info(statement)
        status = "succeeded"


    if email_flag:
        message = f"""From: {from_addr}
To: {to_addr}
Subject: test {success_count}/{success_count + fail_count} successful
Date: {email.utils.formatdate()}
Message-Id: {email.utils.make_msgid()}

This run of Automaton:
{status}.

Used image: {testimage}.

Full output is available at {output_url}{output_part2}.
"""

        context = ssl.create_default_context()

        try:
            server = smtplib.SMTP(smtp_port, port)
            server.starttls(context=context)
            server.sendmail(from_addr, to_addr, message)
        except Exception as e:
            print(e)
        finally:
            server.quit()
    
    if "failed" in status:
        if delete_on_failure:
            logger.error("There was a problem with the last run of automaton. Initiating a cleanup.")
            cleanup_automaton, fail = run(["python3", "Create_Processing_Environment.py", "-et", "CloudyCluster", "-cf", "ConfigurationFiles/gcp_tester.conf", "-dff"], timeout=3600, die=False)

            if fail:
                logger.critical("Could not cleanup. You will have to manually delete the created resources.")
                sys.exit(1)

    elif "succeeded" in status:
        run(["python3", "Create_Processing_Environment.py", "-et", "CloudyCluster", "-cf", "ConfigurationFiles/gcp_tester.conf", "-dff"], timeout=3600, die=False)

    end = time.strftime("%Y%m%d-%H%M")
    statement = f"The end time is: {end}"
    print(statement)
    logger.info(statement)

    finish = time.time()

    final_time = finish - start
    statement = f"It took {final_time} seconds to complete the Automaton run"
    print(statement)
    logger.info(statement)


if __name__ == "__main__":
    main()

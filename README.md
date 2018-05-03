# automaton
Automation system for CloudyCluster environment creation and job submission, that has a dual use of both workflow integration and testing system.  It is a collaborative project between the CU Dice Lab and Omnibond.

# au·tom·a·ton  
/ôˈtämədən,ôˈtäməˌtän/  
noun  
-a moving mechanical device made in imitation of a human being.  
-a machine that performs a function according to a predetermined set of coded instructions, especially one capable of a range of programmed responses to different circumstances.  

The Automaton Project or academically referenced as PAW (Provisioning And Workflow) is a management tool is an tool designed to automate the steps required to dynamically provisioning a large scale cluster environment in the cloud, executing a set of jobs or a custom workflow, and after the jobs have completed de-provisioning the cluster environment in a single operation. For more details on the technical implementation and design please read the following paper located at: https://tigerprints.clemson.edu/computing_pubs/38.  The original release of the PAW framework (where you can academically reference it) can be located at: https://www.cs.clemson.edu/dice/paw/

It is driven by a single configuration file that defines all of the parameters required to create a fully functional HPC Environment in the Cloud. It is designed to be modular and pluggable to allow it to support a variety of HPC Schedulers, environment types, workflows, and cloud providers. This initial implementation of PAW utilizes CloudyCluster and AWS to perform the dynamic provisioning, workflow execution, and automated de-provisioning of the HPC Environment. The sections of the configuration file and their parameters are discussed further on in this document.

This framework + CloudyCluster was utilized by the 1.1m vCPU run referenced here: https://aws.amazon.com/blogs/aws/natural-language-processing-at-clemson-university-1-1-million-vcpus-ec2-spot-instances/

Check the long readme for usage instructions. https://github.com/omnibond/automaton/blob/master/README

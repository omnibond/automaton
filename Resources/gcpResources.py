import os
import time
import traceback
import sys
from resources import Resource 
import googleapiclient.discovery
#from google.cloud import datastore
 #compute = googleapiclient.discovery.build('compute', 'v1')

class GcpResources(Resource):
    def __init__(self, **kwargs):
        super(GcpResources, self).__init__(**kwargs)

    def createClient(self, service, version):
        # Creating a GCP api client
        try:
            compute = googleapiclient.discovery.build(service, version)
            return {"status": "success", "payload": compute}
        except Exception as e:
            return {"status": "error", "payload": {"error": "There was an exception encoutered when trying to obtain a google api session.", "traceback": ''.join(traceback.format_exc())}}

    def createControlResources(self, templateLocation, resourceName, options):
        # Launch a Control Node through gcp and return the id
        print vars(self)
        service = "compute"
        version = "v1"
        response = self.createClient(service, version)
        if response['status'] != "success":
            return {"status": "error"}
        else:
            client = response['payload']
        print "ResourceName is "
        print resourceName
        body = self.makeBody(resourceName, options)
        instance = client.instances().insert(project=options['projectid'], zone=options['zone'], body=body)
        request = instance.execute()
        response = self.createClient(service, version)
        if response['status'] != "success":
            return{"status": "error"}
        else:
            client = response['payload']
        while True:
            result = client.zoneOperations().get(project=options['projectid'], zone=options['zone'], operation=str(request['name'])).execute()
            if result['status'] == 'DONE':
                print "GCP Control Node has been Created"
                if "error" in result:
                    return {"status": "error", "payload": {"error": str(result['error']), "traceback": ''.join(traceback.format_stack())}}
                else:
                    time.sleep(10)
                    response = self.createClient(service, version)
                    client = response['payload']
                    result = client.instances().list(project=options['projectid'], zone=options['zone'], filter='(status eq RUNNING) (name eq ' + str(resourceName) + ')').execute()
                    #print str(result)
                    remoteIp = result['items'][0]['networkInterfaces'][0]['accessConfigs'][0]['natIP']
                    #return {"status": "success", "payload": request['name'], "controlIP": str(remoteIp)}
                    return {"status": "success", "payload": str(remoteIp)}
            time.sleep(5)

    #####Delete the Google Cloud control node with the web route.  
    def deleteControlResources(self, resourceName, options):
        service = "compute"
        version = "v1"
        response = self.createClient(service, version)
        if response['status'] != "success":
            return {"status": "error"}
        else:
            client = response['payload']
        params = {}
        instance = client.instances().delete(project=self.project, zone=self.zone, instance=self.instanceName)
        request = instance.execute()
        while True:
            result = client.zoneOperations().get(project=self.projectId, zone=zone, operation=request['name'])
            if result['status'] == 'DONE':
                print "GCP Control Node has been Deleted"
                if "error" in result:
                    return {"status": "error", "payload": {"error": str(result['error']), "traceback": ''.join(traceback.format_stack())}}
                else:
                    return {"status": "success", "payload": request['name']}        

    def makeBody(self, resourceName, options):
        with open(str(options['pubkeypath']), 'rb') as f:
            tempsshkey = str(options['sshkeyuser'])+':'+f.read()       
        autoDelete = "true"
        machineType = "zones/%s/machineTypes/%s" % (options['zone'], options['instancetype'])
        body = {
            'name': resourceName,
            'machineType': machineType,
            'tags': {
                'items': [
                  'http-server',
                  'https-server'
              ]
            },
            'disks': [
                {
                    'boot': True,
                    'autoDelete': autoDelete,
                    'initializeParams': {'sourceImage': options['sourceimage']},
                    'diskSizeGb': '45'
                }
            ],

            'networkInterfaces': [{
                'network': 'global/networks/default',
                'accessConfigs': [
                    {'type': 'ONE_TO_ONE_NAT', 'name': 'External NAT'}
                ]
            }],

            'serviceAccounts': [{
                'email': os.environ['SERVICE_ACCOUNT_EMAIL'],
                'scopes': [
                    'https://www.googleapis.com/auth/devstorage.read_write',
                    "https://www.googleapis.com/auth/datastore",
                    "https://www.googleapis.com/auth/pubsub",
                    "https://www.googleapis.com/auth/servicecontrol",
                    "https://www.googleapis.com/auth/service.management",
                    "https://www.googleapis.com/auth/logging.write",
                    "https://www.googleapis.com/auth/monitoring.write",
                    "https://www.googleapis.com/auth/compute",
                    'https://www.googleapis.com/auth/logging.write',
                    "https://www.googleapis.com/auth/trace.append",
                    'https://www.googleapis.com/auth/cloud-platform'
                ]
            }],

            'metadata': {
                'items': [{
                    'key': 'bucket',
                    'value': None
                }, {
                    'key': 'ssh-keys',
                    'value': tempsshkey
                },
                   {'key': 'block-project-ssh-keys',
                    'value': True
                }]
            }
        }
        return body










import os
import time
import traceback
import sys
from resources import Resource 
import googleapiclient.discovery


class GcpResources(Resource):
    def __init__(self, **kwargs):
        super(GcpResources, self).__init__(**kwargs)

    def createClient(self, service, version):
        # Creating a GCP api client
        try:
            compute = googleapiclient.discovery.build(service, version, cache_discovery=False)
            return {"status": "success", "payload": compute}
        except Exception as e:
            return {"status": "error", "payload": {"error": "There was an exception encountered when trying to obtain a google api session.", "traceback": ''.join(traceback.format_exc())}}

    def getStartupKey(self, instance, options):
        try:
            client = self.createClient("compute", "v1")["payload"]
            correct_key = None
            counter = 0
            while not correct_key and counter < 5:
                request = client.instances().get(project=options['projectid'], zone=options['zone'], instance=instance)
                response = request.execute()
                metadata = response["metadata"]
                if "items" in metadata:
                    for attribute in metadata["items"]:
                        if attribute["key"] == "startup_key":
                            correct_key = attribute["value"]
                            return {"status": "success", "payload": correct_key}
                time.sleep(20)
                counter += 1
            if not correct_key:
                return {"status": "error", "payload": {"error": "startup_key not found", "traceback": "".join(traceback.format_stack())}}
        except Exception as e:
            return {"status": "error", "payload": {"error": "There was an error trying to get the startup key.", "traceback": ''.join(traceback.format_exc())}}

    def createControlResources(self, templateLocation, resourceName, options):
        # Launch a Control Node through gcp and return the id
        print(vars(self))
        service = "compute"
        version = "v1"
        response = self.createClient(service, version)
        if response['status'] != "success":
            print("createClient failed:", response)
            return {"status": "error"}
        else:
            client = response['payload']
        print("ResourceName is ")
        print(resourceName)
        body = self.makeBody(resourceName, options)
        instance = client.instances().insert(project=options['projectid'], zone=options['zone'], body=body)
        request = instance.execute()
        response = self.createClient(service, version)
        if response['status'] != "success":
            return{"status": "error"}
        else:
            client = response['payload']

        counter = 0
        while True:
            result = client.zoneOperations().get(project=options['projectid'], zone=options['zone'], operation=str(request['name'])).execute()
            if result['status'] == 'DONE':
                print("GCP Control Node has been created")
                if "error" in result:
                    return {"status": "error", "payload": {"error": str(result['error']), "traceback": ''.join(traceback.format_stack())}}
                else:
                    print("Obtaining the IP address from the " + str(resourceName) + " Control Resources.")
                    time.sleep(10)
                    response = self.createClient(service, version)
                    client = response['payload']
                    result = client.instances().list(project=options['projectid'], zone=options['zone'], filter='(status eq RUNNING) (name eq ' + str(resourceName) + ')').execute()
                    #print str(result)
                    remoteIp = result['items'][0]['networkInterfaces'][0]['accessConfigs'][0]['natIP']
                    instance = result["items"][0]["name"]
                    #return {"status": "success", "payload": request['name'], "controlIP": str(remoteIp)}
                    return {"status": "success", "payload": str(remoteIp), "instance": instance}
            else:
                print("You have waited " + str(counter) + " minutes for the Control Resources to enter the requested state.")
                counter += 1
            time.sleep(60)

    #####Delete the Google Cloud control node with the web route.  
    def deleteControlResources(self, resourceName, options):
        response = self.createClient("compute", "v1")
        if response['status'] != "success":
            return {"status": "error"}
        else:
            client = response['payload']
        params = {}
        instance = client.instances().delete(project=options['projectid'], zone=options['zone'], instance=resourceName)
        request = instance.execute()
        while True:
            result = client.zoneOperations().get(project=options['projectid'], zone=options['zone'], operation=request['name']).execute()
            if result['status'] == 'DONE':
                print("GCP Control Node has been Deleted")
                if "error" in result:
                    return {"status": "error", "payload": {"error": str(result['error']), "traceback": ''.join(traceback.format_stack())}}
                else:
                    return {"status": "success", "payload": request['name']}        

    def makeBody(self, resourceName, options):
        with open(str(options['pubkeypath']), 'r') as f:
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
                    'diskSizeGb': '55'
                }
            ],

            'networkInterfaces': [{
                'network': 'global/networks/default',
                'accessConfigs': [
                    {'type': 'ONE_TO_ONE_NAT', 'name': 'External NAT'}
                ]
            }],

            'serviceAccounts': [{
                'email': options['serviceaccountemail'],
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










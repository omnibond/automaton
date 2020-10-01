# Copyright 2017
#
# Licensed under the Apache License, Version 2.0, <LICENSE-APACHE or
# http://apache.org/licenses/LICENSE-2.0> or the MIT license <LICENSE-MIT or
# http://opensource.org/licenses/MIT> or the LGPL, Version 2.0 <LICENSE-LGPLv2 or
# https://www.gnu.org/licenses/old-licenses/lgpl-2.0.txt>, at your option.
# This file may not be copied, modified, or distributed except according to those terms.


import sys
import argparse
import os
import uuid
import configparser
import ast
sys.path.append(os.path.dirname(os.path.realpath(__file__))+str("/EnvironmentTemplates"))


def printTemplatesForEnvironmentType(environmentTemplate):
    values = environmentTemplate.listTemplates()
    if values['status'] != "success":
        errorMessage = str(values['payload']['error']) + "\n" + str(values['payload']['traceback'])
        return {"status": "error", "payload": errorMessage}
    else:
        templateList = values['payload']
        returnString = ""
        returnString += "\nThe templates created for the " + str(environmentTemplate.environmentType) + " Environment Type are:\n\n"
        for template in templateList:
            returnString += str(template) + "\n"
            returnString += "    " + str(templateList[template]) + "\n\n"
        return {"status": "success", "payload": returnString}


def main():
    parser = argparse.ArgumentParser(description="A utility that users can utilize to create/modify/delete Environment Templates.")
    parser.add_argument('-V', '--version', action='version', version='ccAutomaton Environment Template Generator (version 1.0')
    parser.add_argument('-tn', '--templateName', help="The name of the template you wish to generate. This name should be the same as the section in the ccAutomaton.conf file that contains the configuration for the Environment.", default=None)
    parser.add_argument('-et', '--environmentType', help="The type of environment to create the template for.", default=None)
    parser.add_argument('-lt', "--listTemplates", action='store_true', help="Print out the list of templates available for the specified Environment Type.")
    parser.add_argument('-dt', "--deleteTemplate", action='store_true', help="Delete the specified template file if it exists.")
    parser.add_argument('-cf', "--configFilePath", help="The path to the configuration file that contains your configuration files.")

    args = parser.parse_args()

    cloudType = None
    templateName = args.templateName
    environmentType = args.environmentType
    listTemplates = args.listTemplates
    deleteTemplate = args.deleteTemplate
    configFilePath = args.configFilePath
    if not listTemplates:
        if templateName is None:
            # Check and see if there was an argument passed. If there was then we use that as the environment type
            try:
                templateName = args[1]
            except Exception as e:
                print("You must specify a template name when running the ccAutomaton Environment Generator utility. This can be done using the -tn argument or by adding the template name type after the command.")
                sys.exit(0)

    if environmentType is None:
        # Check and see if there was an argument passed. If there was then we use that as the environment type
        try:
            environmentType = args[1]
        except Exception as e:
            print("You must specify an environment type when running the ccAutomaton Environment Generator utility. This can be done using the -et argument or by adding the environment type after the command.")
            sys.exit(0)

    # If we are just listing or deleting the template(s) then we don't need any of this stuff other than the environment name
    if listTemplates or deleteTemplate:
        kwargs = {"environmentType": environmentType, "parameters": None, "templateName": None}

        if deleteTemplate:
            kwargs['templateName'] = templateName

        # Load the module (ex: import cloudycluster)
        environmentTemplateClass = __import__(str(environmentType).lower() + "Templates")

        # Get the actual class that we need to instantiate (ex: from cloudycluster import CloudyCluster)
        myClass = getattr(environmentTemplateClass, environmentType + "Template")

        # Instantiate the class with the required parameters
        environmentTemplate = myClass(**kwargs)

        if listTemplates:
            values = printTemplatesForEnvironmentType(environmentTemplate)
        else:
            # If it isn't listTemplates it must be deleteTemplate
            values = environmentTemplate.delete()
        print(values['payload'])
        sys.exit(0)

    if configFilePath is None:
        try:
            configFilePath = args[1]
        except Exception as e:
            print("You must specify the path to the conf file when running the ccAutomaton Environment Template Generator utility.  This can be done using the -cf argument.")
            sys.exit(0)

    # Read in configuration values from the ccAutomaton.conf file from the local directory
    parser = configparser.ConfigParser()
    parser.read(configFilePath)
    sections = parser.sections()
    configurationFileParameters = {}
    for section in sections:
        configurationFileParameters[str(section)] = {}
        options = parser.options(section)
        for option in options:
            try:
                configurationFileParameters[str(section)][option] = parser.get(section, option)
            except Exception as e:
                print(e)
                configurationFileParameters[str(section)][option] = None

    # Check and see if the requested environment/cloud type is configured in the conf file
    try:
        configurationFileParameters[str(templateName)]
    except Exception as e:
        print("Unable to find the configuration for the " + str(templateName) + " template in the "+str(configFilePath)+ " file. Please check the file and try again.")
        sys.exit(0)

    # If GCP check and see if the login node and scheduler names are lower case, if not make them change it, and check to make sure the character length is less than 18.  If it is more than 18, sys exit and make them do it again.
    if str(configurationFileParameters['General']['cloudtype']).lower() == "gcp":
        # try:
        for i in configurationFileParameters[str(templateName)]:
            if "login" in i or "scheduler" in i or "filesystem" in i:
                nameCheck = ast.literal_eval(configurationFileParameters[templateName][i])['name']
                if len(str(nameCheck)) > 18:
                    print("The name for " + str(i) + " is too many characters.  It needs to be 18 or less.")
                    sys.exit(0)
                for letter in str(nameCheck):
                    if letter.isupper():
                        print("There is an uppercase letter in your " + str(i) + "'s instance's name.  All letters must be lowercase for gcp.")
                        sys.exit(0)

    kwargs = {"environmentType": environmentType, "parameters": configurationFileParameters[str(templateName)], "templateName": str(templateName)}
    # Load the module (ex: import cloudycluster)
    environmentTemplateClass = __import__(str(environmentType).lower()+"Templates")

    # Get the actual class that we need to instantiate (ex: from cloudycluster import CloudyCluster)
    myClass = getattr(environmentTemplateClass, environmentType+"Template")

    # Instantiate the class with the required parameters
    environmentTemplate = myClass(**kwargs)

    # Here we actually create the template from the configuration file
    cloudType = configurationFileParameters['General']['cloudtype']

    values = environmentTemplate.create(cloudType)
    if values['status'] != "success":
        print(values['payload']['error'])
        print(values['payload']['traceback'])
        sys.exit(0)
    else:
        print(values['payload'])
        sys.exit(0)

main()

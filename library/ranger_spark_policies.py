#!/usr/bin/python
# -*- coding: utf-8 -*-

#
# This software is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This software is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this software. If not, see <http://www.gnu.org/licenses/>.


DOCUMENTATION = '''
---
module: ranger_spark_policies
short_description: Manage definition of Spark Policy in Apache Ranger
description:
     - This module will allow you to manage Spark policy in Apache Ranger.
     - Please refer to Apache Ranger documentation for authorization policy concept and usage.
options:
  admin_url:
    description:
      - The Ranger base URL to access Ranger API. Same host:port as the Ranger Admin GUI. https://myranger.server.com:6182
    required: true
    default: None
    aliases: []
  admin_username:
    description:
      - The user name to log on the Ranger Admin. Must have enough rights to manage policies.
    required: true
    default: None
    aliases: []
  admin_password:
    description:
      - The password associated with the admin_username
    required: true
    default: None
    aliases: []
  ssl_verify:
    description:
      - Useful if Ranger Admin connection is using SSL. If no, SSL certificates will not be validated. This should only be used on sites using self-signed certificates.
    required: false
    default: True
    aliases: []
  ca_bundle_file:
    description:
      - Useful if Ranger Admin connection is using SSL. Allow to specify a CA_BUNDLE file, a file that contains root and intermediate certificates to validate the Ranger Admin certificate.
      - In its simplest case, it could be a file containing the server certificate in .pem format.
      - This file will be looked up on the remote system, on which this module will be executed.
    required: false
    default: None
    aliases: []
  service_name:
    description:
      - In most cases, you should not need to set this parameter. It define the Ranger Admin Spark service, typically <yourClusterName>_spark.
      - It must be set if there are several such services defined in your Ranger Admin configuration, to select the one you intend to use.
    required: false
    default: None
    aliases: []
  state:
    description:
      - Whether to install (present) or remove (absent) these policies
    required: false
    default: present
    choices: [ present, absent ]
  policies:
    description:
      - The list of policies you want to be defined by this operation.
    required: true
    default: None
    aliases: []
  policies[0..n].name:
    description:
      - The name of the policy. Must be unique across the system.
    required: true
    default: None
    aliases: []
  policies[0..n].[database | url | sparkservice | global ]:
    description:
      - A list of database names, url, sparkservice or global. Accept wildcard characters '*' and '?'
    required: true
    default: None
    aliases: []
  policies[0..n].[table|udf]:
    description:
      - When database resource is defined. A list of tables or udf. Accept wildcard character '*'
    required: true
    default: None
    aliases: []
  policies[0..n].column:
    description:
      - When database and tables are defined. A list of columns. Accept wildcard character '*'
    required: true
    default: None
    aliases: []
  policies[0..n].enabled:
    description:
      - Whether this policy is enabled.
    required: false
    default: True
    aliases: []
  policies[0..n].audit:
    description:
      - Whether this policy is audited
    required: false
    default: True
    aliases: []
  policies[0..n].permissions:
    description:
      - A list of permissions associated to this policy
    required: True
    default: None
    aliases: []
  policies[0..n].permissions[0..n].users:
    description:
      - A list of users this permission will apply on.
    required: false
    default: None
    aliases: []
  policies[0..n].permissions[0..n].groups:
    description:
      - A list of groups this permission will apply on.
    required: false
    default: None
    aliases: []
  policies[0..n].permissions[0..n].accesses:
    description:
      - A list of access right granted by this permission.
    required: True
    default: None
    aliases: []
  policies[0..n].permissions[0..n].ip_addresses:
    description:
      - A list of source IP addresses to be bound to this permission
    required: false
    default: None
    aliases: []
  policies[0..n].permissions[0..n].delegate_admin:
    description:
      - When a policy is assigned to a user or a group of users those users become the delegated admin. The delegated admin can update, delete the policies.
    required: false
    default: False
    aliases: []

author:
    - "Anil Wavde"

'''


EXAMPLES = '''

# Allow user 'app1' to create,update,drop database 'database1'. And allow user 'app2' and all users belonging to groups 'grp1 and grp2 to select.

- hosts: ambari_nodes
  tasks:
  - ranger_spark_policies:
      state: present
      admin_url: https://ranger.mycompany.com:6182
      admin_username: admin
      admin_password: admin
      ssl_verify: False
      policies:
      - name: "spark_policy1"
        database:
            - "my_ranger_schema"
        table:
            - *
        column:
            - *
        permissions:
        - users:
          - app1
          accesses: [create, update] # all, alter, create, drop, index, lock, read, refresh, repladmin, select, serviceadmin, tempudfadmin, update, write
        - users:
          - app2
          groups:
          - grp1
          - grp2
          accesses:
          - select

# Same result, expressed in a different way
- hosts: en1
  vars:
    policy1:
      { name: spark_policy1, database: [ my_ranger_schema ], table: [*], column: [*], permissions: [ { users: [ app1 ], accesses: [ create,update,drop ] }, { users: [ app2 ], groups: [ grp1, grp2 ], accesses: [ select ] } ] }
  tasks:
  - ranger_spark_policies:
      state: present
      admin_url: https://ranger.mycompany.com:6182
      admin_username: admin
      admin_password: admin
      ssl_verify: False
      policies:
      - "{{ policy1 }}"



'''
import warnings
from oci._vendor import requests
from oci._vendor.requests.auth import HTTPBasicAuth
from ansible.module_utils.basic import AnsibleModule

module = None
resourceType = None
allowedResourceType = None
logs = []
logLevel = 'None'

def log(level, message):
    x = level+':' + message
    logs.append(x)

def debug(message):
    if logLevel == 'debug':
        log("DEBUG", message)

def info(message):
    if logLevel == "info"  or logLevel == "debug":
        log("INFO", message)

class RangerAPI:

    def __init__(self, endpoint, username, password, ssl_verify):
        self.endpoint = endpoint
        self.username = username
        self.password = password
        self.ssl_verify = ssl_verify
        self.serviceNamesByType = None
        self.auth = HTTPBasicAuth(self.username, self.password)
        warnings.filterwarnings("ignore", ".*Unverified HTTPS.*")
        warnings.filterwarnings("ignore", ".*Certificate has no `subjectAltName`.*")

    def get(self, path):
        url = self.endpoint + "/" + path
        resp = requests.get(url, auth = self.auth, verify=self.ssl_verify)
        debug("HTTP GET({})  --> {}".format(url, resp.status_code))
        if resp.status_code == 200:     # Warning: Failing auth may trigger a 200 with an HTML login page.
            contentType = resp.headers["content-type"] if ("content-type" in resp.headers) else "unknown"
            debug("Response content-type:{}".format(contentType))
            if "json" in contentType:
                result = resp.json()
                return result
            elif contentType.startswith("text/html"):
                error("HTML content received. May be Ranger login or password is invalid!")
            else:
                error("Invalid 'content-type' ({}) in response".format(contentType))
        else:
            error("Invalid returned http code '{0}' when calling GET on '{1}'".format(resp.status_code, url))

    def getServiceNameByType(self, stype, candidate=None):
        if self.serviceNamesByType == None:
            self.serviceNamesByType = {}
            services = self.get("service/public/v2/api/service")
            for service in services:
                if not service["type"] in self.serviceNamesByType:
                    self.serviceNamesByType[service['type']] = []
                self.serviceNamesByType[service['type']].append(service['name'])

        if stype not in self.serviceNamesByType:
            error("Service type '{0}' is not defined in this Ranger instance".format(stype) )
        serviceNames = self.serviceNamesByType[stype]
        if candidate != None:
            if candidate not in serviceNames:
                error("Service {0} is not defined on this Ranger instance".format(candidate))
            return candidate
        else:
            if len(serviceNames) != 1:
                error("There is several choice for '{0}' service: {1}. Please configure one explicitly!".format(stype, serviceNames))
            return serviceNames[0]

    def getPolicy(self, service, policyName):
        return self.get("service/public/v2/api/service/{0}/policy?policyName={1}".format(service, policyName))

    def createPolicy(self, policy):
        url = self.endpoint + '/service/public/v2/api/policy'
        resp = requests.post(url, auth = self.auth, json=policy, headers={'content-type': 'application/json'}, verify=self.ssl_verify)
        debug("HTTP POST({})  --> {}".format(url, resp.status_code))
        if resp.status_code != 200:
            error("Invalid returned http code '{0}' when calling POST on '{1}': {2}".format(resp.status_code, url, resp.text))

    def deletePolicy(self, pid):
        url = "{0}/service/public/v2/api/policy/{1}".format(self.endpoint, pid)
        resp = requests.delete(url, auth = self.auth, verify=self.ssl_verify)
        debug("HTTP DELETE({})  --> {}".format(url, resp.status_code))
        if resp.status_code < 200 or resp.status_code > 299:
            error("Invalid returned http code '{0}' when calling DELETE on '{1}: {2}'".format(resp.status_code, url, resp.text))

    def updatePolicy(self, policy):
        url = "{0}/service/public/v2/api/policy/{1}".format(self.endpoint, policy["id"])
        resp = requests.put(url, auth = self.auth, json=policy, headers={'content-type': 'application/json'}, verify=self.ssl_verify)
        debug("HTTP PUT({})  --> {}".format(url, resp.status_code))
        if resp.status_code != 200:
            error("Invalid returned http code '{0}' when calling PUT on '{1}': {2}".format(resp.status_code, url, resp.text))

    def close(self):
        pass

# ---------------------------------------------------------------------------------

def digdiff(left, right):
    result = {
        "missingOnLeft": [],
        "missingOnRight": [],
        "differsByValue": [],
        "differsByType": []
    }
    diffValue(left, right, "", result)
    return result


def diffValue(left, right, path, result):
    if right == None:
        if left != None:
            result["differsByValue"].append(path)
        else:
            pass
    else:
        if left == None:
            result["differsByValue"].append(path)
        elif isinstance(left, dict):
            if isinstance(right, dict):
                diffDict(left, right, path, result)
            else:
                result["differsByType"].append(path)
        elif isinstance(left, list):
            if isinstance(right, list):
                diffList(left, right, path, result)
            else:
                result["differsByType"].append(path)
        else:
            left = normalizeType(left)
            right = normalizeType(right)
            if type(left) != type(right):
                result["differsByType"].append(path)
            else:
                if left != right:
                    result["differsByValue"].append(path)
                else:
                    pass

def normalizeType(value):
    if isinstance(value, str):
        return value
    else:
        return str(value)

def diffDict(left, right, path, result):
    for kl in left:
        path2 = path + "." + kl
        if kl in right:
            diffValue(left[kl], right[kl], path2, result)
        else:
            result['missingOnRight'].append(path2)
    for kr in right:
        path2 = path + "." + kr
        if kr in left:
            pass
        else:
            result['missingOnLeft'].append(path2)

def diffList(left, right, path, result):
    for x in range(len(left)):
        path2 = path + '[' + str(x) + ']'
        if x >= len(right):
            result['missingOnRight'].append(path2)
        else:
            diffValue(left[x], right[x], path2, result)
    for x in range(len(left), len(right)):
        path2 = path + '[' + str(x) + ']'
        result['missingOnLeft'].append(path2)

# ---------------------------------------------------------------------------------

ALLOWED_MISSING_ON_RIGHT = set([".version", ".policyType", ".guid"])

def isPolicyIdentical(old, new):
    result = digdiff(old, new)
    debug("missingOnLeft:{}".format(result['missingOnLeft']))
    debug("missingOnRight:{}".format(result['missingOnRight']))
    debug("differsByType:{}".format(result['differsByType']))
    debug("differsByValue:{}".format(result['differsByValue']))
    if len(result['missingOnLeft']) > 0 or len(result['differsByType']) > 0 or len(result['differsByValue']) > 0:
        return False
    else:
        for missing in result["missingOnRight"]:
            if not missing in ALLOWED_MISSING_ON_RIGHT:
                return False
        return True

# Grooming helper functions
def checkListOfStrNotEmpty(base, attr, prefix):
    if attr not in base:
        error("{0}: Missing attribute '{1}'".format(prefix, attr))
    if not isinstance(base[attr], list):
        error("{0}: Attribute '{1}' is of wrong type. Must be a list".format(prefix, attr))
    if len(base[attr]) == 0:
        error("{0}: Attribute '{1}': Must have at least one items".format(prefix, attr))
    for v in base[attr]:
        if not isinstance(v, str) or len(v) == 0:
            error("{0}: All items of list '{1}' must be non null string".format(prefix, attr))

def checkListOfStr(base, attr, prefix):
    if attr not in base:
        base[attr] = []
    else:
        if not isinstance(base[attr], list):
            error("{0}: Attribute '{1}' is of wrong type. Must be a list".format(prefix, attr))
        for v in base[attr]:
            if not isinstance(v, str) or len(v) == 0:
                error("{0}: All items of list '{1}' must be non null string".format(prefix, attr))

def checkTypeWithDefault(base, attr, typ, default, prefix):
    if attr not in base:
        base[attr] = default
    else:
        if not isinstance(base[attr], typ):
            error("{0}: Attribute '{1}' is of wrong type. Must be a {2}".format(prefix, attr, typ))

def checkEnumWithDefault(base, attr, candidates, default, prefix):
    if attr not in base:
        base[attr] = default
    else:
        if not isinstance(base[attr], str):
            error("{0}: Attribute '{1}' is of wrong type. Must be a string".format(prefix, attr))
        else:
            if not base[attr] in candidates:
                error("{0}: Attribute '{1}' must be one of the following: {2}".format(prefix, attr, candidates))

def checkValidAttr(base, validAttrSet, prefix):
    for attr in base:
        is_valid = False
        for valid_attr in validAttrSet:
            if isinstance(valid_attr, (set, list)):
                if attr in valid_attr:
                    is_valid = True
                    break
            elif attr == valid_attr:
                is_valid = True
                break
        if not is_valid:
            error("{0}: Invalid attribute '{1}'. Must be one of {2}".format(prefix, attr, validAttrSet))

def checkResourceType(base, allowedResourceType, prefix):
    providedResourceType = [attr for attr in base if attr in allowedResourceType]
    if len(providedResourceType) > 1:
        error("{0}: Only one of {1} can be provided, but found {2}".format(
            prefix, allowedResourceType, providedResourceType))
    resourceType = providedResourceType[0] if providedResourceType else None
    return resourceType

def checkDatabaseResource(base, validAttrSet, prefix):
    providedResType = [attr for attr in base if attr in validAttrSet]
    if len(providedResType) > 1:
        error("{0}: Only one of {1} can be provided, but found {2}".format(prefix, validAttrSet, providedResType))
    elif len(providedResType) == 1:
        checkListOfStrNotEmpty(base, providedResType[0], prefix)

# Sanity-checks for target policy
def groom(policy):
    if 'name' not in policy:
        error("There is at least one Spark policy without name!")
    if not isinstance(policy["name"], str):
        error("Spark policy: Attribute 'name' is of wrong type. Must be a string")
    prefix = "Spark policy '{0}': ".format(policy['name'])

    global allowedResourceType
    checkValidAttr(policy, ['name','audit', 'state', allowedResourceType, 'table', 'column', 'udf', 'enabled', 'permissions'], prefix)

    resourceType = checkResourceType(policy, allowedResourceType, prefix)
    debug("resourceType".format(resourceType))
    checkListOfStrNotEmpty(policy, resourceType, prefix)

    if resourceType == 'database':
        # Policy resource type 'database' can optionally have 'table' or 'udf'
        checkDatabaseResource(policy,['table', 'udf'],prefix)
        #  'column' can only be combined with 'table'
        checkDatabaseResource(policy,['column', 'udf'],prefix)
        if 'column' in policy and not 'table' in policy:
                error("{0}: Missing resource 'table' for 'column'".format(prefix))

    else:
        # { url, sparkservice, global } resource type doesn't have any other resourceType combination
        if 'table' in policy or 'column' in policy or 'udf' in policy:
            error("{0}: 'table', 'column', 'udf' can't be combined with '{1}'".format(prefix, resourceType))

    checkTypeWithDefault(policy, "audit", bool, True, prefix)
    checkTypeWithDefault(policy, "enabled", bool, True, prefix)
    checkTypeWithDefault(policy, "permissions", list, [], prefix)

    # Validate permissions block
    for permission in policy['permissions']:
        checkValidAttr(permission, ['users', 'groups', 'accesses', 'delegate_admin'], prefix)
        checkListOfStr(permission, 'users', prefix)
        checkListOfStr(permission, 'groups', prefix)
        checkListOfStr(permission, 'accesses', prefix)
        checkTypeWithDefault(permission, 'delegate_admin', bool, False, prefix)

    return resourceType

def generateNewPolicy(targetPolicy, resourceType, service):
    policy = {
        'allowExceptions': [],
        'dataMaskPolicyItems': [],
        'denyExceptions': [],
        'denyPolicyItems': [],
        'isAuditEnabled': targetPolicy['audit'],
        'isEnabled': targetPolicy['enabled'],
        'name': targetPolicy['name'],
        'policyItems': [],
        'resources': {
            resourceType: {
                "isExcludes": False,
                "isRecursive": False,
                "values": targetPolicy[resourceType]
            }
        },
        'rowFilterPolicyItems': [],
        'service': service
    }

    if 'database' == resourceType:
        if 'udf' in targetPolicy and len(targetPolicy['udf']) > 0:
            policy['resources']['udf'] = { "isExcludes": False, "isRecursive": False, "values": targetPolicy["udf"] }
        if 'table' in targetPolicy and len(targetPolicy['table']) > 0:
            policy['resources']['table'] = { "isExcludes": False, "isRecursive": False, "values": targetPolicy["table"] }
        if 'column' in targetPolicy and len(targetPolicy['column']) > 0:
            policy['resources']['column'] = { "isExcludes": False, "isRecursive": False, "values": targetPolicy["column"]}

    for p in targetPolicy['permissions']:
        tp = {}
        tp['accesses'] = []
        tp['conditions'] = []
        tp['delegateAdmin'] = p['delegate_admin']
        tp['groups'] = p['groups']
        tp['users'] = p['users']
        for a in p['accesses']:
            tp['accesses'].append({ "isAllowed": True, "type": a.lower() })
        policy['policyItems'].append(tp)
    return policy

rangerAPI = None

def cleanup():
    if rangerAPI != None:
        rangerAPI.close()

def error(message):
    cleanup()
    module.fail_json(msg = message, logs=logs)

class Parameters:
    pass

def checkParameters(p):
    pass

def main():
    global module
    module = AnsibleModule(
        argument_spec = dict(
            state = dict(required=False, choices=['present','absent'], default="present"),
            admin_url = dict(required=True, type='str'),
            admin_username = dict(required=True, type='str'),
            admin_password = dict(required=True, type='str',no_log=True),
            ssl_verify = dict(required=False, type='bool', default=False),
            ca_bundle_file = dict(required=False, type='str'),
            service_name = dict(required=False, type='str'),
            policies = dict(required=True, type='list'),
            log_level = dict(required=False, default="None")
        ),
        supports_check_mode=False
    )

    params = Parameters()
    params.state = module.params['state']
    params.adminUrl = module.params['admin_url']
    params.adminUsername = module.params['admin_username']
    params.adminPassword = module.params['admin_password']
    params.sslVerify = module.params['ssl_verify']
    params.ca_bundleFile = module.params['ca_bundle_file']
    params.serviceName = module.params['service_name']
    params.policies = module.params['policies']
    params.logLevel = module.params['log_level']
    params.changed = False

    global logLevel
    global allowedResourceType
    logLevel = params.logLevel
    allowedResourceType = {'database', 'url', 'sparkservice', 'global'}

    checkParameters(params)

    if params.ca_bundleFile != None:
        ssl_verify = params.ca_bundleFile
    else:
        ssl_verify = params.sslVerify

    global rangerAPI
    rangerAPI =  RangerAPI(params.adminUrl, params.adminUsername , params.adminPassword , ssl_verify)

    result = {}
    sparkServiceName = rangerAPI.getServiceNameByType("spark", params.serviceName)

    for targetPolicy in params.policies:
        # Perform check before effective operation
        resourceType = groom(targetPolicy)
        policyName = targetPolicy['name']
        result[policyName] = {}
        oldPolicies = rangerAPI.getPolicy(sparkServiceName, policyName)
        debug("oldPolicies: " + repr(oldPolicies))

        if len(oldPolicies) > 1:
            error("Multiple policies found with name '{0}' !".format(policyName))

        if params.state == 'present':
            if len(oldPolicies) == 0:
                policy = generateNewPolicy(targetPolicy, resourceType, sparkServiceName)
                rangerAPI.createPolicy(policy)
                result[policyName]['action'] = "created"
                params.changed = True
            else:
                oldPolicy = oldPolicies[0]
                pid = oldPolicy["id"]
                policy = generateNewPolicy(targetPolicy, resourceType, sparkServiceName)
                policy["id"] = pid
                result[policyName]['id'] = pid
                if isPolicyIdentical(oldPolicy, policy):
                    result[policyName]['action'] = "none"
                else:
                    result[policyName]['action'] = "updated"
                    rangerAPI.updatePolicy(policy)
                    params.changed = True
        elif params.state == 'absent':
            if len(oldPolicies) == 1:
                rangerAPI.deletePolicy(oldPolicies[0]["id"])
                result[policyName]['action'] = "deleted"
                params.changed = True
            else:
                result[policyName]['action'] = "none"

    cleanup()
    module.exit_json(
        changed = params.changed,
        policies = result,
        logs = logs
    )

if __name__ == '__main__':
    main()


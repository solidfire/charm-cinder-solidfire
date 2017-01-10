#!/usr/bin/python

import json
import sys
import subprocess

from charmhelpers.core.hookenv import (
    Hooks,
    UnregisteredHookError,
    local_unit,
    relation_set,
    relation_ids,
    log,
    status_set
)

from charmhelpers.contrib.openstack.utils import (
    set_os_workload_status,
    os_application_version_set,
)

from contexts import SolidFireSubordinateContext

hooks = Hooks()

@hooks.hook('storage-backend-relation-joined',
            'storage-backend-relation-changed')
def storage_backend(rel_id=None):
    relation_set(relation_id=None,
             backend_name=local_unit().replace('/','-'),
             subordinate_configuration = json.dumps(
                  SolidFireSubordinateContext()()),
             stateless=True, )

if __name__ == '__main__':
    try:
        hooks.execute(sys.argv)
    except UnregisteredHookError as e:
        log("Unknown Hook {} - skipping.".format(e))
    status_set('active',"Unit is ready")
    os_application_version_set('cinder-common')

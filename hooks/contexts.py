from charmhelpers.core.hookenv import (
    config,
    service_name,
    local_unit,
    log
)

from charmhelpers.contrib.openstack.context import (
    OSContextGenerator,
)

class SolidFireIncompleteConfiguration(Exception):
    pass

class SolidFireSubordinateContext(OSContextGenerator):
  interfaces = ['solidfire']

  _config_keys = [
      'san_ip',
      'san_login',
      'san_password',
  ]

  def __call__(self):
    ctxt = []
    missing = []

    for k in self._config_keys:
      if config(k):
        ctxt.append(("{}".format(k.replace('-', '_')),
                     config(k)))
      else:
        missing.append(k)
    if missing:
      raise SolidFireIncompleteConfiguration(
         'Missing configuration: {}.'.format(missing)
      )

    SectionName = local_unit().replace('/','-')
    VolBackendName = service_name()
    # add constants at the end, then dedup with order prservation
    # this allows the user to override if they want.
    ctxt.append(('volume_backend_name', VolBackendName))
    ctxt.append(('volume_driver', 'cinder.volume.drivers.solidfire.SolidFireDriver'))
    return {
            "cinder": {
                "/etc/cinder/cinder.conf": {
                    "sections": {
                        SectionName: ctxt,
                    },
                }
            }
    }


#!/usr/bin/env python
#
# Copyright 2016 Canonical Ltd
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#  http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
Basic cinder-solidfire functional test.
"""
import amulet
import json
import time

from charmhelpers.contrib.openstack.amulet.deployment import (
    OpenStackAmuletDeployment
)

from charmhelpers.contrib.openstack.amulet.utils import (
    OpenStackAmuletUtils,
    DEBUG,
)

# Use DEBUG to turn on debug logging
u = OpenStackAmuletUtils(DEBUG)


class CinderSolidFireBasicDeployment(OpenStackAmuletDeployment):
    """Amulet tests on a basic heat deployment."""

    def __init__(self, series=None, openstack=None, source=None, git=False,
                 stable=False):
        """Deploy the entire test environment."""
        super(CinderSolidFireBasicDeployment, self).__init__(series, openstack,
                                                        source, stable)
        self.git = git
        self._add_services()
        self._add_relations()
        self._configure_services()
        self._deploy()

        u.log.info('Waiting on extended status checks...')
        exclude_services = ['nrpe']

        # Wait for deployment ready msgs, except exclusions
        self._auto_wait_for_status(exclude_services=exclude_services)

        self.d.sentry.wait()
        self._initialize_tests()

    def _add_services(self):
        """Add the services that we're testing, where cinder-solidfire is
        local, and the rest of the services are from lp branches that
        are compatible with the local charm (e.g. stable or next).
        """
        # Note: cinder-solidfire becomes a cinder subordinate unit.
        this_service = {'name': 'cinder-solidfire'}
        other_services = [
            {'name': 'percona-cluster', 'constraints': {'mem': '3072M'}},
            {'name': 'keystone'},
            {'name': 'rabbitmq-server'},
            {'name': 'cinder'}
        ]
        super(CinderSolidFireBasicDeployment, self)._add_services(this_service,
                                                             other_services)

    def _add_relations(self):
        """Add all of the relations for the services."""

        relations = {
            'cinder:storage-backend': 'cinder-solidfire:storage-backend',
            'keystone:shared-db': 'percona-cluster:shared-db',
            'cinder:shared-db': 'percona-cluster:shared-db',
            'cinder:identity-service': 'keystone:identity-service',
            'cinder:amqp': 'rabbitmq-server:amqp',
        }
        super(CinderSolidFireBasicDeployment, self)._add_relations(relations)

    def _configure_services(self):
        """Configure all of the services."""
        keystone_config = {
            'admin-password': 'openstack',
            'admin-token': 'ubuntutesting'
        }
        pxc_config = {
            'dataset-size': '25%',
            'max-connections': 1000,
            'root-password': 'ChangeMe123',
            'sst-password': 'ChangeMe123',
        }
        cinder_config = {
            'block-device': 'None',
            'glance-api-version': '2'
        }
        cinder_solidfire_config = {
            'san_ip': '172.27.1.50',
            'san_login': 'admin',
            'san_password': 'theSecretWord'
        }
        configs = {
            'keystone': keystone_config,
            'percona-cluster': pxc_config,
            'cinder': cinder_config,
            'cinder-solidfire': cinder_solidfire_config
        }
        super(CinderSolidFireBasicDeployment, self)._configure_services(configs)

    def _initialize_tests(self):
        """Perform final initialization before tests get run."""
        # Access the sentries for inspecting service units
        self.pxc_sentry = self.d.sentry['percona-cluster'][0]
        self.keystone_sentry = self.d.sentry['keystone'][0]
        self.rabbitmq_sentry = self.d.sentry['rabbitmq-server'][0]
        self.cinder_sentry = self.d.sentry['cinder'][0]
        self.cinder_solidfire_sentry = self.d.sentry['cinder-solidfire'][0]
        u.log.debug('openstack release val: {}'.format(
            self._get_openstack_release()))
        u.log.debug('openstack release str: {}'.format(
            self._get_openstack_release_string()))

        # Authenticate admin with keystone
        self.keystone = u.authenticate_keystone_admin(self.keystone_sentry,
                                                      user='admin',
                                                      password='openstack',
                                                      tenant='admin')
        # Authenticate admin with cinder endpoint
        self.cinder = u.authenticate_cinder_admin(self.keystone_sentry,
                                                  username='admin',
                                                  password='openstack',
                                                  tenant='admin')

        # Create a demo tenant/role/user
        self.demo_tenant = 'demoTenant'
        self.demo_role = 'demoRole'
        self.demo_user = 'demoUser'
        if not u.tenant_exists(self.keystone, self.demo_tenant):
            tenant = self.keystone.tenants.create(tenant_name=self.demo_tenant,
                                                  description='demo tenant',
                                                  enabled=True)
            self.keystone.roles.create(name=self.demo_role)
            self.keystone.users.create(name=self.demo_user,
                                       password='password',
                                       tenant_id=tenant.id,
                                       email='demo@demo.com')

        # Authenticate demo user with keystone
        self.keystone_demo = u.authenticate_keystone_user(self.keystone,
                                                          self.demo_user,
                                                          'password',
                                                          self.demo_tenant)

        # Authenticate demo user with nova-api
        self.nova_demo = u.authenticate_nova_user(self.keystone,
                                                  self.demo_user,
                                                  'password',
                                                  self.demo_tenant)

    def test_102_services(self):
        """Verify the expected services are running on the service units."""
        services = {
            self.rabbitmq_sentry: ['rabbitmq-server'],
            self.keystone_sentry: ['keystone'],
            self.cinder_sentry: ['cinder-api',
                                 'cinder-scheduler',
                                 'cinder-volume'],
        }

        if self._get_openstack_release() >= self.trusty_liberty:
            services[self.keystone_sentry] = ['apache2']

        ret = u.validate_services_by_name(services)
        if ret:
            amulet.raise_status(amulet.FAIL, msg=ret)

    def test_110_users(self):
        """Verify expected users."""
        u.log.debug('Checking keystone users...')
        expected = [
            {'name': 'cinder_cinderv2',
             'enabled': True,
             'tenantId': u.not_null,
             'id': u.not_null,
             'email': 'juju@localhost'},
            {'name': 'admin',
             'enabled': True,
             'tenantId': u.not_null,
             'id': u.not_null,
             'email': 'juju@localhost'}
        ]
        actual = self.keystone.users.list()
        ret = u.validate_user_data(expected, actual)
        if ret:
            amulet.raise_status(amulet.FAIL, msg=ret)

    def test_112_service_catalog(self):
        """Verify that the service catalog endpoint data"""
        u.log.debug('Checking keystone service catalog...')
        endpoint_vol = {
            'adminURL': u.valid_url,
            'region': 'RegionOne',
            'publicURL': u.valid_url,
            'internalURL': u.valid_url
        }
        endpoint_id = {
            'adminURL': u.valid_url,
            'region': 'RegionOne',
            'publicURL': u.valid_url,
            'internalURL': u.valid_url
        }
        if self._get_openstack_release() >= self.trusty_icehouse:
            endpoint_vol['id'] = u.not_null
            endpoint_id['id'] = u.not_null

        expected = {
            'identity': [endpoint_id],
            'volume': [endpoint_id]
        }
        actual = self.keystone.service_catalog.get_endpoints()

        ret = u.validate_svc_catalog_endpoint_data(expected, actual)
        if ret:
            amulet.raise_status(amulet.FAIL, msg=ret)

    def test_114_cinder_endpoint(self):
        """Verify the cinder endpoint data."""
        u.log.debug('Checking cinder api endpoint data...')
        endpoints = self.keystone.endpoints.list()
        admin_port = internal_port = public_port = '8776'
        expected = {
            'id': u.not_null,
            'region': 'RegionOne',
            'adminurl': u.valid_url,
            'internalurl': u.valid_url,
            'publicurl': u.valid_url,
            'service_id': u.not_null
        }

        ret = u.validate_endpoint_data(endpoints, admin_port, internal_port,
                                       public_port, expected)
        if ret:
            amulet.raise_status(amulet.FAIL,
                                msg='cinder endpoint: {}'.format(ret))

    def test_202_cindersolidfire_cinder_backend_relation(self):
        u.log.debug('Checking cinder-solidfire:storage-backend to '
                    'cinder:storage-backend relation data...')
        unit = self.cinder_solidfire_sentry
        relation = ['storage-backend', 'cinder:storage-backend']

        sub = ('{"cinder": '
                    '{"/etc/cinder/cinder.conf": '
                        '{"sections": '
                            '{"cinder-solidfire-%s": ['
                                '["san_ip", "172.27.1.50"], '
                                '["san_login", "admin"], '
                                '["san_password", "theSecretWord"], '
                                '["volume_backend_name", "cinder-solidfire"], '
                                '["volume_driver", "cinder.volume.drivers.solidfire.SolidFireDriver"]'
                  ']}}}}') % unit.info['unit']

        expected = {
            'subordinate_configuration': sub,
            'private-address': u.valid_ip,
            'backend_name': ('cinder-solidfire-%s' % unit.info['unit']),
            'stateless': 'True'
        }

        ret = u.validate_relation_data(unit, relation, expected)
        if ret:
            msg = u.relation_error('cinder cinder-solidfire storage-backend', ret)
            amulet.raise_status(amulet.FAIL, msg=msg)

    def test_203_cinder_cindersolidfire_backend_relation(self):
        u.log.debug('Checking cinder:storage-backend to '
                    'cinder-solidfire:storage-backend relation data...')
        unit = self.cinder_sentry
        relation = ['storage-backend', 'cinder-solidfire:storage-backend']

        expected = {
            'private-address': u.valid_ip,
        }
        ret = u.validate_relation_data(unit, relation, expected)
        if ret:
            msg = u.relation_error('cinder cinder-solidfire storage-backend', ret)
            amulet.raise_status(amulet.FAIL, msg=msg)

    def test_204_mysql_cinder_db_relation(self):
        """Verify the mysql:glance shared-db relation data"""
        u.log.debug('Checking mysql:cinder db relation data...')
        unit = self.pxc_sentry
        relation = ['shared-db', 'cinder:shared-db']
        expected = {
            'private-address': u.valid_ip,
            'db_host': u.valid_ip
        }
        ret = u.validate_relation_data(unit, relation, expected)
        if ret:
            msg = u.relation_error('mysql shared-db', ret)
            amulet.raise_status(amulet.FAIL, msg=msg)

    def test_205_cinder_mysql_db_relation(self):
        """Verify the cinder:mysql shared-db relation data"""
        u.log.debug('Checking cinder:mysql db relation data...')
        unit = self.cinder_sentry
        relation = ['shared-db', 'percona-cluster:shared-db']
        expected = {
            'private-address': u.valid_ip,
            'hostname': u.valid_ip,
            'username': 'cinder',
            'database': 'cinder'
        }
        ret = u.validate_relation_data(unit, relation, expected)
        if ret:
            msg = u.relation_error('cinder shared-db', ret)
            amulet.raise_status(amulet.FAIL, msg=msg)

    def test_206_keystone_cinder_id_relation(self):
        """Verify the keystone:cinder identity-service relation data"""
        u.log.debug('Checking keystone:cinder id relation data...')
        unit = self.keystone_sentry
        relation = ['identity-service',
                    'cinder:identity-service']
        expected = {
            'service_protocol': 'http',
            'service_tenant': 'services',
            'admin_token': 'ubuntutesting',
            'service_password': u.not_null,
            'service_port': '5000',
            'auth_port': '35357',
            'auth_protocol': 'http',
            'private-address': u.valid_ip,
            'auth_host': u.valid_ip,
            'service_username': 'cinder_cinderv2',
            'service_tenant_id': u.not_null,
            'service_host': u.valid_ip
        }
        ret = u.validate_relation_data(unit, relation, expected)
        if ret:
            msg = u.relation_error('identity-service cinder', ret)
            amulet.raise_status(amulet.FAIL, msg=msg)

    def test_300_cinder_config(self):
        """Verify the data in the cinder.conf file."""
        u.log.debug('Checking cinder config file data...')
        unit = self.cinder_sentry
        conf = '/etc/cinder/cinder.conf'
        unit_mq = self.rabbitmq_sentry
        rel_mq_ci = unit_mq.relation('amqp', 'cinder:amqp')

        sf_backend = ( 'cinder-solidfire-%s' % unit.info['unit'] )
        expected = {
            'DEFAULT': {
                # XXX: Temporarily disabled use_syslog check, pending
                #      resolution of https://bugs.launchpad.net/bugs/1604575
                # 'use_syslog': 'False',
                'debug': 'False',
                'verbose': 'False',
                'iscsi_helper': 'tgtadm',
                'volume_group': 'cinder-volumes',
                'auth_strategy': 'keystone',
                'volumes_dir': '/var/lib/cinder/volumes',
                'enabled_backends': sf_backend
            },
            sf_backend : {
                'san_ip': '172.27.1.50',
                'san_login': 'admin',
                'san_password': 'theSecretWord',
                'volume_backend_name': 'cinder-solidfire',
                'volume_driver': 'cinder.volume.drivers.solidfire.SolidFireDriver'
            }
        }

        expected_rmq = {
            'rabbit_userid': 'cinder',
            'rabbit_virtual_host': 'openstack',
            'rabbit_password': rel_mq_ci['password'],
            'rabbit_host': rel_mq_ci['hostname'],
        }

        if self._get_openstack_release() >= self.trusty_kilo:
            # Kilo or later
            expected['oslo_messaging_rabbit'] = expected_rmq
        else:
            # Juno or earlier
            expected['DEFAULT'].update(expected_rmq)

        for section, pairs in expected.iteritems():
            ret = u.validate_config_data(unit, conf, section, pairs)
            if ret:
                message = "cinder config error: {}".format(ret)
                amulet.raise_status(amulet.FAIL, msg=message)

    def test_400_cinder_api_connection(self):
        """Simple api call to check service is up and responding"""
        u.log.debug('Checking basic cinder api functionality...')
        check = list(self.cinder.volumes.list())
        u.log.debug('Cinder api check (volumes.list): {}'.format(check))
        assert(check == [])

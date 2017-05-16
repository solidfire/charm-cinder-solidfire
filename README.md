SolidFire storage backend for Cinder
------------------------------------

Overview
========

This charm configures Cinder to use SolidFire as a backend.  This charm works
with multiple backends from other vendors including ceph. 

To use:

    juju deploy cinder
    juju deploy cinder-solidfire
    juju config cinder-solidfire san_ip=172.27.1.50 san_login=admin san_password=solidfire
    juju add-relation cinder-solidfire:storage-backend cinder:storage-backend

This will setup a configuration file with the stanza named for the unit
(ex: cinder-solidfire-1) and the volume_backend_name set to 'cinder-solidfire'.
The charm does NOT setup the volume-types for Cinder. You will need to do that
once the Stack is up.  See the cinder configuration guide for details. 

Prerequisites
=============

Everything assumes you have the SolidFire cluster up and running already and
that your controller nodes (containers) can reach the SolidFire MVIP and SVIP
as needed.

Configuration
=============

The configuration options for this charm are shown below (by the charm store).
The required configuration minimum options are san_ip, san_login, san_password,
all others are optional. 

As an option to the above command (in overview) to set the variables, you can
also pass a file into the deploy command with the configuration like this:

    juju deploy  /home/ebalduf/charms/xenial/cinder-solidfire --config=SF-Config.yaml

Contact Information
===================

For issues and concerns please use the NetApp developer site and community forums.

http://netapp.io/
Ed Balduf <ed.balduf@solidfire.com>


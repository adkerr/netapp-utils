#!/usr/bin/python
# vim: tabstop=4 shiftwidth=4 softtabstop=4
#
# Copyright (c) 2013 NetApp, Inc.
# All Rights Reserved.
'''
Created on Feb 6, 2014

@author: akerr

This test requires that the netapp driver is properly configured in cinder.conf
and the nfs shares config file, and that the copy offload binary has beeen 
correctly downloaded to the proper location.  It will attempt to do the rest
of the setup by creating a volume on the vserver for glance to use, configuring
glance to use that volume, creating a proper netapp.json file, mounting the
volume locally for glance, ensuring that cinder is using the right glance api
version and then restarting both Cinder and Glance 
'''
import ConfigParser
import devstack_utils as devstack
import inspect
import ontapSSH
import os
import paramiko
import random
import subprocess
import time
import unittest


class TestCopyOffload(unittest.TestCase):

    def setUp(self):
        # Verify that environment has been primed
        self.assertIsNotNone(os.getenv("OS_USERNAME"),
                             "Environment not set up, please source "
                             "devstack/openrc before running test")
        # Configure Glance and Cinder properly
        self.glance = ConfigParser.SafeConfigParser()
        self.glance.read('/etc/glance/glance-api.conf')
        self.cinder = ConfigParser.SafeConfigParser()
        self.cinder.read('/etc/cinder/cinder.conf')
        backends = self.cinder.get('DEFAULT', 'enabled_backends')
        backends = backends.split(',')
        self.vserver = None
        for backend in backends:
            try:
                self.tool = self.cinder.get(backend,
                                            'netapp_copyoffload_tool_path')
            except ConfigParser.NoOptionError:
                continue
            if os.path.isfile(self.tool):
                self.vserver = self.cinder.get(backend, 'netapp_vserver')
                self.server = self.cinder.get(backend, 'netapp_server_hostname')
                self.login = self.cinder.get(backend, 'netapp_login')
                self.password = self.cinder.get(backend, 'netapp_password')
                self.backend = backend
        self.assertIsNotNone(self.vserver,
                             'No backend is configured for copy offload')
        self.assertTrue(os.path.isfile(self.tool),
                        '%s does not exist' %self.tool)
        self.cinder.set('DEFAULT', 'glance_api_version', '2')

        with open('/etc/cinder/cinder.conf', 'w+') as configfile:
            self.cinder.write(configfile)
        configfile.close()
        
        self.shares_file = self.cinder.get(self.backend, 'nfs_shares_config')
        shares = open(self.shares_file, 'r')
        self.shares = shares.readlines()
        shares.close()

        # Query vserver for glance volume, if it doesn't already exist create 
        # on a random aggregate and find out the vserver's data IP address
        
        self.filer = ontapSSH.NetappFiler(self.server,
                                          self.login,
                                          self.password)
        if 'glance' not in self.filer.get_vserver_volumes(self.vserver):
            aggrs = self.filer.get_vserver_aggrs(self.vserver)
            try:
                aggr = random.choice(aggrs)
            except IndexError:
                print('Vserver %s does not appear to have any aggregates'
                      %self.vserver)
                exit(1)
            self.filer.create_volume(self.vserver, 'glance', aggr)
        self.assertIsNotNone(self.filer.get_volume(self.vserver, 'glance'),
                             'glance volume could not be found or created on '
                             'server %s vserver %s'
                             %(self.server, self.vserver))
        self.filer.unmount_volume('glance')
        self.filer.mount_volume('glance')
        try:
            self.vserver_ip = random.choice(
                                self.filer.get_vserver_data_ips(self.vserver))
        except IndexError:
            print('Vserver %s does not appear to have any data ips'
                  %self.vserver)
            exit(1)
        
        # Use filesystem store
        self.glance.set('DEFAULT', 'default_store', 'file')
        # Mount/remount the filesystem store
        self.image_store = self.glance.get('DEFAULT',
                                           'filesystem_store_datadir')
        if self.image_store[-1] == '/':
            self.image_store = self.image_store[:-1]
        mount = subprocess.check_output("mount").decode("utf-8")
        if self.image_store in mount:
            self._unmount_glance()
        self._mount_glance()
        # The metatdata file is configured
        self._reset_json()
        self.glance.set('DEFAULT',
                        'filesystem_store_metadata_file',
                        '/etc/glance/netapp.json')
        # Multiple locations is True
        self.glance.set('DEFAULT',
                        'show_multiple_locations',
                        'True')
        # show_image_direct_url is True
        self.glance.set('DEFAULT',
                        'show_image_direct_url',
                        'True')
        
        with open('/etc/glance/glance-api.conf', 'w+') as configfile:
            self.glance.write(configfile)
        configfile.close()
        self._restart_services()
        
    
    def tearDown(self):
        self._unmount_glance()
        self._mount_glance()
        self._reset_json()
        self._reset_shares()
        self._restart_services


    def _delete_image(self, image_id):
        # Delete image from glance
        subprocess.call(["glance", "image-delete", image_id])
    
    
    def _reset_json(self):
        metadatafile = open('/etc/glance/netapp.json', 'w')
        json = str('{'
                   '"share_location": "nfs://%s/glance",'
                   '"mount_point": "%s",'
                   '"type": "nfs"'
                   '}' %(self.vserver_ip, self.image_store))
        metadatafile.write(json)
        metadatafile.close()
    
    
    def _reset_shares(self):
        share = open(self.shares_file, 'w')
        share.writelines(self.shares)
        share.close()
    
    
    def _restart_services(self):
        # Restart glance and cinder
        devstack.restart_cinder()
        devstack.restart_glance()
        # Give services time to initialize
        time.sleep(20)
    
    
    def _mount_glance(self):
        subprocess.check_call(["sudo",
                               "mount",
                               "-t",
                               "nfs",
                               "-o",
                               "vers=4",
                               "%s:/glance" %self.vserver_ip,
                               self.image_store])
    
    
    def _unmount_glance(self):
        subprocess.check_call(["sudo", "umount", self.image_store])


    def _do_image_download_test(self):
        ''' This function creates a new volume, uploads it to glance, and
            creates a new volume from that image.  It returns the number of
            copy_reqs and copy_failures generated by the image download '''
        # Create initial volume
        volume_origin = subprocess.check_output(["cinder",
                                                 "create",
                                                 "--name",
                                                 "vol-origin",
                                                 "1"])
        volume_origin = volume_origin.decode("utf-8")
        self.assertIn("creating",
                      volume_origin,
                      "Unexpected output from volume create command:\n%s\n"
                      %volume_origin)
        volume_origin = volume_origin.splitlines()
        for line in volume_origin[3:]:
            line = line.split("|")
            for item in line:
                line[line.index(item)] = item.strip()
            if line[1] == "id":
                volume_origin = line[2]
                break
        self.addCleanup(subprocess.call, ["cinder", "delete", volume_origin])
        # Wait for volume creation
        done = False
        start = time.time()
        while time.time() - start < 120:
            if "available" in subprocess.check_output(["cinder",
                                                       "show",
                                                       volume_origin]
                                                      ).decode("utf-8"):
                done = True
                break
            time.sleep(2)
        if not done:
            output = subprocess.check_output(["cinder",
                                              "show",
                                              volume_origin]).decode("utf-8")
            self.assertIn("available",
                          output,
                          "Volume %s was not created successfully within "
                          "120s:\n%s" %(volume_origin, output))
        
        # Create image from origin volume
        image = subprocess.check_output(["cinder",
                                         "upload-to-image",
                                         volume_origin,
                                         "colImage"]).decode("utf-8")
        image = image.splitlines()
        for line in image[3:]:
            line = line.split("|")
            for item in line:
                line[line.index(item)] = item.strip()
            if line[1] == "image_id":
                image = line[2]
                break
        self.addCleanup(subprocess.call, ["glance", "image-delete", image])
        # Wait for image upload
        done = False
        start = time.time()
        while time.time() - start < 120:
            time.sleep(2)
            if "active" in subprocess.check_output(["glance",
                                                    "image-show",
                                                    image]).decode("utf-8"):
                done = True
                break
        if not done:
            output = subprocess.check_output(["glance",
                                              "image-show",
                                              image]).decode("utf-8")
            self.assertIn("active",
                          output,
                          "Image %s was not uploaded successfully within "
                          "120s:\n%s" %(image, output))
        
        # Check initial volume copy_reqs
        rtn = self.filer.ssh_cmd("node run -node * -command \"priv set diag; "
                                 "stats show copy_manager:%s\"" %self.vserver)
        copy_reqs_origin = 0
        copy_failures_origin = 0
        for line in rtn:
            if ':copy_reqs:' in line:
                copy_reqs_origin += int(line.split(':')[-1])
            if ':copy_failures:' in line:
                copy_failures_origin += int(line.split(':')[-1])
        
        # Create volume from image
        volume = subprocess.check_output(["cinder",
                                          "create",
                                          "--image-id",
                                          image,
                                          "--name",
                                          "vol-image",
                                          "1"])
        volume = volume.decode("utf-8")
        self.assertIn("creating",
                      volume,
                      "Unexpected output from volume create command:\n%s\n"
                      %volume)
        volume = volume.splitlines()
        for line in volume[3:]:
            line = line.split("|")
            for item in line:
                line[line.index(item)] = item.strip()
            if line[1] == "id":
                volume = line[2]
                break
        self.addCleanup(subprocess.call, ["cinder", "delete", volume])
        # Wait for volume creation
        done = False
        start = time.time()
        while time.time() - start < 120:
            time.sleep(5)
            if "available" in subprocess.check_output(["cinder",
                                                       "show",
                                                       volume]).decode("utf-8"):
                done = True
                break
        if not done:
            output = subprocess.check_output(["cinder",
                                              "show",
                                              volume]).decode("utf-8")
            self.assertIn("available",
                          output,
                          "Volume %s was not created successfully within "
                          "120s:\n%s" %(volume, output))
        
        # Check final volume copy_reqs
        rtn = self.filer.ssh_cmd("node run -node * -command \"priv set diag; "
                                 "stats show copy_manager:%s\"" %self.vserver)
        copy_reqs_final = 0
        copy_failures_final = 0
        for line in rtn:
            if ':copy_reqs:' in line:
                copy_reqs_final += int(line.split(':')[-1])
            if ':copy_failures:' in line:
                copy_failures_final += int(line.split(':')[-1])
        
        # Check difference in copy_reqs
        copy_reqs = copy_reqs_final - copy_reqs_origin
        copy_failures = copy_failures_final - copy_failures_origin
        return copy_reqs, copy_failures


    def test_image_download_different_flexvols_positive(self):
        ''' This test attempts to use copy offload when downloading an image
            from glance that resides in a different flexvol than where the
            cinder volumes are stored '''
        print('%s...' %inspect.stack()[0][3])
        copy_reqs, copy_failures = self._do_image_download_test()
        self.assertEqual(copy_reqs,
                         1,
                         '%s copy_reqs detected, expected 1' %copy_reqs)
        self.assertEqual(copy_failures,
                         0,
                         '%s copy_failures detected, expected 0' %copy_failures)
        print('%s... OK' %inspect.stack()[0][3])
    
    
    def test_image_download_same_flexvol_positive(self):
        ''' This tests the use of copy offload when downloading an image
            from glance that resides in the same flexvol as where the
            cinder volumes are stored.  Cloning should be used instead of
            copy offload '''
        print('%s...' %inspect.stack()[0][3])
        self._unmount_glance()
        # Force cinder to use only 1 possible flexvol
        share = open(self.shares_file, 'r+')
        share.write(self.shares[0])
        share.close()
        
        ip = self.shares[0].split('/')[0]
        vol = self.shares[0].split(':')[-1]
        
        metadatafile = open('/etc/glance/netapp.json', 'w')
        metadatafile.write(str('{'
                               '"share_location": "nfs://%s%s",'
                               '"mount_point": "%s",'
                               '"type": "nfs"'
                               '}' %(ip[:-1], vol, self.image_store)))
        metadatafile.close()
        subprocess.check_call(["sudo",
                               "mount",
                               "-t",
                               "nfs",
                               "-o",
                               "vers=4",
                               "%s" %self.shares[0].strip(),
                               self.image_store])
        self._restart_services()
        copy_reqs, copy_failures = self._do_image_download_test()
        self.assertEqual(copy_reqs,
                         0,
                         '%s copy_reqs detected, expected 0' %copy_reqs)
        self.assertEqual(copy_failures,
                         0,
                         '%s copy_failures detected, expected 0' %copy_failures)
        print('%s... OK' %inspect.stack()[0][3])

if __name__ == "__main__":
    #import sys;sys.argv = ['', 'Test.testRapidClone']
    unittest.main()
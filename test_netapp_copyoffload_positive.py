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
            subprocess.check_call(["sudo", "umount", self.image_store])
        subprocess.check_call(["sudo",
                               "mount",
                               "-t",
                               "nfs",
                               "-o",
                               "vers=4",
                               "%s:/glance" %self.vserver_ip,
                               self.image_store])
        # The metatdata file is configured
        metadatafile = open('/etc/glance/netapp.json', 'w')
        json = str('{'
                   '"share_location": "nfs://%s/glance",'
                   '"mount_point": "%s",'
                   '"type": "nfs"'
                   '}' %(self.vserver_ip, self.image_store))
        metadatafile.write(json)
        metadatafile.close()
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
        
        # Restart glance and cinder
        devstack.restart_cinder()
        devstack.restart_glance()
        # Give services time to initialize
        time.sleep(20)
        
    
    def tearDown(self):
        del self.filer


    def _delete_image(self, image_id):
        # Delete image from glance
        subprocess.call(["glance", "image-delete", image_id])

    def testCopyOffload(self):
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
                print ("Volume %s successfully created in %ss"
                       %(volume_origin, time.time() - start))
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
                print ("Image %s successfully uploaded in %ss"
                       %(image, time.time() - start))
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
        
        client=paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        client.connect(self.server,
                       22,
                       username=self.login,
                       password=self.password)
        
        stdin, stdout, stderr = client.exec_command("node run -node * -command"
                                                    " \"priv set diag; stats "
                                                    "show copy_manager:%s\""
                                                    %self.vserver)
        stdin.close()
        stdout = stdout.readlines()
        copy_reqs_origin = 0
        copy_failures_origin = 0
        for line in stdout:
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
        print ("Volume %s being created from image %s" %(volume, image))
        # Wait for volume creation
        done = False
        start = time.time()
        while time.time() - start < 120:
            time.sleep(5)
            if "available" in subprocess.check_output(["cinder",
                                                       "show",
                                                       volume]).decode("utf-8"):
                print ("Volume %s successfully created in %ss"
                       %(volume, time.time() - start))
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
        
        stdin, stdout, stderr = client.exec_command("node run -node * -command "
                                                    "\"priv set diag; stats "
                                                    "show copy_manager:%s\""
                                                    %self.vserver)
        stdin.close()
        stdout = stdout.readlines()
        copy_reqs_final = 0
        copy_failures_final = 0
        for line in stdout:
            if ':copy_reqs:' in line:
                copy_reqs_final += int(line.split(':')[-1])
            if ':copy_failures:' in line:
                copy_failures_final += int(line.split(':')[-1])
        
        # Check difference in copy_reqs
        copy_reqs = copy_reqs_final - copy_reqs_origin
        copy_failures = copy_failures_final - copy_failures_origin
        print('copy_reqs increased by %s' %copy_reqs)
        self.assertGreater(copy_reqs, 0, 'copy_reqs did not increment')
        print('copy_failures increased by %s' %copy_failures)
        self.assertEquals(copy_failures, 0, 'copy_failures was not 0')
        

if __name__ == "__main__":
    #import sys;sys.argv = ['', 'Test.testRapidClone']
    unittest.main()
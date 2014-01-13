#! /usr/bin/python
# vim: tabstop=4 shiftwidth=4 softtabstop=4
#
# Copyright (c) 2013 NetApp, Inc.
# All Rights Reserved.
'''
Created on Jan 6, 2014

@author: akerr
'''
import os
import subprocess
import time
import unittest


class TestRapidCloning(unittest.TestCase):


    def setUp(self):
        # Verify that environment has been primed
        self.assertIsNotNone(os.getenv("OS_USERNAME"), "Environment not set up, please source devstack/openrc before running test")
        # Verify that glance has the appropriate image
        images = subprocess.check_output(["glance", "image-list"])
        images = images.decode("utf-8")
        self.assertIn("cirros-0.3.1-x86_64-uec",
                      images,
                      "cirros image is not in glance:\n%s\n" %images)
        # Grab cirros image id
        images = images.split("|")
        for item in images:
            images[images.index(item)] = item.strip()
        self.image_id = images[images.index("cirros-0.3.1-x86_64-uec")-1]
        # Locate NFS mount points
        self.mounts = []
        mount = subprocess.check_output("mount")
        # subprocess.check_output returns byte string
        mount = mount.decode("utf-8")
        mountlines = mount.splitlines()
        for line in mountlines:
            if "nfs" in line and "cinder" in line:
                self.mounts.append(line.split()[2])
        self._remove_cache()


    def tearDown(self):
        pass


    def _remove_cache(self):
        # Remove any existing cache files for the image
        for mount in self.mounts:
            path = '%s/img-cache-%s' %(mount, self.image_id)
            if os.path.isfile(path):
                subprocess.check_call(["rm", path])
                print "Cache file removed from %s" %path


    def testRapidClone(self):
        # Create volume from image
        volume = subprocess.check_output(["cinder",
                                          "create",
                                          "--image-id",
                                          self.image_id,
                                          "1"])
        volume = volume.decode("utf-8")
        self.assertIn("creating", volume, "Unexpected output from volume create command:\n%s\n" %volume)
        volume = volume.splitlines()
        for line in volume[3:]:
            line = line.split("|")
            for item in line:
                line[line.index(item)] = item.strip()
            if line[1] == "id":
                volume = line[2]
                break
        self.addCleanup(subprocess.call, ["cinder", "delete", volume])
        print "Volume %s created from image %s" %(volume, self.image_id)
        print "Sleeping for 60s to wait for image to finish creating..."
        # Wait for volume creation
        time.sleep(60)
        found = False
        for mount in self.mounts:
            path = '%s/img-cache-%s' %(mount, self.image_id)
            if os.path.isfile(path):
                found = True
                print "Found cache file at %s" %path
                break
        self.assertTrue(found, 'img-cache-%s does not exist' %(self.image_id))


if __name__ == "__main__":
    #import sys;sys.argv = ['', 'Test.testRapidClone']
    unittest.main()
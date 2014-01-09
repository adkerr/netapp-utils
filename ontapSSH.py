#!/usr/bin/python
# vim: tabstop=4 shiftwidth=4 softtabstop=4
#
# Copyright (c) 2013 NetApp, Inc.
# All Rights Reserved.

import paramiko

class NetappFiler:
    
    def __init__(self, host, username, password, port=22):
        # Create ssh client
        self.client=paramiko.SSHClient()
        self.client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        self.client.connect(host, port , username=username, password=password)


    def __del__(self):
        # Close ssh connection
        self.client.close()


    def setup_ssh(self, ssh_key):
        ssh_key='ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABAQDEpidHBQCxrZ+a2+iqrLiu+bcozbenWdCXVNBbouYcQ5Th85lPk8hiizY2Q8VZ8OY9JMdnZKAH/GtIW3jORr9Lc70BcWNG0ZCGeUqjxPdDK+PFFF6ewa55AjJ3eLvA3IBCUNEXMoGa0nhy2n35HK4vZk4Ws0uaQ8x/3RSADYfHHLVO7ll6Oa1ap1G4bHy4AgHAZm+BQIGPMzZjQJM4Qy6Smc3GyJ7YgoY/9X3HY7yVfKVgIRkA6WofOc7f6JD29T/xbOWNKwNZyjbqF9puufDcaHJtvrA4E7akfsLQ0SUhgjcd7TslaaHyR8nYkz/M8Pf/PpyvCaJSPe0Q1B02iHd7 root@stlrx300s7-30'
        # setup ssh keys -- THIS HAPPENS ON THE CONTROLLER BEFORE SCRIPT EXECUTION WITH THE CORRECT ssh_key SUBSTITUTED
        STR="security login create -username admin -application ssh -authmethod publickey -profile admin"
        print (STR)
        #note if an existing key then change index to 1 below
        STR2="security login publickey create -username admin -index 0 -publickey %s" %(ssh_key)
        print (STR2)
    
    
    def _ssh_cmd(self, cmd):
        print (cmd)
        stdin, stdout, stderr = self.client.exec_command(cmd)
        stdin.close()
        stdout = stdout.readlines()
        for line in stdout:
            print (line)
    
    
    def _ssh_yes_cmd(self, cmd):
        print (cmd)
        stdin, stdout, stderr = self.client.exec_command(cmd)
        stdin.write('y\n')
        stdin.flush()
        stdin.close()
        stdout = stdout.readlines()
        for line in stdout:
            print (line)
    
    
    def _create_volume(self, vserver, vol_name, vol_size, target_aggr):
        # Creates a thick volume
        cmd = "vol create -vserver %s -volume %s -aggregate %s -size %s -state online -type RW -policy default -user 0 -group 1 -security-style unix -unix-permissions ---rwxr-xr-x -max-autosize 60GB -autosize-increment 2.50GB -min-autosize 50GB -autosize-mode grow -space-guarantee volume" %(vserver, vol_name, target_aggr, vol_size)
        self._ssh_cmd(cmd)
    
    
    def create_set_QOS_policy(self, qosPolicy, vserver, vol_name):
        cmds = []
        # create policy-group
        cmds.append("policy-group create -policy-group %s -vserver %s -max-throughput 500MB" %(qosPolicy, vserver))
        #apply policy group to a volume
        cmds.append("vol modify -vserver %s -volume %s -qos-policy-group %s" %(vserver, vol_name, qosPolicy))
        for cmd in cmds:
            self._ssh_cmd(cmd)
    
    
    def set_dedup (self, vserver, vol_name):
        #turn dedup on for a volume
        cmd = "sis on -vserver %s -volume %s" %(vserver, vol_name)
        self._ssh_cmd(cmd)
    
    
    def set_compression (self, vserver, vol_name):
        cmds = []
        # turn on compession
        cmds.append("sis modify -vserver %s -volume %s -compression true" %(vserver, vol_name))
        for cmd in cmds:
            self._ssh_cmd(cmd)
    
    
    def set_thick (self, vserver, vol_name):
        # make volume thick provisioned
        cmd = "vol modify  -vserver %s -volume %s  -space-guarantee volume" %(vserver, vol_name)
        self._ssh_cmd(cmd)
    
    
    def set_thin (self, vserver, vol_name):
        # make volume thin provisioned
        cmd = "vol modify  -vserver %s -volume %s -space-guarantee none" %(vserver, vol_name)
        self._ssh_cmd(cmd)
    
    
    def mirror_vol (self, vserver, mirror_vserver, vol_name, vol_size, mirror_aggr):
        cmds = []
        # create mirror in other vserver based on existing volume. autocreates target vol name
        mirror_vol="%s_mirror_target" %(vol_name)
        cmds.append("volume create -vserver %s -volume %s -aggregate %s -size %s -state online -type RW -policy default -unix-permissions ---rwxr-xr-x -space-guarantee volume -snapshot-policy default -foreground true -antivirus-on-access-policy default -autosize true" %(mirror_vserver, mirror_vol, mirror_aggr, vol_size))
        cmds.append("snapmirror create -source-path  %s:%s -destination-path  %s:%s" %(vserver, vol_name, mirror_vserver, mirror_vol))
        for cmd in cmds:
            self._ssh_cmd(cmd)
    
    
    def _is_vol_mirrored(self, vserver, vol_name):
        source_path = '%s:%s' %(vserver, vol_name)
        cmd = 'snapmirror show -S %s' %(source_path)
        print (cmd)
        stdin, stdout, stderr = self.client.exec_command(cmd)
        stdin.close()
        stdout = stdout.readlines()
        for line in stdout:
            print (line)
        for line in stdout:
            if source_path in line:
                # If entries are returned find the destination path
                for line in stdout:
                    words = line.split()
                    for word in words:
                        if '%s_mirror_target' %(vol_name) in word:
                            return word
        return False
    
    
    def filer_test(self):
        cmd = 'vol show'
        self._ssh_cmd(cmd)
        
    
    def create_volume(self,
                      vserver,
                      vol_name,
                      vol_size='10GB',
                      source_aggr='aggr2',
                      mirror_aggr='aggr3',
                      dedup=False,
                      compression=False,
                      thin=False,
                      mirrored=False,
                      mirror_vserver=None,
                      qosPolicy=None):
        '''
        Create a volume with various attributes
        
        @param vserver: The name of the vserver
        @type vserver: str
        @param vol_name: The name of the filer's volume
        @type vol_name: str
        @param vol_size: *Default 10GB* size of the volume
        @type vol_size: str
        @param source_aggr: *Default 'aggr2'* this should be the main 
                                aggregate for creations on the primary vserver
        @type source_aggr: str
        @param mirror_aggr: *Default 'aggr3'* this is only used to create
                                an alternate volume in another vserver for
                                mirroring
        @type mirror_aggr: str
        @param dedup: *Default False* dedup=True/False
        @type dedup: bool
        @param compression: *Default False*  compression=True/False
        @type compression: bool
        @param thin: *Default False*  thin=True/False
        @type thin: bool
        @param mirrored: *Default False*  mirrored=True/False
        @type mirrored: bool
        @param mirror_vserver: *Default None* name of the vserver on
                                which to create the mirrored volume.  Must
                                be different from vserver
        @type mirror_vserver: str
        @param qosPolicy: *Default None*  Name of QOS policy to apply
                                If None, then no policy will be applied
        @type qosPolicy: str
        '''
        # Check for impossibilities
        if compression and not dedup:
            print "Can't have compression without dedup, converting dedup to true"
            dedup = True
        
        # Create the volume
        self._create_volume(vserver, vol_name, vol_size, source_aggr)
        
        if dedup:
            self.set_dedup(vserver, vol_name)
        if compression:
            self.set_compression(vserver, vol_name)
        if thin:
            self.set_thin(vserver, vol_name)
        if mirrored:
            if (mirror_vserver is not None) and (mirror_vserver is not vserver):
                self.mirror_vol(vserver,
                                 mirror_vserver,
                                 vol_name,
                                 vol_size,
                                 mirror_aggr)
        if qosPolicy is not None:
            self.create_set_QOS_policy(qosPolicy, vserver, vol_name)
    
    
    def _delete_volume(self, vserver, vol_name):
        cmds = []
        cmds.append("vol unmount -vserver %s -volume %s" %(vserver, vol_name))
        cmds.append("volume offline -vserver %s -volume %s -foreground true" %(vserver, vol_name))
        delcmd = "volume delete -vserver %s -volume %s -foreground true" %(vserver, vol_name)
        for cmd in cmds:
            self._ssh_cmd(cmd)
        self._ssh_yes_cmd(delcmd)
    
    
    def delete_volume(self, vserver, vol_name):
        '''
        Removes a volume and all of its snapmirrors from the vserver
        ''' 
        # Test for mirror relationships
        while self._is_vol_mirrored(vserver, vol_name) is not False:
            mirror = self._is_vol_mirrored(vserver, vol_name)
            cmd = "snapmirror delete -S %s:%s -destination-path %s -foreground true" %(vserver, vol_name, mirror)
            self._ssh_cmd(cmd)
            mirror = mirror.split(':')
            self._delete_volume(mirror[0], mirror[1])
        self._delete_volume(vserver, vol_name)
        
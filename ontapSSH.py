#!/usr/bin/python
# vim: tabstop=4 shiftwidth=4 softtabstop=4
#
# Copyright (c) 2013 NetApp, Inc.
# All Rights Reserved.

import paramiko
import socket

class NetappFiler:
    
    def __init__(self, host, username, password, port=22):
        # Create ssh client
        self.client=paramiko.SSHClient()
        self.client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        self.client.connect(host, port , username=username, password=password)


    def __del__(self):
        # Close ssh connection
        self.client.close()    
    
    
    def ssh_cmd(self, cmd):
        #print (cmd)
        stdin, stdout, stderr = self.client.exec_command(cmd)
        stdin.close()
        stdout = stdout.readlines()
        return stdout
    
    
    def _ssh_yes_cmd(self, cmd):
        #print (cmd)
        stdin, stdout, stderr = self.client.exec_command(cmd)
        stdin.write('y\n')
        stdin.flush()
        stdin.close()
        stdout = stdout.readlines()
        return stdout
    
    
    def _create_volume(self, vserver, vol_name, vol_size, target_aggr):
        # Creates a thick volume
        cmd = ("vol create -vserver %s -volume %s -aggregate %s -size %s "
               "-state online -type RW -policy default -user 0 -group 1 "
               "-security-style unix -unix-permissions ---rwxrwxrwx "
               "-max-autosize 60GB -autosize-increment 2.50GB "
               "-min-autosize 50GB -autosize-mode grow -space-guarantee volume"
               %(vserver, vol_name, target_aggr, vol_size))
        self.ssh_cmd(cmd)
    
    
    def create_set_QOS_policy(self, qosPolicy, vserver, vol_name):
        cmds = []
        # create policy-group
        cmds.append("policy-group create -policy-group %s -vserver %s "
                    "-max-throughput 500MB" %(qosPolicy, vserver))
        #apply policy group to a volume
        cmds.append("vol modify -vserver %s -volume %s -qos-policy-group %s"
                    %(vserver, vol_name, qosPolicy))
        for cmd in cmds:
            self.ssh_cmd(cmd)
    
    
    def set_dedup (self, vserver, vol_name):
        #turn dedup on for a volume
        cmd = "sis on -vserver %s -volume %s" %(vserver, vol_name)
        self.ssh_cmd(cmd)
    
    
    def set_compression (self, vserver, vol_name):
        cmds = []
        # turn on compession
        cmds.append("sis modify -vserver %s -volume %s -compression true"
                    %(vserver, vol_name))
        for cmd in cmds:
            self.ssh_cmd(cmd)
    
    
    def set_thick (self, vserver, vol_name):
        # make volume thick provisioned
        cmd = ("vol modify  -vserver %s -volume %s  -space-guarantee volume"
               %(vserver, vol_name))
        self.ssh_cmd(cmd)
    
    
    def set_thin (self, vserver, vol_name):
        # make volume thin provisioned
        cmd = ("vol modify  -vserver %s -volume %s -space-guarantee none"
               %(vserver, vol_name))
        self.ssh_cmd(cmd)
    
    
    def mirror_vol (self,
                    vserver,
                    mirror_vserver,
                    vol_name,
                    vol_size,
                    mirror_aggr):
        cmds = []
        # create mirror in other vserver based on existing volume.
        # autocreates target vol name
        mirror_vol="%s_mirror_target" %(vol_name)
        cmds.append("volume create -vserver %s -volume %s -aggregate %s "
                    "-size %s -state online -type RW -policy default "
                    "-unix-permissions ---rwxr-xr-x -space-guarantee volume "
                    "-snapshot-policy default -foreground true "
                    "-antivirus-on-access-policy default -autosize true"
                    %(mirror_vserver, mirror_vol, mirror_aggr, vol_size))
        cmds.append("snapmirror create -source-path  %s:%s "
                    "-destination-path  %s:%s"
                    %(vserver, vol_name, mirror_vserver, mirror_vol))
        for cmd in cmds:
            self.ssh_cmd(cmd)
    
    
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
        self.ssh_cmd(cmd)
        
    
    def create_volume(self,
                      vserver,
                      vol_name,
                      source_aggr,
                      vol_size='10GB',
                      mirror_aggr=None,
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
        @param source_aggr: This should be the main 
                                aggregate for creations on the primary vserver
        @type source_aggr: str
        @param mirror_aggr: *Default None* this is only used to create
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
            # Can't have compression without dedup, converting dedup to true
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
        cmds.append("volume offline -vserver %s -volume %s -foreground true"
                    %(vserver, vol_name))
        delcmd = ("volume delete -vserver %s -volume %s -foreground true"
                  %(vserver, vol_name))
        for cmd in cmds:
            self.ssh_cmd(cmd)
        self._ssh_yes_cmd(delcmd)
    
    
    def delete_volume(self, vserver, vol_name):
        '''
        Removes a volume and all of its snapmirrors from the vserver
        ''' 
        # Test for mirror relationships
        while self._is_vol_mirrored(vserver, vol_name) is not False:
            mirror = self._is_vol_mirrored(vserver, vol_name)
            cmd = ("snapmirror delete -S %s:%s -destination-path %s "
                   "-foreground true" %(vserver, vol_name, mirror))
            self.ssh_cmd(cmd)
            mirror = mirror.split(':')
            self._delete_volume(mirror[0], mirror[1])
        self.unmount_volume(vol_name)
        return self._delete_volume(vserver, vol_name)
    
    
    def get_vserver_aggrs(self, vserver):
        ''' Return a list of aggregates assigned to a given vserver '''
        
        aggrs = []
        cmd = 'vserver show -vserver %s -aggr-list *' %vserver
        rtn = self.ssh_cmd(cmd)
        for line in rtn:
            if 'List of Aggregates Assigned:' in line:
                aggrs = line.split(':')[-1]
                aggrs = aggrs.split(',')
                for idx, aggr in enumerate(aggrs):
                    aggrs[idx] = aggr.strip()
        return aggrs
    
    
    def get_vserver_data_ips(self, vserver):
        ''' Return a list of data IP addresses for a given vserver '''
        
        ips = []
        cmd = ('network interface show -vserver %s -lif * -status-oper up '
               '-status-admin up -role data' %vserver)
        rtn = self.ssh_cmd(cmd)
        for line in rtn:
            words = line.split()
            for word in words:
                ip = word.split('/')[0]
                try:
                    # Quickly determine valid IPv4 addresses
                    socket.inet_aton(ip)
                    ips.append(ip)
                    continue
                except socket.error:
                    pass
                try:
                    # Quickly determine valid IPv6 addresses
                    socket.inet_pton(socket.AF_INET6, ip)
                    ips.append(ip)
                except socket.error:
                    pass
        return ips
    
    
    def get_vserver_volumes(self, vserver):
        ''' Return a list of volumes defined on a given vserver '''
        
        volumes = []
        cmd = ('volume show -vserver %s' %vserver)
        rtn = self.ssh_cmd(cmd)
        for line in rtn[2:]:
            words = line.split()
            if len(words) >= 2:
                volumes.append(words[1])
        return volumes
    
    
    def get_volume(self, vserver, vol_name):
        '''
        Return a dictionary object containing details of a given volume
        
        Returns None if volume does not exist 
        '''
        
        volume = {}
        cmd = ('volume show -vserver %s -volume %s' %(vserver, vol_name))
        rtn = self.ssh_cmd(cmd)
        for line in rtn:
            line = line.strip()
            if line == 'There are no entries matching your query.':
                return None
            if line != '':
                words = line.split(':')
                volume[words[0].strip()] = words[1].strip()
        return volume
    
    
    def mount_volume(self, vol_name, mount=None):
        ''' Mounts a volume, junction path defaults to /vol_name '''
        
        if mount is None:
            mount = '/%s' %vol_name
        cmd = ('volume mount -volume %s -junction-path %s' %(vol_name, mount))
        self.ssh_cmd(cmd)
    
    
    def unmount_volume(self, vol_name):
        ''' Unmounts a volume '''
        cmd = ('volume unmount -volume %s' %vol_name)
        self.ssh_cmd(cmd)
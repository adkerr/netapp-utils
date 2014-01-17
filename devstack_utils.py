import subprocess

def start_cinder_volume():
    subprocess.check_call(["screen",
                           "-S", "stack",
                           "-p", "c-vol",
                           "-X", "stuff", "!!\n"])

def stop_cinder_volume():
    subprocess.call(["killall", "cinder-volume"])

def restart_cinder_volume():
    stop_cinder_volume()
    start_cinder_volume()
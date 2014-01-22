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

def start_cinder_scheduler():
    subprocess.check_call(["screen",
                           "-S", "stack",
                           "-p", "c-sch",
                           "-X", "stuff", "!!\n"])

def stop_cinder_scheduler():
    subprocess.call(["killall", "cinder-scheduler"])

def restart_cinder_scheduler():
    stop_cinder_scheduler()
    start_cinder_scheduler()

def start_cinder_backup():
    subprocess.check_call(["screen",
                           "-S", "stack",
                           "-p", "c-bak",
                           "-X", "stuff", "!!\n"])

def stop_cinder_backup():
    subprocess.call(["killall", "cinder-backup"])

def restart_cinder_backup():
    stop_cinder_backup()
    start_cinder_backup()

def start_cinder_api():
    subprocess.check_call(["screen",
                           "-S", "stack",
                           "-p", "c-api",
                           "-X", "stuff", "!!\n"])

def stop_cinder_api():
    subprocess.call(["killall", "cinder-api"])

def restart_cinder_api():
    stop_cinder_api()
    start_cinder_api()

def restart_cinder():
    restart_cinder_volume()
    restart_cinder_backup()
    restart_cinder_scheduler()
    restart_cinder_api()
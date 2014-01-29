import subprocess

def start_cinder_volume():
    subprocess.check_call(["screen",
                           "-S", "stack",
                           "-p", "c-vol",
                           "-X", "stuff", "!!\n"])

def stop_cinder_volume():
    try:
        pids = subprocess.check_output(["pgrep", "-f", "cinder-volume"])
    except subprocess.CalledProcessError:
        pass
    pids = pids.decode("utf-8")
    if pids == '':
        return
    pids = pids.splitlines()
    for pid in pids:
        subprocess.call(['kill', pid])
    

def restart_cinder_volume():
    stop_cinder_volume()
    start_cinder_volume()

def start_cinder_scheduler():
    subprocess.check_call(["screen",
                           "-S", "stack",
                           "-p", "c-sch",
                           "-X", "stuff", "!!\n"])

def stop_cinder_scheduler():
    try:
        pids = subprocess.check_output(["pgrep", "-f", "cinder-scheduler"])
    except subprocess.CalledProcessError:
        pass
    pids = pids.decode("utf-8")
    if pids == '':
        return
    pids = pids.splitlines()
    for pid in pids:
        subprocess.call(['kill', pid])

def restart_cinder_scheduler():
    stop_cinder_scheduler()
    start_cinder_scheduler()

def start_cinder_backup():
    subprocess.check_call(["screen",
                           "-S", "stack",
                           "-p", "c-bak",
                           "-X", "stuff", "!!\n"])

def stop_cinder_backup():
    try:
        pids = subprocess.check_output(["pgrep", "-f", "cinder-backup"])
    except subprocess.CalledProcessError:
        pass
    pids = pids.decode("utf-8")
    if pids == '':
        return
    pids = pids.splitlines()
    for pid in pids:
        subprocess.call(['kill', pid])

def restart_cinder_backup():
    stop_cinder_backup()
    start_cinder_backup()

def start_cinder_api():
    subprocess.check_call(["screen",
                           "-S", "stack",
                           "-p", "c-api",
                           "-X", "stuff", "!!\n"])

def stop_cinder_api():
    try:
        pids = subprocess.check_output(["pgrep", "-f", "cinder-api"])
    except subprocess.CalledProcessError:
        pass
    pids = pids.decode("utf-8")
    if pids == '':
        return
    pids = pids.splitlines()
    for pid in pids:
        subprocess.call(['kill', pid])

def restart_cinder_api():
    stop_cinder_api()
    start_cinder_api()

def restart_cinder():
    restart_cinder_volume()
    restart_cinder_backup()
    restart_cinder_scheduler()
    restart_cinder_api()
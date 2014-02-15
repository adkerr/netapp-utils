import subprocess

def start_cinder_volume():
    subprocess.check_call(["screen",
                           "-S", "stack",
                           "-p", "c-vol",
                           "-X", "stuff", "!!\n"])

def stop_cinder_volume():
    try:
        pids = subprocess.check_output(["pgrep", "-f", "cinder-volume"])
        pids = pids.decode("utf-8")
    except subprocess.CalledProcessError:
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
        pids = pids.decode("utf-8")
    except subprocess.CalledProcessError:
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
        pids = pids.decode("utf-8")
    except subprocess.CalledProcessError:
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
        pids = pids.decode("utf-8")
    except subprocess.CalledProcessError:
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

def stop_glance_api():
    try:
        pids = subprocess.check_output(["pgrep", "-f", "glance-api"])
        pids = pids.decode("utf-8")
    except subprocess.CalledProcessError:
        return
    pids = pids.splitlines()
    for pid in pids:
        subprocess.call(['kill', pid])

def start_glance_api():
    subprocess.check_call(["screen",
                           "-S", "stack",
                           "-p", "g-api",
                           "-X", "stuff", "!!\n"])

def restart_glance_api():
    stop_glance_api()
    start_glance_api()

def stop_glance_reg():
    try:
        pids = subprocess.check_output(["pgrep", "-f", "glance-registry"])
        pids = pids.decode("utf-8")
    except subprocess.CalledProcessError:
        return
    pids = pids.splitlines()
    for pid in pids:
        subprocess.call(['kill', pid])

def start_glance_reg():
    subprocess.check_call(["screen",
                           "-S", "stack",
                           "-p", "g-reg",
                           "-X", "stuff", "!!\n"])

def restart_glance_reg():
    stop_glance_reg()
    start_glance_reg()

def restart_glance():
    restart_glance_api()
    restart_glance_reg()
import os
import time
import paramiko

HOST, PORT, USER = "connect.nma1.seetacloud.com", 22841, "root"

for attempt in range(1, 6):
    try:
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        client.connect(HOST, port=PORT, username=USER,
                       password=os.environ["REMOTE_PW"], timeout=90,
                       banner_timeout=90, auth_timeout=90)
        _, out, err = client.exec_command("date '+%F %T %Z'; uptime", timeout=60)
        print("CONNECT_OK attempt", attempt)
        print(out.read().decode())
        client.close()
        break
    except Exception as e:
        print(f"attempt {attempt} failed: {type(e).__name__}: {e}")
        time.sleep(30)
else:
    print("ALL_ATTEMPTS_FAILED")

import sys
import os
import adsb_client
from daemon import runner

f = open(os.devnull, 'w')
sys.stdout = f

app = adsb_client.Client()
daemon_runner = runner.DaemonRunner(app)
daemon_runner.do_action()
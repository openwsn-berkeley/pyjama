# =========================== adjust path =====================================

import sys
import os
import json
import time
from datetime import datetime
import threading

if __name__ == "__main__":
    here = sys.path[0]
    sys.path.insert(0, os.path.join(here, '../', 'smartmeshsdk', 'libs'))

from SmartMeshSDK.utils import JsonManager

#============================ classes =========================================

class Logger(object):

    LOG_FILE  = "sm.log"
    def __init__(self, manager_port, first_logfile, snapshot_interval):
        self.manager_port         = manager_port
        self.lock                 = threading.RLock()
        self.logfile              = first_logfile
        self.snapshot_interval    = snapshot_interval
        self.loggin               = True
        # initialize JsonManager
        self.jsonManager          = JsonManager.JsonManager(
             autoaddmgr           = False,
             autodeletemgr        = False,
             serialport           = self.manager_port,
             notifCb              = self._notif_cb,
        )
        # create or empty file
        self._clean_logfile()
        # wait for manager to be connected
        while self.jsonManager.managerHandlers == {}:
            time.sleep(1)
        while self.jsonManager.managerHandlers[self.jsonManager.managerHandlers.keys()[0]].connector is None:
            time.sleep(1)

        self.snapshot_thread      = threading.Thread(
                        name      = 'snapshot_thread',
                        target    = self._trigger_snapshot,
                        args      = (self.snapshot_interval,),
        )
        self.snapshot_thread.start()

    # =========================== private ==========================================

    def _trigger_snapshot(self, interval):
        while True:
            time.sleep(interval)
            # snapshot
            self.jsonManager.snapshot_POST(self.manager_port)

    def _change_experiment(self, new_logfile):
        self.logfile    = new_logfile
        self._clean_logfile()
        self.loggin     = True
        self._send_reset()


    def _clean_logfile(self):
        with open(self.logfile, 'w') as f:
            pass

    def _send_reset(self):
        notifJson       = self.jsonManager.raw_POST(
           commandArray = ["reset"],
           fields       = {'type': 0x00, 'macAddress': '00-17-0d-00-00-31-c7-de'},
           manager      = self.manager_port ,
        )
        self._notif_cb('reset', notifJson)

    def _notif_cb(self,notifName, notifJson):
        with self.lock:
            # add notif name if not present
            if 'name' not in notifJson:
                notifJson['name'] = notifName

            # add datetime
            if 'datetime' not in notifJson:
                notifJson['datetime'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            # write to file
            if self.logging:
                with open(self.logfile, 'a') as f:
                    f.write(json.dumps(notifJson) + "\n")


# =========================== main ============================================


if __name__ == "__main__":
    test = Logger('/dev/ttyUSB3','one.log', 60)

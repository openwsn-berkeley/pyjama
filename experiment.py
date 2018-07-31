import paramiko
import time
from wifi import Cell, Scheme
import threading
import Queue
import logger
import inspect
import logging


WIFI_INTERFACE     = 'wlp1s0'
WIFI_AP            = ['rpi2', 'rpi4','rpi6',]
WIFI_CLIENTS       = {
    WIFI_AP[0]: 'rpi3',
    WIFI_AP[1]: 'rpi5',
    WIFI_AP[2]: 'rpi7',
}

TURN_ON_AP_COMMAND = 'sudo service hostapd start'
TURN_OFF_AP_COMMAND = 'sudo service hostapd stop'
CONNECT_WIFI       = 'sudo wpa_supplicant -Dnl80211 -iwlan0 -c/etc/wpa_supplicant/wpa_supplicant.conf'
DEFAULT_IP_CLIENTS = '192.168.42.22'
RPI_USERNAME       = 'pi'
RPI_PASS           = 'inria'
MAX_TX_RATE        = 16000 # kbits = 2 Mbytes
TEST_TIME          = 60*60
SNAPSHOT_INTERVAL  = 60*20
LOGFILE            = 'program_status.log'



#============================ classes =========================================
class Wifi_experiment(object):

    def __init__(self):

        with open(LOGFILE, 'w') as f:
            pass
        logging.basicConfig(filename=LOGFILE,level=logging.INFO)
        # local variables
        self.logger          = logger.Logger('/dev/ttyUSB3', 'one.log', SNAPSHOT_INTERVAL)
        self.running_test    = False
        self.traffic_levels  = [0, 0.5, 1]
        self.experiments     = []
        # populate experiments array
        for t in self.traffic_levels:
            for n in range(0,4):
                if n==0 and t!=0:
                    continue
                parameters   = {}
                parameters['traffic']            = t
                parameters['active_networks']    = []
                for a in range(0,n):
                    parameters['active_networks']+= [WIFI_AP[a],]
                parameters['disable_networks']   = []
                for d in range(2,n-1,-1):
                    parameters['disable_networks']+= [WIFI_AP[d],]
                parameters['name']     = '{0}_wifiAP_{1}_traffic'.format(n,t)
                self.experiments      += [parameters,]

        for e in self.experiments:
            logging.info('Start test')
            logging.info(e)
            self._do_test(e)
            logging.info('End test')


    #======================== public ==========================================

    #======================== private =========================================

    #======== principal functions

    def _do_test(self, parameters):
        # turn on and off the AP
        self._set_wifi_networks(parameters['active_networks'], parameters['disable_networks'])
        logging.info('wifi networks done')
        file_tranfers         = []
        self.running_test     = True
        if parameters['traffic']!=0:
            # make sure of wifi clients connection
            self._set_wifi_clients(parameters['active_networks'])
            # run file tranfers
            for n in parameters['active_networks']:
                file_tranfers    += [threading.Thread(
                    target        = self._send_file,
                    args          = ('{0}.local'.format(n), parameters['traffic'], True,)
                ),]
            for f in file_tranfers:
                f.start()
        self.logger._change_experiment('{0}.log'.format(parameters['name']))
        # just log from the manager during a TEST_TIME
        time.sleep(TEST_TIME)
        self.logger._change_experiment('one.log')
        self.running_test     = False
        # stop file tranfers
        for n in parameters['active_networks']:
            self._send_sshcommand('{0}.local'.format(n), 'sudo killall ssh', False)
        # wait for file transfer finish
        for f in file_tranfers:
            f.join()

    #========= misc

    def _set_wifi_networks(self, active_networks, disable_networks):
        for n in active_networks:
            self._send_sshcommand('{0}.local'.format(n), TURN_ON_AP_COMMAND, False)
            self._waitforwifinetworkon(n)

        for n in disable_networks:
            self._send_sshcommand('{0}.local'.format(n), TURN_OFF_AP_COMMAND, False)
            self._waitforwifinetworkoff(n)

    def _set_wifi_clients(self, active_networks):
        for n in active_networks:
            self._send_sshcommand('{0}.local'.format(WIFI_CLIENTS[n]), CONNECT_WIFI, False)
            self._wait_until_wifi_connection('{0}.local'.format(WIFI_CLIENTS[n]))

    def _send_sshcommand(self, hostname, command, is_loop):
        result     = []
        ssh_session     = paramiko.SSHClient()
        ssh_session.load_system_host_keys()
        ssh_session.connect(hostname, username=RPI_USERNAME, password=RPI_PASS)
        if is_loop:
            out    = False
            while self.running_test:
                stdin,stdout,stderr = ssh_session.exec_command(command)
                out     = stdout.read()
            return out
        else:
            ssh_result  = ssh_session.exec_command(command)
            result   += [ssh_result[1].read(),]
            result   += [ssh_result[2].read(),]
            ssh_session.close()
            return result

    def _waitforwifinetworkon(self, ssid):
        goOn  = True
        while goOn:
            wifi_networks    = Cell.all(WIFI_INTERFACE)
            for w in wifi_networks:
                if w.ssid == ssid:
                    goOn     = False
                    break

    def _waitforwifinetworkoff(self, ssid):
        goOn  = True
        while goOn:
            wifi_networks    = Cell.all(WIFI_INTERFACE)
            goOn             = False
            for w in wifi_networks:
                if w.ssid == ssid:
                    goOn     = True
                    break

    def _wait_until_wifi_connection(self, hostname):
        goOn  = True
        while goOn:
            result = self._send_sshcommand(hostname, 'hostname -I',False)
            if result[0].find(DEFAULT_IP_CLIENTS) != -1:
                goOn    = False
            else:
                time.sleep(0.2)

    def _send_file(self, hostname_tx, percentage_rate, is_loop):
        command    = 'sshpass -p "inria" scp -l {0} /home/pi/Documents/file_to_send.img pi@192.168.42.22:/home/pi/Documents/'.format(int(MAX_TX_RATE*percentage_rate))
        ssh_result = self._send_sshcommand(hostname_tx, command, is_loop)
        return ssh_result

#============================ main ============================================

if __name__ == '__main__':
    experiment = Wifi_experiment()

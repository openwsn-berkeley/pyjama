import paramiko
import time
from wifi import Cell, Scheme
import threading
import Queue
import logger
import inspect
import logging
import RPi.GPIO as GPIO


WIFI_INTERFACE     = 'wlan0'
#WIFI_INTERFACE     = 'wlp1s0'
WIFI_AP            = ['wifitest1', 'wifitest2','wifitest3',]

WIFI_CLIENTS_ETH   = {
    WIFI_AP[0]: '192.168.1.109',
    WIFI_AP[1]: '192.168.1.104',
    WIFI_AP[2]: '192.168.1.110',
}

WIFI_CLIENTS   = {
    WIFI_AP[0]: '192.168.1.105',
    WIFI_AP[1]: '192.168.1.111',
    WIFI_AP[2]: '192.168.1.112',
}

WIFI_SENDER       = {
    WIFI_AP[0]: '192.168.1.101',
    WIFI_AP[1]: '192.168.1.102',
    WIFI_AP[2]: '192.168.1.108',
}

GPIO_PORTS       = {
    WIFI_AP[0]: 14,
    WIFI_AP[1]: 15,
    WIFI_AP[2]: 18,
}

TURN_ON_AP_COMMAND      = 'sudo service hostapd start'
TURN_OFF_AP_COMMAND     = 'sudo service hostapd stop'
CONNECT_WIFI            = 'sudo wpa_supplicant -Dnl80211 -iwlan0 -c/etc/wpa_supplicant/wpa_supplicant.conf'
DEFAULT_IP_CLIENTS      = '192.168.42.22'
DEFAULT_IP_CLIENTS      = '169.254.0.109'
DEFAULT_IP_AP           = '169.254.0.109'
RPI_USERNAME            = 'pi'
RPI_PASS                = 'inria'
MAX_TX_RATE             = 48000 # kbits = 2 Mbytes
TEST_TIME               = 60*60*9.5
SNAPSHOT_INTERVAL       = 60*15
LOGFILE                 = 'program_status.log'
NET_ID                  = 400
TIME_BTW_EXP            = 60*10


#============================ classes =========================================
class Wifi_experiment(object):

    def __init__(self):

        with open(LOGFILE, 'w') as f:
            pass
        logging.basicConfig(filename=LOGFILE,level=logging.INFO)
        # local variables
        self.logger          = logger.Logger('/dev/ttyUSB3', 'one.log', SNAPSHOT_INTERVAL)
        self.running_test    = False
        self.traffic_levels  = [0, 0.15, 0.35]
        self.experiments     = []
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(14, GPIO.OUT)
        GPIO.setup(15, GPIO.OUT)
        GPIO.setup(18, GPIO.OUT)
        #populate experiments array
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

 #       self._small_test()


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
           # self._set_wifi_clients(parameters['active_networks'])
            time.sleep(60) 
	   # run file tranfers
            for n in parameters['active_networks']:
                file_tranfers    += [threading.Thread(
                    target        = self._send_file,
                    args          = (WIFI_SENDER[n], WIFI_CLIENTS[n],parameters['traffic'], True,)
                ),]
            for f in file_tranfers:
                f.start()

        self.logger._change_experiment('{0}.log'.format(parameters['name']))
        self.logger._change_netid(NET_ID)
        # just log from the manager during a TEST_TIME
        time.sleep(TEST_TIME)
	self.logger._change_experiment('one.log')
	self.logger._change_netid(NET_ID+1)
        time.sleep(TIME_BTW_EXP)
        self.running_test     = False
        # stop file tranfers
	if parameters['traffic']!=0:
           for n in parameters['active_networks']:
               self._send_sshcommand(WIFI_SENDER[n], 'sudo killall ssh', False)
        # wait for file transfer finish
        for f in file_tranfers:
            f.join()

    def _small_test(self):
        self._waitforwifinetworkon('wifitest')
        logging.info('wifi networks done')
        file_tranfers         = []
        self.running_test     = True
        logging.info('a conectarse')
        self._send_sshcommand('169.254.0.108', CONNECT_WIFI, False)
        logging.info('comando enviado')
        self._wait_until_wifi_connection('169.254.0.108')
        logging.info('listas conexiones')
        send_file = threading.Thread(
                target        = self._send_file,
                args          = ('169.254.0.105', '169.254.0.109', 1, True,)
                )
        send_file.start()
        self.logger._change_experiment('{0}.log'.format('routertest'))
        time.sleep(TEST_TIME)

        self.logger._change_experiment('one.log')
        self.running_test     = False

        self._send_sshcommand('169.254.0.105', 'sudo killall ssh', False)
        send_file.join()
    #========= misc

    def _set_wifi_networks(self, active_networks, disable_networks):
        for n in active_networks:
            GPIO.output(GPIO_PORTS[n], GPIO.HIGH)
            self._waitforwifinetworkon(n)

        for n in disable_networks:
            GPIO.output(GPIO_PORTS[n], GPIO.LOW)
            self._waitforwifinetworkoff(n)

    def _set_wifi_clients(self, active_networks):
        for n in active_networks:
            self._send_sshcommand('{0}'.format(WIFI_CLIENTS[n]), CONNECT_WIFI, False)
            self._wait_until_wifi_connection(n)

    def _send_sshcommand(self, hostname, command, is_loop):
        result     = []
        ssh_session     = paramiko.SSHClient()
        ssh_session.load_system_host_keys()
        ssh_session.set_missing_host_key_policy(paramiko.AutoAddPolicy())
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
	    try:
                wifi_networks    = Cell.all(WIFI_INTERFACE)
            except:
		wifi_networks    = []
            for w in wifi_networks:
                if w.ssid == ssid:
                    goOn     = False
                    break

    def _waitforwifinetworkoff(self, ssid):
        goOn  = True
        while goOn:
	    try:
                wifi_networks    = Cell.all(WIFI_INTERFACE)
                goOn             = False
            except:
		wifi_networks    = []
            for w in wifi_networks:
                if w.ssid == ssid:
                    goOn     = True
                    break

    def _wait_until_wifi_connection(self, wifi_ap):
        goOn  = True
        while goOn:
            result = self._send_sshcommand(WIFI_CLIENTS_ETH[wifi_ap], 'hostname -I',False)
            logging.info(result)
            if result[0].find(WIFI_CLIENTS[wifi_ap]) != -1:
                goOn    = False
            else:
                time.sleep(0.2)

    def _send_file(self, hostname_tx, hostname_rx, percentage_rate, is_loop):
        if percentage_rate == 1 :
            command    = 'sshpass -p "inria" scp /home/pi/Documents/file_to_send.img pi@{0}:/home/pi/Documents/'.format(hostname_rx)
        else:
            command    = 'sshpass -p "inria" scp -l {0} /home/pi/Documents/file_to_send.img pi@{1}:/home/pi/Documents/'.format(int(MAX_TX_RATE*percentage_rate), hostname_rx)

        logging.info(command)
        ssh_result = self._send_sshcommand(hostname_tx, command, is_loop)
        return ssh_result

#============================ main ============================================

if __name__ == '__main__':
    experiment = Wifi_experiment()

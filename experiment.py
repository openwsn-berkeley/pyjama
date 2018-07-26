import paramiko
import time
from wifi import Cell, Scheme
import threading
import Queue
import logger
import inspect

WIFI_INTERFACE     = 'wlp1s0'
WIFI_AP            = ['rpi2', 'rpi4','rpi6',]
WIFI_CLIENTS       = {
    WIFI_AP[0]: 'rpi3',
    WIFI_AP[1]: 'rpi5',
    WIFI_AP[2]: 'rpi7',
}
RPI2_HOSTNAME      = 'rpi2.local'
RPI3_HOSTNAME      = 'rpi3.local'
RPI2_WIFI          = 'rpi2'
RPI4_WIFI          = 'rpi4'
RPI6_WIFI          = 'rpi6'
TURN_ON_AP_COMMAND = 'sudo service hostapd start'
TURN_OFF_AP_COMMAND = 'sudo service hostapd stop'
CONNECT_WIFI       = 'sudo wpa_supplicant -Dnl80211 -iwlan0 -c/etc/wpa_supplicant/wpa_supplicant.conf'
DEFAULT_IP_CLIENTS = '192.168.42.22'
RPI_USERNAME       = 'pi'
RPI_PASS           = 'inria'
MAX_TX_RATE        = 16000 # kbits = 2 Mbytes
TEST_TIME          = 60



#============================ classes =========================================
class Wifi_experiment(object):

    def __init__(self):
        # store params

        # local variables
        self.logger     = logger.Logger('/dev/ttyUSB3', 'one.log', 30)
        # First test: No Wifi networks at all
        #self._no_wifi_networks_at_all_test()
        # Second test: rpi2 wifi network activated
        #self._onlyrpi2wifinetwork_test()
        # Third test: 50% traffic level one wifi network
        #self._onlyrpi2wifiaveragetraffic_test()



    #======================== public ==========================================

    #======================== private =========================================

    #======== principal functions

    def _do_test(self, parameters):
        # turn on and off the AP
        self._set_wifi_networks(parameters['active_networks'], parameters['disable_networks'])
        file_tranfers         = []
        if parameters['traffic']!=0:
            # make sure of wifi clients connection
            self._set_wifi_clients(parameters['active_networks'])
            # run file tranfers
            for n in parameters['active_networks']:
                file_tranfers    += threading.Thread(
                    target        = self._send_file,
                    args          = ('{0}.local'.format(n), parameters['traffic'], TEST_TIME)
                )
            for f in file_tranfers:
                f.start()
        self.logger._change_experiment('{0}.log'.format(parameters['name']))


    '''
    def _no_wifi_networks_at_all_test(self):
        active_networks      = []
        disable_networks     = WIFI_AP
        self._set_wifi_networks(active_networks, disable_networks)
        #
        self.logger._change_experiment('{0}.log'.format(inspect.stack()[0][3]))

    def _onlyrpi2wifinetwork_test(self):

        self._send_sshcommand(RPI2_HOSTNAME, TURN_ON_AP_COMMAND, 0)
        self._waitforwifinetworkon(RPI2_WIFI)
        print 'listo'
        # TO_DO: algo para leer puerto serial y todo eso

    def _onlyrpi2wifiaveragetraffic_test(self):
        # check if rpi3 connected to rpi2 wifi
        self._send_sshcommand(RPI3_HOSTNAME, CONNECT_WIFI, 0)
        self._wait_until_wifi_connection(RPI3_HOSTNAME)
        # at this point rp3 and rp2 are ready to exchange information
        self._send_file(RPI2_HOSTNAME, 1, 20)
        # TO_DO: algo para leer puerto serial y todo eso
    '''
    #========= misc

    def _set_wifi_networks(self, active_networks, disable_networks):
        for n in active_networks:
            self._send_sshcommand('{0}.local'.format(n), TURN_ON_AP_COMMAND, 0)
            self._waitforwifinetworkon(n)

        for n in disable_networks:
            self._send_sshcommand('{0}.local'.format(n), TURN_OFF_AP_COMMAND, 0)
            self._waitforwifinetworkoff(n)

    def _set_wifi_clients(self, active_networks):
        for n in active_networks:
            self._send_sshcommand('{0}.local'.format(WIFI_CLIENTS[n]), CONNECT_WIFI, 0)
            self._wait_until_wifi_connection('{0}.local'.format(WIFI_CLIENTS[n]))

    def _send_sshcommand(self, hostname, command, time_out):
        result     = []
        ssh_session     = paramiko.SSHClient()
        ssh_session.load_system_host_keys()
        ssh_session.connect(hostname, username=RPI_USERNAME, password=RPI_PASS)
        if time_out != 0:
            stop_queue            = Queue.Queue()
            exec_command_thread   = threading.Thread(
                target            = self._loop_command,
                args              = (ssh_session, command, stop_queue)
            )
            exec_command_thread.start()
            time.sleep(time_out)
            stop_queue.put('stop')
            self._send_sshcommand(hostname, 'sudo killall ssh', 0)
            exec_command_thread.join()
        else:
            ssh_result      = ssh_session.exec_command(command)
            result   += [ssh_result[1].read(),]
            result   += [ssh_result[2].read(),]
            ssh_session.close()
            return result

    def _loop_command(self, ssh_session, command, stop_queue):
        while stop_queue.empty():
            stdin,stdout,stderr = ssh_session.exec_command(command)
            out = stdout.read()


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
            result = self._send_sshcommand(hostname, 'hostname -I',0)
            if result[0].find(DEFAULT_IP_CLIENTS) != -1:
                goOn    = False
            else:
                time.sleep(0.2)

    def _send_file(self, hostname_tx, percentage_rate, time_out):
        command    = 'sshpass -p "inria" scp -l {0} /home/pi/Documents/file_to_send.img pi@192.168.42.22:/home/pi/Documents/'.format(int(MAX_TX_RATE*percentage_rate))
        ssh_result = self._send_sshcommand(hostname_tx, command, time_out)
        return ssh_result

#============================ main ============================================

if __name__ == '__main__':
    experiment = Wifi_experiment()

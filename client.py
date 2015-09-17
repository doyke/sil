""" 
Stream data from a TCP server providing datafeed of ADS-B messages

"""

import socket
import sys, os
import time
import datetime
from pymongo import MongoClient
from adsb_decoder import decoder

class Client():

    def __init__(self):
        self.stdin_path = '/dev/null'
        self.stdout_path = '/dev/tty'
        self.stderr_path = '/dev/tty'
        self.pidfile_path =  '/tmp/sil-adsb-client.pid'
        self.pidfile_timeout = 5

    def connect(self, host, port):
        while True:
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.settimeout(10)    # 10 second timeout
                s.connect((host, port))
                print "Server %s connected" % host
                return s
            except socket.error as err:
                print "Socket connection error: %s. reconnecting..." % err
                time.sleep(3)

    def read_mode_s(self, raw):
        '''
        <esc> "1" : 6 byte MLAT timestamp, 1 byte signal level, 2 byte Mode-AC
        <esc> "2" : 6 byte MLAT timestamp, 1 byte signal level, 7 byte Mode-S short frame
        <esc> "3" : 6 byte MLAT timestamp, 1 byte signal level, 14 byte Mode-S long frame
        <esc> "4" : 6 byte MLAT timestamp, status data, DIP switch configuration settings (not on Mode-S Beast classic)
        <esc><esc>: true 0x1a
        <esc> is 0x1a, and "1", "2" and "3" are 0x31, 0x32 and 0x33

        timestamp: 
        http://wiki.modesbeast.com/Radarcape:Firmware_Versions#The_GPS_timestamp
        '''

        # convert raw data to integer represntation
        data = [ord(i) for i in raw]

        # split raw data into chunks
        chunks = []
        separator = 0x1a
        piece = []
        for d in data:
            if d == separator:
                # shortest msgs are 11 chars
                if len(piece) > 10 :
                    chunks.append(piece)
                piece =[]
            piece.append(d)

        # extract messages
        messages = []
        for cnk in chunks:
            msgtype = cnk[1]

            # Mode-S Short Message, 7 byte
            if msgtype == 0x32:
                msg = ''.join('%02X' % i for i in cnk[9:16])

            # Mode-S Short Message, 14 byte
            elif msgtype == 0x33:
                msg = ''.join('%02X' % i for i in cnk[9:23])

            # Other message tupe
            else:
                continue

            ts = time.time()

            messages.append([msg, ts])
        return messages


    def run(self):
        mclient = MongoClient('localhost', 27017)
        mdb = mclient.SIL

        host = '127.0.0.1'
        port = 30334
        tcp_buffer_size = 1024

        sock = self.connect(host, port)


        while True:
            try:
                raw = sock.recv(tcp_buffer_size)
                # print ''.join(x.encode('hex') for x in raw)

                messages = self.read_mode_s(raw)

                if not messages:
                    continue

                for msg, ts in messages:
                    if len(msg) < 28:
                        continue

                    df = decoder.get_df(msg)
                    if df != 17:
                        continue

                    if not decoder.checksum(msg):
                        continue

                    addr = decoder.get_icao_addr(msg)
                    tc = decoder.get_tc(msg)
                    adsb = {}
                    adsb['addr'] = addr
                    adsb['msg'] = msg
                    adsb['tc'] = tc
                    adsb['time'] = ts

                    # get the current MongoDB collection, by data
                    coll_name = str(datetime.date.today())
                    mcoll = mdb[coll_name]
                    mcoll.insert(adsb)

            except Exception, e:
                print "Unexpected Error:", e
                pass

if __name__ == '__main__':
    client = Client()
    client.run()
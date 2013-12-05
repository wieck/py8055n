"""
k8055n.py - Velleman K8055(N)/VM110(N) access via pylibusb.
"""

import ctypes
import math
import pylibusb as usb

DEBUG = False

K8055 = 'K8055'
K8055N = 'K8055N'
OPEN8055 = 'OPEN8055'

TAG_OLD_SET_DEBOUNCE = 1
TAG_OLD_RESET_COUNTER = 3
TAG_OLD_SET_OUTPUT = 5

TAG_NEW_SET_PROTO = 6
TAG_NEW_SET_DEBOUNCE = 11
TAG_NEW_RESET_COUNTER = 13      # 13 and 14
TAG_NEW_SET_DIGITAL_OUT = 15
TAG_NEW_GET_DIGITAL_IN = 16
TAG_NEW_GET_ANALOG_IN = 17
TAG_NEW_GET_COUNTER = 18        # 18 and 19
TAG_NEW_GET_COUNTER16 = 20      # 21 and 21

usb.init()

class py8055n:
    """
    Implements a connection to a physically attached K8055(N)/VM110(N)
    Experimental USB Interface Card. 
    """

    ##########
    # py8055n - Creating a new card instance.
    ##########
    def __init__(self, card_number, protocol = None):
        """
        Open a K8055(N) card and attempt to switch it to the new K8055N
        protocol. If successful, read all current settings of the card.
        """
        self.card_number = card_number
        self.recv_buffer = ctypes.create_string_buffer(8)
        self.send_buffer = ctypes.create_string_buffer(8)
        self.libusb_handle = None

        # ----
        # Search for the specified K8055(N) device.
        # ----
        busses = usb.get_busses()
        if not busses:
            usb.find_busses()
            usb.find_devices()
            busses = usb.get_busses()
        found = False
        for bus in busses:
            for dev in bus.devices:
                self._debug('idVendor: 0x%04x idProduct: 0x%04x'%(dev.descriptor.idVendor,
                                                            dev.descriptor.idProduct))
                if (dev.descriptor.idVendor == 0x10cf and
                    dev.descriptor.idProduct == 0x5500 + card_number):
                    found = True
                    break
            if found:
                break
        if not found:
            raise RuntimeError('Cannot find K8055(N) number {0}'.format(
                    card_number))

        # ----
        # Open device.
        # ----
        self._debug('found device', dev)
        self.libusb_handle = usb.open(dev)

        # ----
        # Detach an eventually attached kernel driver.
        # ----
        self.interface_nr = 0
        if hasattr(usb, 'get_driver_np'):
            # non-portable libusb extension
            name = usb.get_driver_np(self.libusb_handle, self.interface_nr)
            if name != '':
                self._debug("attached to kernel driver '%s', detaching."%name)
                usb.detach_kernel_driver_np(self.libusb_handle,
                        self.interface_nr)
                self.had_kernel_driver = True
            else:
                self.had_kernel_driver = False

        # ----
        # Set to configuration 0.
        # ----
        if dev.descriptor.bNumConfigurations > 1:
            self._debug("WARNING: more than one configuration, choosing first")
        self._debug('setting configuration')
        self._debug('dev.config[0]', dev.config[0])
        config = dev.config[0]
        self._debug('config.bConfigurationValue', config.bConfigurationValue)
        usb.set_configuration(self.libusb_handle, config.bConfigurationValue)

        # ----
        # Claim interface.
        # ----
        self._debug('config.bNumInterfaces', config.bNumInterfaces)
        self._debug('claiming interface')
        usb.claim_interface(self.libusb_handle, self.interface_nr)

        # ----
        # Attempt to switch to the requested protocol ("new" by default)
        # ----
        if protocol is None or protocol == K8055N:
            self._debug('attempt to switch to "new" K8055N protocol')
            self.send_buffer[0] = chr(TAG_NEW_SET_PROTO)
            self._send_pkt()
            self._recv_pkt()
        elif protocol == K8055:
            self._recv_pkt()
            if ord(self.recv_buffer[1]) > 20:
                raise RuntimeError('Cannot enforce "old" protocol')
            else:
                if ord(self.recv_buffer[1]) > 10:
                    self._debug('enforce "old" protocol on K8055N')
                    self.recv_buffer[1] = chr(card_number + 1)
                else:
                    self._debug('found original K8055')
        elif protocol is None:
            self.send_buffer[0] = chr(TAG_NEW_SET_PROTO)
            self._send_pkt()
            self._recv_pkt()

        if ord(self.recv_buffer[1]) > 10:
            for i in range(0, 33):
                if ord(self.recv_buffer[1]) > 20:
                    break
                self._send_pkt()
                self._recv_pkt()
            if not ord(self.recv_buffer[1]) > 20:
                raise RuntimeError('Failed to switch K8055N to new protocol')
            self.card_type = K8055N
        else:
            self.card_type = K8055

    ##########
    # __del__()
    ##########
    def __del__(self):
        """
        Cleanup on object destruction.
        """
        if self.libusb_handle is not None:
            self.close()

    ##########
    # close()
    ##########
    def close(self):
        """
        Close the connection to this K8055(N) and restore the kernel
        device driver (if there was one on open).
        """
        usb.release_interface(self.libusb_handle, self.interface_nr)
        if hasattr(usb, 'get_driver_np') and self.had_kernel_driver:
            usb.attach_kernel_driver_np(self.libusb_handle, self.interface_nr)
        usb.close(self.libusb_handle)
        self.libusb_handle = None

    ##########
    # set_counter_debounce_time()
    ##########
    def set_counter_debounce_time(self, port, ms):
        """
        Set the debounce time of 'port' to 'ms' milliseconds.
        """
        if port < 0 or port > 1:
            raise RuntimeError('invalid counter number %d'%port)

        val = int(round(0.9 * 2.4541 * math.pow(ms, 0.5328)))
        if val < 1:
            val = 1
        if val > 255:
            val = 255
        val = chr(val)

        if self.card_type == K8055N:
            self.send_buffer[0] = chr(port + TAG_NEW_SET_DEBOUNCE)
            self.send_buffer[6 + port] = val
        elif self.card_type == K8055:
            self.send_buffer[0] = chr(port + TAG_OLD_SET_DEBOUNCE)
            self.send_buffer[6 + port] = val
        else:
            raise Exception('internal card_type error')
        self._send_pkt()
        
    ##########
    # reset_counter()
    ##########
    def reset_counter(self, port):
        """
        Reset a counter.
        """
        if port < 0 or port > 1:
            raise RuntimeError('invalid counter number %d'%port)

        if self.card_type == K8055N:
            self.send_buffer[0] = chr(port + TAG_NEW_RESET_COUNTER)
        elif self.card_type == K8055:
            self.send_buffer[0] = chr(port + TAG_OLD_RESET_COUNTER)
        else:
            raise Exception('internal card_type error')
        self._send_pkt()
        
    ##########
    # set_digital_all()
    ##########
    def set_digital_all(self, val):
        """
        Set the state of all digital outputs.
        """
        if self.card_type == K8055N:
            self.send_buffer[0] = chr(TAG_NEW_SET_DIGITAL_OUT)
        elif self.card_type == K8055:
            self.send_buffer[0] = chr(TAG_OLD_SET_OUTPUT)
        else:
            raise Exception('internal card_type error')
        self.send_buffer[1] = chr(val)
        self._send_pkt()

    ##########
    # read_digital_all()
    ##########
    def read_digital_all(self):
        """
        Read the state of all digital inputs.
        """
        if self.card_type == K8055N:
            self.send_buffer[0] = chr(TAG_NEW_GET_DIGITAL_IN)
            self._send_pkt()
        elif self.card_type == K8055:
            pass
        else:
            raise Exception('internal card_type error')
        self._recv_pkt()
        val = ord(self.recv_buffer[0])
        return (((val & 0x10) >> 4) |
                ((val & 0x20) >> 4) |
                ((val & 0x01) << 2) |
                ((val & 0x40) >> 3) |
                ((val & 0x80) >> 3))
        return ord(self.recv_buffer[0])

    ##########
    # read_counter()
    ##########
    def read_counter(self, port):
        """
        Read the current counter of 'port'.
        """
        if port < 0 or port > 1:
            raise RuntimeError('illegal counter number %d'%port)
        if self.card_type == K8055N:
            self.send_buffer[0] = chr(TAG_NEW_GET_COUNTER + port)
            self._send_pkt()
            self._recv_pkt()
            return ((ord(self.recv_buffer[4])) |
                    (ord(self.recv_buffer[5]) << 8) |
                    (ord(self.recv_buffer[6]) << 16) |
                    (ord(self.recv_buffer[7]) << 24))
        elif self.card_type == K8055:
            self._recv_pkt()
            return ((ord(self.recv_buffer[4 + port * 2])) |
                    (ord(self.recv_buffer[5 + port * 2]) << 8))
        else:
            raise Exception('internal card_type error')

    ##########
    # read_counter16()
    ##########
    def read_counter16(self, port):
        """
        Read the current counter of 'port' (16 bit compatibility version).
        """
        if port < 0 or port > 1:
            raise RuntimeError('illegal counter number %d'%port)
        if self.card_type == K8055N:
            self.send_buffer[0] = chr(TAG_NEW_GET_COUNTER16 + port)
            self._send_pkt()
            self._recv_pkt()
        elif self.card_type == K8055:
            self._recv_pkt()
        else:
            raise Exception('internal card_type error')
        return ((ord(self.recv_buffer[4 + port * 2])) |
                (ord(self.recv_buffer[5 + port * 2]) << 8))

    ##########
    # set_analog_all()
    ##########
    def set_analog_all(self, val1, val2):
        """
        Set the state of all analog outputs.
        """
        if self.card_type == K8055N:
            self.send_buffer[0] = chr(TAG_NEW_SET_DIGITAL_OUT)
        elif self.card_type == K8055:
            self.send_buffer[0] = chr(TAG_OLD_SET_OUTPUT)
        else:
            raise Exception('internal card_type error')
        self.send_buffer[2] = chr(val1)
        self.send_buffer[3] = chr(val2)
        self._send_pkt()

    ##########
    # read_analog_all()
    ##########
    def read_analog_all(self):
        """
        Read the state of all digital inputs.
        """
        if self.card_type == K8055N:
            self.send_buffer[0] = chr(TAG_NEW_GET_ANALOG_IN)
            self._send_pkt()
        elif self.card_type == K8055:
            pass
        else:
            raise Exception('internal card_type error')
        self._recv_pkt()
        val1 = ord(self.recv_buffer[2])
        val2 = ord(self.recv_buffer[3])
        return val1, val2

    ############################################################
    # Private functions
    ############################################################

    def _debug(self, *args):
        if DEBUG:
            print 'DEBUG:', args

    def _dump_pkt(self, pkt):
        res = []
        for i in range(0, 8):
            res.append('{0:02x}'.format(ord(pkt[i])))
        return ' '.join(res)

    def _recv_pkt(self):
        rc = usb.interrupt_read(self.libusb_handle, 0x81, self.recv_buffer, 0)
        if rc != len(self.recv_buffer):
            raise RuntimeError(
                    'interrupt_read() returned {0} - expected {1}'.format(
                    rc, len(self.recv_buffer)))
        self._debug('RECV:', self._dump_pkt(self.recv_buffer))

    def _send_pkt(self):
        self._debug('SEND:', self._dump_pkt(self.send_buffer))
        rc = usb.interrupt_write(self.libusb_handle, 0x81, self.send_buffer, 0)
        if rc != len(self.recv_buffer):
            raise RuntimeError(
                    'interrupt_write() returned {0} - expected {1}'.format(
                    rc, len(self.recv_buffer)))


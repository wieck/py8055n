#!/usr/bin/env python
"""
example.py - Velleman K8055(N)/VM110(N) example program.
"""

import sys
import py8055n
        
def main(argv):
    try:
        card = py8055n.py8055n(0)
    except Exception as err:
        sys.stderr.write(str(err) + '\n')
        return 1

    print 'CARD_0 opened'
    print 'DIGITAL_OUT:', card.readback_digital_all()
    print 'ANALOG_OUT:', card.readback_analog_all()
    print 'IN_1:', card.read_digital_port(0)
    print 'A_1:', card.read_analog_port(0)

    card.set_digital_all(0x54)
    card.set_digital_port(0, True)
    card.set_counter_debounce_time(0, 1)
    card.set_counter_debounce_time(1, 1)
    cur_d = -1
    cur_c1 = -1
    cur_c2 = -1
    cur_a1 = -1
    cur_a2 = -1

    print ''
    print '===================='
    print 'press digital input 5 to end example'
    print '===================='
    print ''
    while True:
        new_d = card.read_digital_all()
        if new_d != cur_d:
            cur_d = new_d
            print 'DIGITAL:', new_d
        new_c1 = card.read_counter(0)
        if new_c1 != cur_c1:
            cur_c1 = new_c1
            print 'COUNTER_1:', new_c1
        new_c2 = card.read_counter16(1)
        if new_c2 != cur_c2:
            cur_c2 = new_c2
            print 'COUNTER_2:', new_c2
        new_a1, new_a2 = card.read_analog_all()
        if new_a1 != cur_a1:
            cur_a1 = new_a1
            print 'ANALOG_1:', new_a1
        if new_a2 != cur_a2:
            cur_a2 = new_a2
            print 'ANALOG_2:', new_a2
        card.set_analog_all(new_a1, new_a2)
        if (new_d & 0x10) != 0:
            break
    card.set_digital_all(0x00)
    card.set_analog_all(0, 0)
    card.close()

if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))


from escpos.printer import Serial
def init_printer():
    return Serial(devfile='/dev/ttyS0', baudrate=9600, bytesize=8, parity='N', stopbits=1, timeout=1.00, dsrdtr=True)
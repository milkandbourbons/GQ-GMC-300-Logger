#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import serial
import serial.tools.list_ports
import threading
import time
import csv
from datetime import datetime
import struct

# Set this flag to True to see debug messages.
DEBUG = False

def convert_cpm_to_usvh(cpm):
    return cpm * 0.0065

CSV_FILENAME = "geiger_log.csv"
GPS_COORDS = "53.4096, -2.5737"

# Global lock for thread-safe serial writes
serial_lock = threading.Lock()
# Global variable for the latest battery voltage
last_batt_voltage = None

def initialize_csv(filename):
    try:
        with open(filename, 'x', newline='') as csvfile:
            writer = csv.writer(csvfile)
            # CSV header includes Battery Voltage, Device Serial, and Device Version.
            writer.writerow(["Timestamp", "CPM", "uSv/h", "Battery Voltage", "GPS", "Device Serial", "Device Version"])
    except FileExistsError:
        pass

def log_data(filename, timestamp, cpm, usvh, batt_voltage, device_serial, device_version):
    # If batt_voltage is a number, format it; otherwise, log as blank.
    if isinstance(batt_voltage, (int, float)):
        batt_str = f"{batt_voltage:.2f}"
    else:
        batt_str = ""
    with open(filename, 'a', newline='') as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow([timestamp.isoformat(), cpm, usvh, batt_str, GPS_COORDS, device_serial, device_version])
    # (Debug) if DEBUG: print(f"Logged: {timestamp.isoformat()}, CPM: {cpm}, uSv/h: {usvh:.2f}, Batt: {batt_str} V, Serial: {device_serial}, Version: {device_version}")

def get_serial_port():
    ports = serial.tools.list_ports.comports()
    if ports:
        return ports[0].device
    return None

def get_device_version(ser):
    with serial_lock:
        ser.write(b'\r\n')
        time.sleep(0.2)
        ser.write(b'<GETVER>>')
    time.sleep(0.5)
    version = ser.readline().decode('utf-8', errors='replace').strip()
    return version

def get_device_serial_number(ser):
    with serial_lock:
        ser.write(b'<GETSERIAL>>')
    time.sleep(0.5)
    data = ser.read(7)
    if len(data) == 7:
        serial_str = ''.join(f"{byte:02X}" for byte in data)
        return serial_str
    return "Unknown"

def set_device_datetime(ser):
    now = datetime.now()
    YY = f"{now.year % 100:02X}"
    MM = f"{now.month:02X}"
    DD = f"{now.day:02X}"
    hh = f"{now.hour:02X}"
    mm = f"{now.minute:02X}"
    ss = f"{now.second:02X}"
    cmd = f"<SETDATETIME{YY}{MM}{DD}{hh}{mm}{ss}>>"
    with serial_lock:
        ser.write(cmd.encode())
    if DEBUG:
        print(f"Set device datetime with command: {cmd}")

def sync_time_loop(ser):
    while ser.is_open:
        set_device_datetime(ser)
        time.sleep(1800)  # Sync every 30 minutes

def read_battery_voltage_loop(ser):
    global last_batt_voltage
    while ser.is_open:
        try:
            ser.reset_input_buffer()
            with serial_lock:
                ser.write(b'<GETVOLT>>')
            time.sleep(0.5)
            response = ser.read(1)
            if len(response) == 1:
                voltage = response[0] / 10.0
                if voltage > 5.0:
                    if DEBUG:
                        print(f"Invalid battery voltage reading: {voltage:.2f} V; ignoring.")
                else:
                    last_batt_voltage = voltage
                    if DEBUG:
                        print(f"Battery Voltage: {voltage:.2f} V")
            else:
                if DEBUG:
                    print("Incomplete battery voltage data")
        except Exception as e:
            print("Error in battery voltage loop:", e)
        time.sleep(60)  # Poll every 60 seconds

def read_cpm_loop(ser, device_serial, device_version):
    while ser.is_open:
        try:
            ser.reset_input_buffer()
            with serial_lock:
                ser.write(b'<GETCPM>>')
            time.sleep(2)
            response = ser.read_all()
            if DEBUG:
                print(f"[CPM Raw bytes]: {response}")
            if response:
                if len(response) >= 2:
                    valid_response = response[:2]
                    cpm_value = int.from_bytes(valid_response, byteorder='big') & 0x3FFF
                    usvh = convert_cpm_to_usvh(cpm_value)
                    timestamp = datetime.now()
                    batt_voltage = last_batt_voltage if last_batt_voltage is not None else ""
                    log_data(CSV_FILENAME, timestamp, cpm_value, round(usvh, 2), batt_voltage, device_serial, device_version)
                elif len(response) == 1:
                    if response == b'\xaa':
                        if DEBUG:
                            print("Ignoring marker byte 0xAA")
                    else:
                        if DEBUG:
                            print("Unexpected 1-byte response:", response)
            else:
                if DEBUG:
                    print("No CPM data received")
        except Exception as e:
            print("Error in CPM loop:", e)
            break
        time.sleep(4)  # Poll every 4 seconds

def main():
    initialize_csv(CSV_FILENAME)
    port = get_serial_port()
    if port is None:
        print("No serial port found. Ensure the device is connected.")
        return
    try:
        ser = serial.Serial(port, 57600, timeout=1,
                            parity=serial.PARITY_NONE,
                            bytesize=serial.EIGHTBITS,
                            stopbits=serial.STOPBITS_ONE)
        time.sleep(2)
        device_version = get_device_version(ser)
        device_serial = get_device_serial_number(ser)

        # Start automatic time synchronization thread
        threading.Thread(target=sync_time_loop, args=(ser,), daemon=True).start()
        # Start battery voltage polling thread
        threading.Thread(target=read_battery_voltage_loop, args=(ser,), daemon=True).start()
        # Start CPM reading loop thread
        threading.Thread(target=read_cpm_loop, args=(ser, device_serial, device_version), daemon=True).start()

        # Keep the main thread alive indefinitely.
        while True:
            time.sleep(1)
    except Exception as e:
        print("Error connecting to serial port:", e)

if __name__ == "__main__":
    main()
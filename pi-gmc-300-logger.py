#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import serial
import serial.tools.list_ports
import threading
import time
import csv
from datetime import datetime
import struct

# Conversion factor for CPM to µSv/h
def convert_cpm_to_usvh(cpm):
    return cpm * 0.0065

CSV_FILENAME = "geiger_log.csv"
GPS_COORDS = "53.4096, -2.5737"

# Global lock for thread-safe serial writes
serial_lock = threading.Lock()
# Global variable for the latest battery voltage (default to 0.0)
last_batt_voltage = 0.0

def initialize_csv(filename):
    try:
        with open(filename, 'x', newline='') as csvfile:
            writer = csv.writer(csvfile)
            # CSV header includes Battery Voltage, Device Serial, and Device Version.
            writer.writerow(["Timestamp", "CPM", "uSv/h", "Battery Voltage", "GPS", "Device Serial", "Device Version"])
    except FileExistsError:
        pass

def log_data(filename, timestamp, cpm, usvh, batt_voltage, device_serial, device_version):
    # If batt_voltage is not a number, default to 0.0.
    if not isinstance(batt_voltage, (int, float)):
        batt_voltage = 0.0
    batt_str = f"{batt_voltage:.2f}"
    with open(filename, 'a', newline='') as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow([timestamp.isoformat(), cpm, usvh, batt_str, GPS_COORDS, device_serial, device_version])
    # Minimal terminal output for logging; remove or comment out the next line if desired.
    # print(f"Logged: {timestamp.isoformat()}, CPM: {cpm}, uSv/h: {usvh:.2f}, Batt: {batt_str} V, Serial: {device_serial}, Version: {device_version}")

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
    print(f"Set device datetime with command: {cmd}")

def sync_time_loop(ser):
    while ser.is_open:
        set_device_datetime(ser)
        time.sleep(1800)  # 30 minutes

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
                # For a LiPo AAA cell, expect voltage below 5V.
                if voltage > 5.0:
                    print(f"Invalid battery voltage reading: {voltage:.2f} V; setting to 0.0 V.")
                    last_batt_voltage = 0.0
                else:
                    last_batt_voltage = voltage
                    # Uncomment next line for debug: print(f"Battery Voltage: {voltage:.2f} V")
            else:
                print("Incomplete battery voltage data; setting battery voltage to 0.0 V.")
                last_batt_voltage = 0.0
        except Exception as e:
            print("Error in battery voltage loop:", e)
            last_batt_voltage = 0.0
        time.sleep(60)  # Poll battery voltage every 60 seconds

def read_cpm_loop(ser, device_serial, device_version):
    while ser.is_open:
        try:
            ser.reset_input_buffer()
            with serial_lock:
                ser.write(b'<GETCPM>>')
            time.sleep(2)
            # Try to read exactly 2 bytes (or 3 if an extra marker is present)
            response = ser.read(2)
            if len(response) < 2:
                extra = ser.read(1)
                response += extra
            print(f"[CPM Raw bytes]: {response}")
            if response:
                if len(response) >= 2:
                    valid_response = response[:2]
                    cpm_value = int.from_bytes(valid_response, byteorder='big') & 0x3FFF
                    usvh = convert_cpm_to_usvh(cpm_value)
                    timestamp = datetime.now()
                    batt_voltage = last_batt_voltage if last_batt_voltage is not None else 0.0
                    log_data(CSV_FILENAME, timestamp, cpm_value, round(usvh, 2), batt_voltage, device_serial, device_version)
                elif len(response) == 1:
                    if response == b'\xaa':
                        print("Ignoring marker byte 0xAA")
                    else:
                        print("Unexpected 1-byte response:", response)
            else:
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
    print(f"Using serial port: {port}")
    try:
        ser = serial.Serial(port, 57600, timeout=1,
                            parity=serial.PARITY_NONE,
                            bytesize=serial.EIGHTBITS,
                            stopbits=serial.STOPBITS_ONE)
        time.sleep(2)
        print(f"Connected to {port}")

        device_version = get_device_version(ser)
        print(f"Device version: {device_version}")
        device_serial = get_device_serial_number(ser)
        print(f"Device serial number: {device_serial}")

        threading.Thread(target=sync_time_loop, args=(ser,), daemon=True).start()
        threading.Thread(target=read_battery_voltage_loop, args=(ser,), daemon=True).start()
        threading.Thread(target=read_cpm_loop, args=(ser, device_serial, device_version), daemon=True).start()

        while True:
            time.sleep(1)
    except Exception as e:
        print("Error connecting to serial port:", e)

if __name__ == "__main__":
    main()

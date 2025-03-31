# GQ-GMC 300E+ Logger

A Python-based logging solution for the GQ Electronics GMC-300 Geiger-Muller Counter. This headless script is designed for continuous, long-term logging (for example, on a Raspberry Pi) and writes data to a CSV file.
Tested on GMC-300E+V4 (V4.81) - others may work but untested.

## Future Development
Plan to move from CSV to some flavour of database and perhaps a Grafana dashboad.

## Features

### Auto-detection and Connection
The script automatically detects the first available serial port and connects to the device.

### Cross-Platform
Runs on Windows as well as *nix Kernels. Lightweight. 1 year of one per 4 sec logging generates ~550Mb CSV.

### Device Identification
Retrieves the device version using `<GETVER>>` and the device serial number using `<GETSERIAL>>`. These values are logged with every record.

### Continuous CPM Logging
Every 4 seconds, the script polls the device for counts per minute (CPM) using the `<GETCPM>>` command. The first two bytes of the response (after masking off the highest two bits) are used as the valid CPM value.

### µSv/h Calculation
CPM is converted to µSv/h using a conversion factor of 0.0065 µSv/h per CPM.

### Battery Voltage Monitoring
Every 60 seconds, the script polls for battery voltage using `<GETVOLT>>`. The device returns one byte which is divided by 10.0. If the voltage is above 5.0 V (an implausible value for a single LiPo cell), it is treated as an error and set to 0.0 V.

### Automatic Time Synchronization
The device’s internal clock is synchronized every 30 minutes using the `<SETDATETIME[YY][MM][DD][hh][mm][ss]>>` command (all fields are sent as two-digit hexadecimal values).

### Data Logging
Each CSV log entry includes:
- Timestamp (ISO formatted)
- CPM (counts per minute)
- µSv/h (converted value)
- Battery Voltage (in volts; if invalid, logged as 0.0 V)
- GPS Coordinates (a constant value)
- Device Serial Number
- Device Version

### Thread-safe Communication
A global serial lock ensures that commands are sent without collision.

## Requirements

- Python 3.x
- `pyserial`

Install via pip:

```bash
pip install pyserial
```

## Installation & Setup

### Clone the Repository

```bash
git clone https://github.com/milkandbourbons/GQ-GMC-300-Logger.git
cd GQ-GMC-300-Logger
```

### Ensure the Device is Connected
Connect your GQ Electronics GMC-300 Geiger-Muller Counter (via a USB-to-Serial adapter if necessary).

### Configure (Optional)
The GPS coordinates are set as a constant in the code. Update the `GPS_COORDS` variable if needed.

## Running the Script

Run the script with Python 3:

```bash
python3 your_script_name.py
```

The script will:
- Auto-detect the serial port.
- Retrieve and store the device version and serial number.
- Start synchronizing the device time every 30 minutes.
- Poll and log battery voltage every 60 seconds and CPM data every 4 seconds.
- Append all data to `geiger_log.csv`.

## CSV File Format

If the CSV file does not already exist, it will be created with the following header:

```csv
Timestamp, CPM, uSv/h, Battery Voltage, GPS, Device Serial, Device Version
```

Each subsequent row logs the data as described above.

## Minimizing SD Card I/O

This script minimizes write operations by logging each measurement directly to a CSV file. For even less frequent disk writes, consider buffering entries in memory and writing them in batches.

## Troubleshooting

### Serial Port Not Found
Ensure your device is connected and that your user has permissions to access the serial port (on Linux, you might need to add your user to the `dialout` group).

### Battery Voltage Readings
If you see a reading above 5.0 V, the script ignores it and logs 0.0 V instead.

### Hanging on Read Operations
If the script hangs when reading data, adjust the sleep durations after sending commands. The current settings have been tuned for many devices but may require tweaking for your specific setup.

## License

This project is provided under the GNU General Public License (GPL). Feel free to use, modify, and distribute the code as needed.

## Acknowledgments

This software was developed to log data from the GQ Electronics GMC-300 Geiger-Muller Counter. Special thanks to the community and contributors for their help and feedback.

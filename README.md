# Windows DHCP Web

A small Flask-based web interface for viewing and managing DHCP data on a Windows DHCP server.

## Overview

This project provides a lightweight web UI to interact with a Windows DHCP server.
It was built for homelab and small environments to simplify access to DHCP information without using the Windows MMC.

The application runs locally and is intended to be used behind a reverse proxy.

---

## Features

* View active DHCP leases
* Filter leases by hostname, MAC address, or IP
* Display current DHCP log files
* Track "seen devices" over time
* Create DHCP reservations via PowerShell
* Simple web interface
* Works behind reverse proxy (tested with subpath setup)

---

## Requirements

* Windows Server with DHCP role installed
* PowerShell
* Python 3.x

Python packages:

* flask
* flask-caching
* waitress
* werkzeug

---

## Configuration

The following variables must be adjusted in the script to match your environment:

* `LOG_DIR` → Path to DHCP log directory
* `APP_LOG_FILE` → Path for application log file
* `HOST` → Bind address (default: 127.0.0.1)
* `PORT` → Port (default: 6780)
* `APPLICATION_ROOT` → Subpath (e.g. `/dhcp`)
* `SEEN_DEVICES_FILE` → JSON file for device tracking

---

## Usage

1. Install dependencies:

   ```bash
   pip install flask flask-caching waitress werkzeug
   ```

2. Adjust configuration values in the script

3. Run the application:

   ```bash
   python windows_dhcp_web.py
   ```

4. Access via browser:

   ```
   http://localhost:6780/dhcp
   ```

---

## Compatibility

This tool was developed and tested on:

* Windows Server 2016
* German (DE) system locale

### Important

The application reads DHCP log files based on their default naming and format.

On non-German systems (e.g. English installations):

* DHCP log file names may differ
* Log file formats or field names may vary

As a result, the log parsing functionality may not work correctly without adjustments.

Tested with German DHCP log naming (e.g. `DhcpSrvLog-*.log`).

### Recommendation

If you are using a non-German system:

* Verify DHCP log file naming conventions
* Adjust parsing logic in the script if needed

---

## Security Notice

This project is **not a hardened production-ready application**.

* No authentication is implemented in the app itself
* Intended to run behind a reverse proxy with authentication
* Should not be exposed directly to the internet

---

## Notes

* Developed and tested in a personal homelab environment
* Uses PowerShell commands to interact with DHCP
* Requires appropriate permissions to read and modify DHCP data
* Error handling and edge cases are limited

---

## Limitations

* No user management
* No role-based access control
* Limited input validation
* Not designed for large-scale environments

---

## License

This project is provided as-is without any warranty.

---

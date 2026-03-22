# -*- coding: cp1252 -*-
import logging
from logging.handlers import TimedRotatingFileHandler
from flask import Flask, request, render_template, redirect, Response, url_for
from flask_caching import Cache
import subprocess, json, os, re, ipaddress
from werkzeug.middleware.proxy_fix import ProxyFix
from waitress import serve
from datetime import datetime

# -------------------- Konfigurierbare Pfade --------------------
LOG_DIR = r"C:\Windows\System32\dhcp"
APP_LOG_FILE = r"X:\logs\dhcp\webapp.log"
HOST = "127.0.0.1"
PORT = 6780
APPLICATION_ROOT = "/dhcp"
SEEN_DEVICES_FILE = "data/seen_devices.json"

# --------------- Logging Setup ------------------
logger = logging.getLogger('dhcp_webapp')
logger.setLevel(logging.DEBUG)
file_handler = TimedRotatingFileHandler(APP_LOG_FILE, when='midnight', interval=1, backupCount=7, encoding='utf-8', utc=False)
file_formatter = logging.Formatter('%(asctime)s %(levelname)s: %(message)s')
file_handler.setFormatter(file_formatter)
logger.addHandler(file_handler)
console_handler = logging.StreamHandler()
console_handler.setFormatter(file_formatter)
logger.addHandler(console_handler)

# Flask-App initialisieren
app = Flask(__name__)
cache = Cache(app, config={'CACHE_TYPE': 'SimpleCache'})
app.config['APPLICATION_ROOT'] = APPLICATION_ROOT
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_prefix=1)

lease_cache = []
last_update = None
last_renew_map = {}
log_cache = {"mtime": None, "content": ""}

# -------------------- Hilfsfunktionen --------------------
def get_log_file_for_today():
    """
    Liefert die DhcpSrvLog-Datei für den aktuellen Wochentag (IPv4).
    Fällt zurück auf die neueste vorhandene Datei, wenn heute keine vorhanden ist.
    """
    if not os.path.isdir(LOG_DIR):
        logger.warning(f"LOG_DIR {LOG_DIR} existiert nicht.")
        return None

    # Nur IPv4-Logs berücksichtigen, IPv6 ausschließen
    files = [f for f in os.listdir(LOG_DIR) if f.startswith("DhcpSrvLog-") and not f.startswith("DhcpV6SrvLog")]
    if not files:
        logger.warning("Keine IPv4 DhcpSrvLog-Dateien gefunden.")
        return None

    # Wochentagsnamen
    weekday_map = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"]
    today_str = weekday_map[datetime.today().weekday()]

    # passende Datei suchen
    today_file = next((os.path.join(LOG_DIR, f) for f in files if f"DhcpSrvLog-{today_str}" in f), None)

    if today_file:
        logger.debug(f"Logdatei für heute gefunden: {today_file}")
        return today_file
    else:
        # fallback auf die neueste vorhandene Datei
        files.sort(key=lambda f: os.path.getmtime(os.path.join(LOG_DIR, f)), reverse=True)
        fallback_file = os.path.join(LOG_DIR, files[0])
        logger.warning(f"Keine Logdatei von heute gefunden, verwende neueste vorhandene Datei: {fallback_file}")
        return fallback_file


def parse_dotnet_date(s):
    if not s or not isinstance(s, str): return ""
    m = re.match(r"^/Date\((\d+)\)/$", s)
    if not m: return s
    try:
        ts = int(m.group(1)) / 1000
        return datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S")
    except Exception as e:
        logger.error(f"Fehler beim Parsen des Datums {s}: {e}")
        return s

def parse_dhcp_logs():
    global last_renew_map
    newest = get_log_file_for_today()
    if not newest:
        last_renew_map = {}
        return
    temp_map = {}
    try:
        with open(newest, encoding="utf-8", errors="ignore") as f:
            for line in f:
                if "Erneuern" not in line:
                    continue
                parts = line.strip().split(",")
                if len(parts) < 5:
                    continue
                ip = parts[4].strip()
                mm, dd, yy = parts[1].split("/")
                hh_mm_ss = parts[2]
                ts = f"20{yy}-{mm.zfill(2)}-{dd.zfill(2)} {hh_mm_ss}"
                temp_map[ip] = ts
        last_renew_map = temp_map
        logger.debug(f"last_renew_map aktualisiert mit {len(temp_map)} Einträgen")
    except Exception as e:
        logger.error(f"Fehler beim Lesen der Logdatei {newest}: {e}")
        last_renew_map = {}

def load_seen_devices():
    if not os.path.exists(SEEN_DEVICES_FILE):
        return []

    with open(SEEN_DEVICES_FILE, "r", encoding="utf-8") as f:
        devices = json.load(f)

    now_iso = datetime.now().isoformat(timespec='seconds')

    # Beispiel: Aktualisiere last_seen, wenn du gerade DHCP-Leases durchgehst
    for device in devices:
        device.setdefault("last_seen", device.get("first_seen", now_iso))
    return devices
	
def update_seen_device(mac, ip, hostname):
    devices = load_seen_devices()
    now_iso = datetime.now().isoformat(timespec='seconds')

    # Prüfen, ob Gerät bereits bekannt
    for device in devices:
        if device["mac"].lower() == mac.lower():
            device["ip"] = ip
            device["hostname"] = hostname
            device["last_seen"] = now_iso
            break
    else:
        # Neues Gerät
        devices.append({
            "mac": mac,
            "ip": ip,
            "hostname": hostname,
            "first_seen": now_iso,
            "last_seen": now_iso
        })

    # Speichern
    with open(SEEN_DEVICES_FILE, "w", encoding="utf-8") as f:
        json.dump(devices, f, indent=2)

def save_seen_devices(devices):
    """Speichert bekannte Geräte in JSON-Datei"""
    with open(SEEN_DEVICES_FILE, "w", encoding="utf-8") as f:
        json.dump(devices, f, indent=2, ensure_ascii=False)

def add_seen_device(mac, ip, hostname):
    """Fügt Gerät hinzu, falls noch nicht vorhanden"""
    devices = load_seen_devices()
    if not any(d["mac"] == mac for d in devices):
        devices.append({
            "mac": mac,
            "ip": ip,
            "hostname": hostname,
            "first_seen": datetime.now().isoformat()
        })
        save_seen_devices(devices)

def update_leases():
    global lease_cache, last_update
    parse_dhcp_logs()
    ps_cmd = """
    Get-DhcpServerv4Scope | ForEach-Object { Get-DhcpServerv4Lease -ScopeId $_.ScopeId } | ConvertTo-Json -Depth 3
    """
    try:
        logger.info("Aktualisiere DHCP-Leases via PowerShell")
        output = subprocess.check_output(
            ['powershell', '-Command', ps_cmd],
            text=True,
            creationflags=subprocess.CREATE_NO_WINDOW  # <- Fensterlos
        )
        new_leases = json.loads(output)
        if isinstance(new_leases, dict): new_leases = [new_leases]
        refreshed = []
        for l in new_leases:
            ip_str = l.get("IPAddressToString") or l.get("IPAddress", {}).get("IPAddressToString", "")
            l["_IP"] = ip_str
            lease_expiry = l.get("LeaseExpiryTime") or l.get("LeaseExpires")
            lease_expiry_val = parse_dotnet_date(lease_expiry) if lease_expiry else "static"
            last_renew_val = last_renew_map.get(ip_str, "-")
            l["LeaseExpiryTime"] = lease_expiry_val
            l["LastRenew"] = last_renew_val
            refreshed.append(l)

            hostname = l.get("HostName", "")
            clientid = l.get("ClientId", "")
            add_seen_device(clientid, ip_str, hostname)
        lease_cache.clear()
        lease_cache.extend(refreshed)
        last_update = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        logger.info(f"Leases aktualisiert: {len(refreshed)} Einträge, Zeit: {last_update}")
    except Exception as e:
        logger.error(f"Fehler bei Lease-Aktualisierung: {e}")

def get_current_log():
    newest = get_log_file_for_today()
    if not newest:
        return "Keine Logs gefunden"
    mtime = os.path.getmtime(newest)
    if log_cache["mtime"] != mtime:
        try:
            with open(newest, encoding="utf-8", errors="ignore") as f:
                log_cache["content"] = f.read()
            log_cache["mtime"] = mtime
        except Exception as e:
            logger.error(f"Fehler beim Lesen der Logdatei: {e}")
            return "Fehler beim Lesen der Logdatei"
    return log_cache["content"]

# ------------------------- ROUTES -------------------------
@app.route("/", methods=["GET"])
def leases():
    host_filter = request.args.get("host", "").lower()
    mac_filter = request.args.get("mac", "").lower()
    ip_filter = request.args.get("ip", "")
    filtered = []
    for l in lease_cache:
        hostname = l.get("HostName")
        if host_filter and (not isinstance(hostname, str) or host_filter not in hostname.lower()):
            continue
        clientid = l.get("ClientId", "")
        if mac_filter and mac_filter not in clientid.lower():
            continue
        if ip_filter and ip_filter not in l.get("_IP", ""):
            continue
        filtered.append(l)
    return render_template("leases.html", leases=filtered, request=request, last_update=last_update,
                           error_message="", prefill_mac="", prefill_ip="", prefill_hostname="")

@app.route("/refresh")
def refresh():
    update_leases()
    return redirect(url_for('leases'))

@app.route("/add_reservation", methods=["POST"])
def add_reservation():
    mac = request.form["mac"].strip()
    ip = request.form["ip"].strip()
    hostname = request.form["hostname"].strip()
    mac_ok = re.fullmatch(r"^[0-9A-Fa-f]{2}([-:][0-9A-Fa-f]{2}){5}$", mac)
    try:
        ip_obj = ipaddress.ip_address(ip)
    except ValueError:
        ip_obj = None
    error_message = None
    if not mac_ok or not ip_obj:
        error_message = "Ungültige IP- oder MAC-Adresse."
    else:
        exists = any(l["_IP"] == ip or l.get("ClientId", "").lower() == mac.lower() for l in lease_cache)
        if exists:
            error_message = f"Reservierung mit IP {ip} oder MAC {mac} existiert bereits."
    if error_message:
        update_leases()
        filtered = lease_cache
        return render_template("leases.html", leases=filtered, request=request, last_update=last_update,
                               error_message=error_message, prefill_mac=mac, prefill_ip=ip, prefill_hostname=hostname)
    scope = ".".join(ip.split(".")[:3]) + ".0"
    ps_cmd = ["Add-DhcpServerv4Reservation", "-ScopeId", scope, "-IPAddress", ip, "-ClientId", mac, "-Name", hostname]
    try:
        result = subprocess.run(
            ["powershell", "-NoProfile", "-Command"] + ps_cmd,
            capture_output=True,
            text=True,
            creationflags=subprocess.CREATE_NO_WINDOW  # <- Fensterlos
        )
        if result.returncode == 0:
            return redirect(url_for('leases'))
        else:
            error_message = f"Fehler bei der Reservierung: {result.stderr.strip()}"
    except Exception as e:
        error_message = f"Unbekannter Fehler bei Reservation: {e}"

    update_leases()
    filtered = lease_cache
    return render_template("leases.html", leases=filtered, request=request, last_update=last_update,
                           error_message=error_message, prefill_mac=mac, prefill_ip=ip, prefill_hostname=hostname)

@app.route("/log")
def log():
    content = get_current_log()
    if not content.strip():
        return Response("Keine Log-Daten gefunden", mimetype="text/plain")
    lines = content.splitlines()
    header_idx = next((i for i, line in enumerate(lines) if line.startswith("ID,")), None)
    if header_idx is None:
        return Response("Keine Log-Daten gefunden", mimetype="text/plain")
    hints = lines[:header_idx]
    header = lines[header_idx].split(",")
    rows = [l.split(",") for l in lines[header_idx + 1:] if l.strip()]
    relevant_cols = ["ID", "Datum", "Zeit", "Beschreibung", "IP-Adresse", "Hostname", "MAC-Adresse", "DNS-Registrierungsfehler"]
    keep_idx = [header.index(c) for c in relevant_cols if c in header]
    filtered_header = [header[i] for i in keep_idx]
    filtered_rows = [[row[i] if i < len(row) else "" for i in keep_idx] for row in rows]
    return render_template("log.html", hints=hints, filtered_header=filtered_header, filtered_rows=filtered_rows)

@app.route("/logdatei")
def logdatei():
    content = get_current_log()
    return Response(content, mimetype="text/plain")

@app.route("/seen_devices")
def seen_devices():
    devices = load_seen_devices()
    show_static = request.args.get("show_static", "0") == "1"
    sort_order = request.args.get("sort", "desc")  # "desc" = neueste zuerst, "asc" = älteste zuerst

    if not show_static:
        devices = [d for d in devices if d.get("ip") != "static"]

    # Sortieren nach last_seen oder first_seen
    devices.sort(
        key=lambda d: d.get("last_seen") or d.get("first_seen"),
        reverse=(sort_order == "desc")
    )

    # Formatieren für Anzeige
    for device in devices:
        for key in ["first_seen", "last_seen"]:
            val = device.get(key)
            if val:
                try:
                    dt = datetime.fromisoformat(val)
                    device[key] = dt.strftime('%Y-%m-%d %H:%M:%S')
                except ValueError:
                    pass

    return render_template(
        "seen_devices.html",
        devices=devices,
        show_static=show_static,
        sort_order=sort_order
    )


# Flask-Debugserver
if __name__ == "__main__":
    update_leases()
    app.run(host=HOST, port=PORT, debug=True, use_reloader=False)

# Waitress Server	
#if __name__ == "__main__":
#    update_leases()
#    serve(app, host=HOST, port=PORT)

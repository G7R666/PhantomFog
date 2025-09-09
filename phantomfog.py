#!/usr/bin/env python3
"""
PhantomFog Advanced - Adaptive Network Fog & Monitoring
Features: Adaptive noise, dynamic targets, enhanced fingerprinting, web dashboard, logging.
AUTHORIZED TESTING ONLY.
"""

import threading, time, random, os, json, socket, hashlib
from datetime import datetime
from pathlib import Path

from flask import Flask, jsonify, render_template_string
from werkzeug.serving import make_server

try:
    from scapy.all import send, IP, UDP
except Exception:
    print("[!] scapy not installed. Install with: pip install scapy")
    exit(1)

# ---------- Configuration ----------
OUTPUT_DIR = Path("./phantomfog_output")
OUTPUT_DIR.mkdir(exist_ok=True)
LOG_FILE = OUTPUT_DIR / "fog_log.json"
FINGERPRINT_FILE = OUTPUT_DIR / "fingerprint.json"

BASE_RATE_PER_MIN = 6
MAX_RATE_PER_MIN = 200
ADAPT_MULTIPLIER = 5
DEFAULT_PORTS = [53, 80, 443, 8080]
RATE_CHECK_INTERVAL = 5
AUTH_LOG_PATHS = ["/var/log/auth.log", "/var/log/secure"]
PROTECTED_IPS = ["192.168.1.1", "10.0.0.1"]

state = {
    "targets": [],
    "rate_per_min": BASE_RATE_PER_MIN,
    "attack_score": 0,
    "failures": {},
    "running": True,
    "dry_run": False,
    "fingerprint": {}
}
state_lock = threading.Lock()

# ---------- Logging ----------
def log_event(event: dict):
    event["timestamp"] = datetime.utcnow().isoformat()
    print(json.dumps(event))
    try:
        with LOG_FILE.open("a") as f:
            f.write(json.dumps(event) + "\n")
    except Exception:
        pass

# ---------- Fingerprinting ----------
def fingerprint_system():
    fp = {}
    try:
        fp["hostname"] = socket.gethostname()
        fp["platform"] = os.uname().sysname if hasattr(os, "uname") else "unknown"
        fp["interfaces"] = []
        for iface in socket.if_nameindex():
            name = iface[1]
            try:
                mac = open(f"/sys/class/net/{name}/address").read().strip()
            except Exception:
                mac = None
            fp["interfaces"].append({"name": name, "mac": mac})
        fp["cpu_count"] = os.cpu_count()
    except Exception as e:
        fp["error"] = str(e)
    try:
        with FINGERPRINT_FILE.open("w") as f:
            json.dump(fp, f, indent=2)
    except Exception:
        pass
    return fp

# ---------- Adaptive Rate ----------
def adaptive_rate_manager():
    while state["running"]:
        with state_lock:
            attack = state["attack_score"]
            multiplier = 1 + min(ADAPT_MULTIPLIER, attack / 5.0)
            state["rate_per_min"] = min(MAX_RATE_PER_MIN, BASE_RATE_PER_MIN * multiplier)
            state["attack_score"] = max(0, attack - 1)
        log_event({"type":"rate_update","rate_per_min":state["rate_per_min"]})
        time.sleep(RATE_CHECK_INTERVAL)

# ---------- Noise Sender ----------
def noise_sender(target):
    while state["running"]:
        with state_lock:
            rpm = state["rate_per_min"]
            dry = state["dry_run"]
        if target in PROTECTED_IPS:
            time.sleep(1)
            continue
        interval = 60.0 / max(0.1,rpm)
        sleep_time = max(0.1, random.gauss(interval, interval*0.3))
        payload = hashlib.sha256(f"fog:{time.time()}:{random.randint(0,9999)}".encode()).hexdigest()[:64].encode()
        port = random.choice(DEFAULT_PORTS)
        if dry:
            log_event({"type":"dry_run","target":target,"port":port})
        else:
            try:
                pkt = IP(dst=target)/UDP(dport=port)/payload
                send(pkt,verbose=False)
                log_event({"type":"noise_sent","target":target,"port":port})
            except Exception as e:
                log_event({"type":"noise_error","error":str(e)})
        time.sleep(sleep_time)

# ---------- Web Dashboard ----------
app = Flask(__name__)
@app.route("/")
def index():
    with state_lock:
        data = {
            "targets": state["targets"],
            "rate_per_min": state["rate_per_min"],
            "attack_score": state["attack_score"],
            "failures": state["failures"]
        }
    template = """
    <h2>PhantomFog Dashboard</h2>
    <p>Rate per minute: {{rate_per_min}}</p>
    <p>Attack Score: {{attack_score}}</p>
    <p>Targets: {{targets}}</p>
    <p>Failures: {{failures}}</p>
    """
    return render_template_string(template, **data)

class WebServerThread(threading.Thread):
    def __init__(self):
        threading.Thread.__init__(self)
        self.srv = make_server("0.0.0.0", 5000, app)
        self.ctx = app.app_context()
        self.ctx.push()
    def run(self):
        self.srv.serve_forever()
    def shutdown(self):
        self.srv.shutdown()

# ---------- CLI ----------
def start_noise_threads(targets):
    threads = []
    for t in targets:
        thr = threading.Thread(target=noise_sender,args=(t,),daemon=True)
        thr.start()
        threads.append(thr)
    return threads

def run_cli(targets, dry_run=False):
    state["targets"]=targets
    state["dry_run"]=dry_run
    state["fingerprint"]=fingerprint_system()
    log_event({"type":"startup","targets":targets,"dry_run":dry_run})
    noise_threads = start_noise_threads(targets)
    web_thread = WebServerThread()
    web_thread.start()
    print("PhantomFog Advanced running. Web dashboard: http://localhost:5000")
    try:
        while True:
            cmd = input("Fog> ").strip().lower()
            if cmd in ("exit","stop"):
                with state_lock:
                    state["running"]=False
                break
            elif cmd=="status":
                with state_lock:
                    print(f"rate_per_min:{state['rate_per_min']}, attack_score:{state['attack_score']}")
            elif cmd=="targets":
                print("Targets:", state["targets"])
            elif cmd.startswith("add "):
                ip=cmd.split(" ",1)[1].strip()
                with state_lock:
                    if ip not in state["targets"]:
                        state["targets"].append(ip)
                        t=threading.Thread(target=noise_sender,args=(ip,),daemon=True)
                        t.start()
            elif cmd.startswith("remove "):
                ip=cmd.split(" ",1)[1].strip()
                with state_lock:
                    if ip in state["targets"]:
                        state["targets"].remove(ip)
            elif cmd=="failures":
                with state_lock:
                    print(state["failures"])
            else:
                print("Commands: status, targets, add <ip>, remove <ip>, failures, exit")
    except KeyboardInterrupt:
        with state_lock:
            state["running"]=False

if __name__ == "__main__":
    run_cli(targets=[])

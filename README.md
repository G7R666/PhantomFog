# PhantomFog -  Tool


## Features

- Adaptive network noise generation to mislead potential attackers.
- Monitors authentication logs for suspicious activity.
- 
- Minimal web dashboard for real-time monitoring.
- Safe and non-intrusive: does not modify or encrypt files.

---

## Installation

1. Clone the repository:

```bash
git clone https://github.com/G7R666/PhantomFog.git
cd PhantomFog



python3 -m venv .venv
source .venv/bin/activate

pip install -r requirements.txt
python3 phantomfog.py


Fog> status
Fog> targets
Fog> add 192.168.1.50
Fog> remove 192.168.1.50
Fog> failures
Fog> exit


Web Dashboard

Once running, open your browser at: http://localhost:5000

This dashboard shows:

Current noise rate per minute

Attack score

Active targets

Logged failures


Developer'abdalmohamen

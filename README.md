# Network Speed Test – README

Eine kleine Python‑Implementierung eines Netzwerk‑Speed‑Tests, ähnlich wie **iperf3**. Misst Durchsatz (Mbps) und – im UDP‑Modus – zudem Paketverlust, RTT und Jitter.

---

## Installation

Lade die Datei `speedtest.py` auf beide Rechner (Server und Client) und stelle sicher, dass Python 3.x installiert ist.

```bash
chmod +x speedtest.py   # optional: ausführbar machen
```

---

## Verwendung

Starte den Server in einem Terminal und den Client in einem anderen.

### TCP‑Test (Standard)

**Server**

```bash
python speedtest.py -s -p 5201 -t 10
```

**Client**

```bash
python speedtest.py -c <SERVER_IP> -p 5201 -t 10
```

### UDP‑Test

Füge dem Server und Client jeweils `-u` hinzu.

**Server**

```bash
python speedtest.py -s -u -p 5201 -t 10
```

**Client**

```bash
python speedtest.py -c <SERVER_IP> -u -p 5201 -t 10
```

---

## Optionen‑Übersicht

| Flag | Bedeutung | Standard |
|------|-----------|----------|
| `-s`, `--server` | Server‑Modus (auf dieses Rechner lauschen) | – |
| `-c`, `--client` | Client‑Modus (Verbindung zu Server herstellen) | – |
| `-p`, `--port` | Port‑Nummer für die Verbindung | `5201` |
| `-t`, `--time` | Testdauer in Sekunden | `10` |
| `-u`, `--udp` | UDP‑Modus statt TCP | TCP |
| `-h`, `--help` | Hilfe‑Anzeige | – |

---

## Beispiel‑Ausgabe (TCP)

```
[SERVER] Listening on 0.0.0.0:5201 for 10s

[SERVER] Connection from 127.0.0.1:59324

[SERVER] Received: 1250000 bytes

[SERVER] Duration: 10.00s
[SERVER] Bandwidth: 1.00 Mbps
```

Beispiel‑Ausgabe (UDP)

```
[UDP SERVER] Listening on 0.0.0.0:5201 for 10s

[UDP SERVER] Packets received: 120
[UDP SERVER] Duration: 10.00s
[UDP SERVER] Bandwidth: 2.88 Mbps

[UDP CLIENT] Packets sent: 125
[UDP CLIENT] Packet loss: 4
[UDP CLIENT] Average RTT: 1.23 ms
[UDP CLIENT] Jitter: 0.45 ms
[UDP CLIENT] Bandwidth: 2.88 Mbps
```

---

## Hinweise

- Stelle sicher, dass die Firewalls beider Rechner den gewählten Port (default 5201) freigeben.
- Die Standard‑IP für den Client ist `127.0.0.1` (localhost). Verwende die echte IP‑Adresse des Servers für Tests über ein Netzwerk.
- Die Bandbreiten‑Formel rechnet korrekt in **Mbps** (1 Mbps = 10⁶ bit/s).


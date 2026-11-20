# speedtest.py – Netzwerk-Speedtest (iperf3-ähnlich)

Kleiner Python-Speedtest für TCP und UDP. Server und Client sind im selben Skript.

## Schnellstart

**Server** (Terminal 1, läuft bis Ctrl+C):
```bash
python speedtest.py -s              # TCP
python speedtest.py -s -u           # UDP
```

**Client** (Terminal 2):
```bash
python speedtest.py -c 192.168.89.10              # TCP
python speedtest.py -c 192.168.89.10 -u -b 100    # UDP, Zielrate 100 Mbit/s
python speedtest.py -c 192.168.89.10 -t 30        # 30 s Testdauer
```

## Optionen

| Option | Bedeutung | Standard |
|---|---|---|
| `-s`, `--server` | Server-Modus (lauscht, läuft bis Ctrl+C) | – |
| `-c SERVER_IP` | Client-Modus, Ziel-IP (ohne Wert: `127.0.0.1`) | – |
| `-p PORT` | Port | `5201` |
| `-t SEKUNDEN` | Testdauer (nur Client) | `10` |
| `-u`, `--udp` | UDP statt TCP | TCP |
| `-b MBIT` | UDP-Zielrate in Mbit/s (`0` = unbegrenzt) | `0` |
| `-l BYTE` | UDP-Paketgröße | `1400` |
| `-h` / `-V` | Hilfe / Version | – |

## Ausgabe

* **TCP**: Dauer, gesendete Datenmenge, Durchsatz in Mbit/s (1-s-Intervalle + Summe).
* **UDP**: gesendete/empfangene Pakete, Durchsatz, **Paketverlust in %**, **Jitter in ms**
  (Verlust und Jitter werden serverseitig ermittelt und am Ende an den Client zurückgemeldet).

## Hinweise

* Server beenden: **Ctrl+C** – funktioniert jederzeit, auch während eines laufenden Tests.
* Firewall muss den Port (Standard 5201) auf dem Server-Rechner erlauben.
* UDP ohne `-b` sendet so schnell wie möglich (CPU/NIC-Limit); für reproduzierbare
  Messungen eine Zielrate setzen, z. B. `-b 100`.
* Der Server meldet beim Start alle lokalen IPv4-Adressen – praktisch, um die richtige
  IP für den Client zu finden.

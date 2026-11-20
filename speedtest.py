#!/usr/bin/env python3
"""
speedtest.py - kleiner iperf3-Klon (TCP + UDP)

Server starten:   python speedtest.py -s
TCP-Client:       python speedtest.py -c 192.168.89.10
UDP-Client:       python speedtest.py -c 192.168.89.10 -u -b 100
UDP-Server:       python speedtest.py -s -u

Server jederzeit mit Ctrl+C beenden.
"""

import argparse
import socket
import struct
import sys
import time

VERSION = "2.0"
DEFAULT_PORT = 5201
DEFAULT_TIME = 10.0
DEFAULT_PACKET_LEN = 1400
DEFAULT_BITRATE = 0.0        # Mbit/s, 0 = so schnell wie moeglich
IDLE_TIMEOUT = 2.0           # Sekunden ohne Daten -> Test beendet
POLL_TIMEOUT = 0.5           # Socket-Timeout -> Ctrl+C wirkt sofort
BUFSIZE = 65536

UDP_HDR = struct.Struct("!Id")        # Sequenznummer + Sendezeitstempel
UDP_REPLY = struct.Struct("!QQId")    # Pakete (Q), Bytes (Q), max. Seq (I), Jitter ms (d)
UDP_END_SEQ = 0xFFFFFFFF

CHUNK = b"\x00" * BUFSIZE


# ---------------------------------------------------------------- Helpers
def bytes_to_mbps(num_bytes, seconds):
    if seconds <= 0:
        return 0.0
    return num_bytes * 8 / seconds / 1_000_000.0


def human_bytes(num_bytes):
    value = float(num_bytes)
    for unit in ("B", "KiB", "MiB", "GiB", "TiB"):
        if value < 1024.0 or unit == "TiB":
            return f"{value:.2f} {unit}"
        value /= 1024.0
    return f"{value:.2f} TiB"


class JitterTracker:
    """Jitter nach RFC 3550 (gleitender Mittelwert)."""

    def __init__(self):
        self._prev = None
        self.value = 0.0

    def update(self, transit):
        if self._prev is not None:
            delta = abs(transit - self._prev)
            self.value += (delta - self.value) / 16.0
        self._prev = transit


def local_ips():
    ips = set()
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            ips.add(info[4][0])
    except OSError:
        pass
    try:
        probe = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            probe.connect(("8.8.8.8", 80))
            ips.add(probe.getsockname()[0])
        finally:
            probe.close()
    except OSError:
        pass
    return sorted(ip for ip in ips if not ip.startswith("127."))


def bind_or_die(sock, host, port, proto):
    try:
        sock.bind((host, port))
    except OSError as exc:
        print(f"[{proto} SERVER] Fehler: Port {port} nicht belegbar: {exc}", file=sys.stderr)
        raise SystemExit(1)


def print_server_banner(proto, host, port):
    print(f"[{proto} SERVER] lauscht auf {host}:{port}")
    for ip in local_ips():
        print(f"[{proto} SERVER] erreichbar unter {ip}:{port}")
    print(f"[{proto} SERVER] Beenden mit Ctrl+C "
          f"(die Testdauer -t bestimmt der Client)\n")


# ---------------------------------------------------------------- UDP
class UdpSession:
    def __init__(self, addr, now):
        self.addr = addr
        self.start = now
        self.last_seen = now
        self.last_report = now
        self.packets = 0
        self.nbytes = 0
        self.report_bytes = 0
        self.max_seq = -1
        self.jitter = JitterTracker()

    def add(self, seq, sent_ts, size, now):
        self.packets += 1
        self.nbytes += size
        self.report_bytes += size
        self.last_seen = now
        if seq > self.max_seq:
            self.max_seq = seq
        self.jitter.update(now - sent_ts)

    def summary(self, now):
        duration = max(now - self.start, 1e-9)
        expected = self.max_seq + 1
        lost = max(expected - self.packets, 0)
        loss_pct = 100.0 * lost / expected if expected else 0.0
        return {
            "duration": duration,
            "packets": self.packets,
            "bytes": self.nbytes,
            "mbps": bytes_to_mbps(self.nbytes, duration),
            "lost": lost,
            "loss_pct": loss_pct,
            "jitter_ms": self.jitter.value * 1000.0,
        }


def print_summary(label, addr, s):
    print(f"[{label}] Ergebnis von {addr[0]}:{addr[1]}")
    print(f"    Dauer .......... {s['duration']:.2f} s")
    print(f"    Empfangen ...... {s['packets']} Pakete / {human_bytes(s['bytes'])}")
    print(f"    Durchsatz ...... {s['mbps']:.2f} Mbit/s")
    print(f"    Verlust ........ {s['lost']} Pakete ({s['loss_pct']:.2f} %)")
    print(f"    Jitter ......... {s['jitter_ms']:.3f} ms")


def udp_server(host, port):
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    bind_or_die(sock, host, port, "UDP")
    sock.settimeout(POLL_TIMEOUT)          # <-- sorgt fuer zuverlaessiges Ctrl+C
    print_server_banner("UDP", host, port)

    sessions = {}
    try:
        while True:
            data = None
            try:
                data, addr = sock.recvfrom(BUFSIZE)
            except socket.timeout:
                pass                        # kein Datum: kurz Luft holen -> Ctrl+C

            now = time.time()

            if data is not None and len(data) >= UDP_HDR.size:
                seq, sent_ts = UDP_HDR.unpack_from(data)
                if seq == UDP_END_SEQ:
                    session = sessions.pop(addr, None)
                    if session is not None:
                        s = session.summary(session.last_seen)
                        print_summary("UDP SERVER", addr, s)
                        sock.sendto(
                            UDP_REPLY.pack(session.packets, session.nbytes,
                                           max(session.max_seq, 0), s["jitter_ms"]),
                            addr)
                else:
                    session = sessions.get(addr)
                    if session is None:
                        session = UdpSession(addr, now)
                        sessions[addr] = session
                        print(f"[UDP SERVER] neuer Client: {addr[0]}:{addr[1]}")
                    session.add(seq, sent_ts, len(data), now)

            for addr in list(sessions):
                s = sessions[addr]
                if now - s.last_report >= 1.0:
                    print(f"    {now - s.start:5.1f}s  "
                          f"{bytes_to_mbps(s.report_bytes, now - s.last_report):9.2f} Mbit/s")
                    s.report_bytes = 0
                    s.last_report = now
                if now - s.last_seen > IDLE_TIMEOUT:
                    print_summary("UDP SERVER", addr, s.summary(s.last_seen))
                    del sessions[addr]
    finally:
        sock.close()
        print("[UDP SERVER] Socket geschlossen.")


def udp_client(host, port, duration, packet_len, bitrate):
    payload = b"\x00" * max(packet_len - UDP_HDR.size, 0)
    pkt_size = UDP_HDR.size + len(payload)

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(POLL_TIMEOUT)

    interval = (pkt_size * 8) / (bitrate * 1e6) if bitrate > 0 else None
    start = time.time()
    deadline = start + duration
    next_send = start
    next_report = start + 1.0
    sent = 0
    sent_bytes = 0
    report_bytes = 0

    if interval:
        print(f"[UDP CLIENT] {host}:{port}  {duration:g}s  {pkt_size} B/Paket  "
              f"Zielrate {bitrate:g} Mbit/s")
    else:
        print(f"[UDP CLIENT] {host}:{port}  {duration:g}s  {pkt_size} B/Paket  "
              f"Rate unbegrenzt")

    reply = None
    try:
        while True:
            now = time.time()
            if now >= deadline:
                break
            if interval is not None and now < next_send:
                pause = min(next_send - now, deadline - now)
                if pause > 0:
                    time.sleep(pause)
                continue

            try:
                sock.sendto(UDP_HDR.pack(sent & 0xFFFFFFFE, now) + payload, (host, port))
            except OSError as exc:
                print(f"[UDP CLIENT] Senden fehlgeschlagen: {exc}", file=sys.stderr)
                break
            sent += 1
            sent_bytes += pkt_size
            report_bytes += pkt_size
            if interval is not None:
                next_send += interval

            now = time.time()
            if now >= next_report:
                print(f"    {now - start:5.1f}s  "
                      f"{bytes_to_mbps(report_bytes, now - (next_report - 1.0)):9.2f} Mbit/s")
                report_bytes = 0
                next_report += 1.0

        # Testende signalisieren und Statistik abholen
        try:
            sock.sendto(UDP_HDR.pack(UDP_END_SEQ, time.time()), (host, port))
            sock.settimeout(IDLE_TIMEOUT)
            wait_until = time.time() + IDLE_TIMEOUT
            while time.time() < wait_until:
                try:
                    data, _ = sock.recvfrom(1024)
                except socket.timeout:
                    break
                if len(data) == UDP_REPLY.size:
                    reply = UDP_REPLY.unpack(data)
                    break
        except OSError as exc:
            print(f"[UDP CLIENT] Kein Server-Report: {exc}", file=sys.stderr)
    finally:
        sock.close()

    elapsed = max(time.time() - start, 1e-9)
    print("\n[UDP CLIENT] Ergebnis")
    print(f"    Dauer .......... {elapsed:.2f} s")
    print(f"    Gesendet ....... {sent} Pakete / {human_bytes(sent_bytes)}")
    print(f"    Senderate ...... {bytes_to_mbps(sent_bytes, elapsed):.2f} Mbit/s")

    if reply is None:
        print("    Server-Report .. nicht erhalten")
        print("    -> Laeuft der Server mit -u? Ist der Port in der Firewall offen?")
        return

    packets, nbytes, max_seq, jitter_ms = reply
    expected = max_seq + 1
    lost = max(expected - packets, 0)
    loss_pct = 100.0 * lost / expected if expected else 0.0
    print(f"    Empfangen ...... {packets} Pakete / {human_bytes(nbytes)}")
    print(f"    Durchsatz ...... {bytes_to_mbps(nbytes, elapsed):.2f} Mbit/s")
    print(f"    Verlust ........ {lost} Pakete ({loss_pct:.2f} %)")
    print(f"    Jitter ......... {jitter_ms:.3f} ms")


# ---------------------------------------------------------------- TCP
def handle_tcp_conn(conn, addr):
    conn.settimeout(POLL_TIMEOUT)
    start = last_seen = last_report = time.time()
    total = 0
    report_bytes = 0

    while True:
        data = None
        try:
            data = conn.recv(BUFSIZE)
        except socket.timeout:
            if time.time() - last_seen > IDLE_TIMEOUT:
                break
        except OSError:
            break

        now = time.time()
        if data == b"":
            break
        if data:
            total += len(data)
            report_bytes += len(data)
            last_seen = now

        if now - last_report >= 1.0:
            print(f"    {now - start:5.1f}s  "
                  f"{bytes_to_mbps(report_bytes, now - last_report):9.2f} Mbit/s")
            report_bytes = 0
            last_report = now

    duration = max(time.time() - start, 1e-9)
    print(f"[TCP SERVER] Ergebnis von {addr[0]}:{addr[1]}")
    print(f"    Dauer .......... {duration:.2f} s")
    print(f"    Empfangen ...... {human_bytes(total)}")
    print(f"    Durchsatz ...... {bytes_to_mbps(total, duration):.2f} Mbit/s\n")


def tcp_server(host, port):
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    bind_or_die(srv, host, port, "TCP")
    srv.listen(1)
    srv.settimeout(POLL_TIMEOUT)        # <-- accept() pollt -> Ctrl+C wirkt sofort
    print_server_banner("TCP", host, port)

    try:
        while True:
            try:
                conn, addr = srv.accept()
            except socket.timeout:
                continue
            print(f"[TCP SERVER] Client verbunden: {addr[0]}:{addr[1]}")
            try:
                handle_tcp_conn(conn, addr)
            finally:
                conn.close()
    finally:
        srv.close()
        print("[TCP SERVER] Socket geschlossen.")


def tcp_client(host, port, duration):
    try:
        sock = socket.create_connection((host, port), timeout=5.0)
    except OSError as exc:
        print(f"[TCP CLIENT] Verbindung zu {host}:{port} fehlgeschlagen: {exc}",
              file=sys.stderr)
        print("    -> Laeuft der Server? Ist der Port in der Firewall offen?", file=sys.stderr)
        raise SystemExit(2)

    sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
    sock.settimeout(POLL_TIMEOUT)

    start = last_report = time.time()
    deadline = start + duration
    total = 0
    report_bytes = 0
    print(f"[TCP CLIENT] {host}:{port}  {duration:g}s")

    try:
        while True:
            now = time.time()
            if now >= deadline:
                break
            try:
                n = sock.send(CHUNK)
            except socket.timeout:
                continue
            except OSError as exc:
                print(f"[TCP CLIENT] Senden fehlgeschlagen: {exc}", file=sys.stderr)
                break
            total += n
            report_bytes += n

            now = time.time()
            if now >= last_report + 1.0:
                print(f"    {now - start:5.1f}s  "
                      f"{bytes_to_mbps(report_bytes, now - last_report):9.2f} Mbit/s")
                report_bytes = 0
                last_report = now
    finally:
        try:
            sock.shutdown(socket.SHUT_WR)
        except OSError:
            pass
        sock.close()

    elapsed = max(time.time() - start, 1e-9)
    print("\n[TCP CLIENT] Ergebnis")
    print(f"    Dauer .......... {elapsed:.2f} s")
    print(f"    Gesendet ....... {human_bytes(total)}")
    print(f"    Durchsatz ...... {bytes_to_mbps(total, elapsed):.2f} Mbit/s")


# ---------------------------------------------------------------- main
def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Netzwerk-Speedtest aehnlich iperf3 (TCP/UDP)")
    parser.add_argument("-s", "--server", action="store_true", help="Server-Modus")
    parser.add_argument("-c", "--client", metavar="SERVER_IP", nargs="?",
                        const="127.0.0.1", default=None,
                        help="Client-Modus, verbindet zu SERVER_IP (Standard: 127.0.0.1)")
    parser.add_argument("-p", "--port", type=int, default=DEFAULT_PORT,
                        help=f"Port (Standard: {DEFAULT_PORT})")
    parser.add_argument("-t", "--time", type=float, default=DEFAULT_TIME,
                        help=f"Testdauer in Sekunden (Standard: {DEFAULT_TIME:g})")
    parser.add_argument("-u", "--udp", action="store_true", help="UDP statt TCP")
    parser.add_argument("-l", "--length", type=int, default=DEFAULT_PACKET_LEN,
                        metavar="BYTE",
                        help=f"UDP-Paketgroesse (Standard: {DEFAULT_PACKET_LEN})")
    parser.add_argument("-b", "--bitrate", type=float, default=DEFAULT_BITRATE,
                        metavar="MBIT",
                        help="UDP-Zielrate in Mbit/s (Standard: 0 = unbegrenzt)")
    parser.add_argument("-V", "--version", action="version",
                        version=f"speedtest.py {VERSION}")
    args = parser.parse_args(argv)

    # --- Validierung zuerst ---
    if args.server and args.client is not None:
        parser.error("Server (-s) und Client (-c) schliessen sich aus.")
    if args.length < UDP_HDR.size + 8:
        parser.error(f"UDP-Paketgroesse muss mindestens {UDP_HDR.size + 8} Byte sein.")
    if args.time <= 0:
        parser.error("Testdauer (-t) muss > 0 sein.")
    if not 1 <= args.port <= 65535:
        parser.error("Port muss zwischen 1 und 65535 liegen.")

    if not args.server and args.client is None:
        parser.print_help()
        return 0

    if args.server:
        if args.udp:
            udp_server("0.0.0.0", args.port)
        else:
            tcp_server("0.0.0.0", args.port)
    elif args.udp:
        udp_client(args.client, args.port, args.time, args.length, args.bitrate)
    else:
        tcp_client(args.client, args.port, args.time)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n[INFO] Abgebrochen mit Ctrl+C.")
        sys.exit(130)

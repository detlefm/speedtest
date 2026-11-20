#!/usr/bin/env python3
"""
Network Speed Test - Python implementation similar to iperf3
Supports TCP and UDP throughput tests.

Usage:
  Server:  python speedtest.py -s -p 5201 -t 10
  Client:  python speedtest.py -c <server_ip> -p 5201 -t 10
  UDP:     add -u (e.g. python speedtest.py -s -u -p 5201)
"""

import socket
import time
import argparse
import struct

def calc_mbps(start, end, byte_count):
    """Bandwidth in Mbps (1 Mbps = 1e6 bit/s)."""
    duration = end - start
    if duration <= 0:
        return 0.0
    return byte_count * 8 / (duration * 1_000_000)

# ==================== TCP ====================
def tcp_server(host, port, duration):
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind((host, port))
    server.listen(1)
    print(f"[SERVER] Listening on {host}:{port} for {duration}s")

    conn, addr = server.accept()
    print(f"[SERVER] Connection from {addr[0]}:{addr[1]}")

    total = 0
    start = time.time()
    conn.settimeout(1)

    while True:
        try:
            data = conn.recv(65536)
        except socket.timeout:
            break
        if not data:
            break
        total += len(data)
        if time.time() - start >= duration:
            break

    elapsed = time.time() - start
    throughput = calc_mbps(start, time.time(), total)
    print(f"\n[SERVER] Received: {total} bytes")
    print(f"[SERVER] Duration: {elapsed:.2f}s")
    print(f"[SERVER] Bandwidth: {throughput:.2f} Mbps")

    conn.close()
    server.close()

def tcp_client(host, port, duration):
    client = socket.create_connection((host, port))
    client.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
    total = 0
    start = time.time()

    while time.time() - start < duration:
        chunk = b'\x00' * 65536
        try:
            n = client.send(chunk)
            total += n
        except OSError:
            break

    elapsed = time.time() - start
    throughput = calc_mbps(start, time.time(), total)
    print(f"\n[CLIENT] Sent: {total} bytes")
    print(f"[CLIENT] Duration: {elapsed:.2f}s")
    print(f"[CLIENT] Bandwidth: {throughput:.2f} Mbps")
    client.close()

# ==================== UDP ====================
def udp_server(host, port, duration):
    server = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    server.bind((host, port))
    server.settimeout(0.5)
    print(f"[UDP SERVER] Listening on {host}:{port} for {duration}s")

    start = time.time()
    end_time = start + duration
    received_count = 0
    total_bytes = 0

    while time.time() < end_time:
        try:
            data, addr = server.recvfrom(65536)
            received_count += 1
            total_bytes += len(data)
            server.sendto(b'P', addr)
        except socket.timeout:
            pass
        except OSError:
            break

    elapsed = time.time() - start
    throughput = calc_mbps(start, time.time(), total_bytes)
    print(f"\n[UDP SERVER] Packets received: {received_count}")
    print(f"[UDP SERVER] Duration: {elapsed:.2f}s")
    print(f"[UDP SERVER] Bandwidth: {throughput:.2f} Mbps")
    server.close()

def udp_client(host, port, duration):
    client = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    client.bind(('0.0.0.0', 0))
    client.settimeout(2)

    interval = 0.5
    packet_size = 1400
    start = time.time()
    sent_packets = 0
    rtts = []
    losses = 0
    total_bytes_sent = 0

    end_time = start + duration

    while time.time() - start < duration:
        seq = sent_packets
        data = struct.pack('!H', seq) + b'\x00' * (packet_size - 2)
        sent_time = time.time()
        try:
            client.sendto(data, (host, port))
        except OSError:
            losses += 1
            time.sleep(interval)
            continue
        sent_packets += 1
        total_bytes_sent += len(data)

        try:
            client.recvfrom(65536)
            rtts.append(time.time() - sent_time)
        except socket.timeout:
            losses += 1
        except OSError:
            losses += 1

        time.sleep(interval)

    elapsed = time.time() - start
    throughput = calc_mbps(start, time.time(), total_bytes_sent)
    avg_rtt = sum(rtts) / len(rtts) if rtts else 0
    variance = sum((r - avg_rtt) ** 2 for r in rtts) / len(rtts) if rtts else 0
    jitter = (variance ** 0.5) * 1000

    print(f"\n[UDP CLIENT] Packets sent: {sent_packets}")
    print(f"[UDP CLIENT] Packet loss: {losses}")
    print(f"[UDP CLIENT] Average RTT: {avg_rtt * 1000:.2f} ms")
    print(f"[UDP CLIENT] Jitter: {jitter:.2f} ms")
    print(f"[UDP CLIENT] Bandwidth: {throughput:.2f} Mbps")
    client.close()

# ==================== MAIN ====================
def main():
    parser = argparse.ArgumentParser(description='Network Speed Test (like iperf3)')
    parser.add_argument('-s', '--server', action='store_true', help='Run in server mode')
    parser.add_argument('-c', '--client', action='store_true', help='Run in client mode')
    parser.add_argument('-p', '--port', type=int, default=5201, help='Port number (default: 5201)')
    parser.add_argument('-t', '--time', type=int, default=10, help='Test duration in seconds (default: 10)')
    parser.add_argument('-u', '--udp', action='store_true', help='Use UDP mode (default: TCP)')
    args = parser.parse_args()

    host = '0.0.0.0' if args.server else '127.0.0.1'

    if args.server:
        if args.udp:
            udp_server(host, args.port, args.time)
        else:
            tcp_server(host, args.port, args.time)
    elif args.client:
        if args.udp:
            udp_client('127.0.0.1', args.port, args.time)
        else:
            tcp_client('127.0.0.1', args.port, args.time)
    else:
        parser.print_help()

if __name__ == '__main__':
    main()
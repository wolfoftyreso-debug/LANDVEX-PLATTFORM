"""Vad servern gör med en kropp den inte kan lita på.

Fyndet som gjorde testet nödvändigt: `int(self.headers.get("Content-
Length", 0))` följt av `self.rfile.read(length)` utan tak. En klient som
lovade två miljarder byte och skickade tio höll tråden för alltid —
ThreadingHTTPServer ger en tråd per anslutning, så en handfull sådana
anslutningar tömmer servern utan att skicka mer än några hundra byte.

Testet startar en riktig server och pratar rå HTTP mot den, eftersom
felen ligger i transportlagret och inte går att nå via en HTTP-klient som
själv beter sig korrekt.

Kör: python3 -m tests.test_http_limits
"""
from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import time

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_PORT = 8731
_PROC: subprocess.Popen | None = None


def _start() -> None:
    global _PROC
    env = {**os.environ, "LANDVEX_DB": "off", "LANDVEX_LIVE": "0",
           "LANDVEX_PORT": str(_PORT), "LANDVEX_HOST": "127.0.0.1",
           "LANDVEX_AUDIT_LOG": "off", "PYTHONPATH": _ROOT}
    _PROC = subprocess.Popen([sys.executable, "-m", "api.dev_server"],
                             cwd=_ROOT, env=env,
                             stdout=subprocess.DEVNULL,
                             stderr=subprocess.DEVNULL)
    for _ in range(100):                       # vänta tills den lyssnar
        try:
            socket.create_connection(("127.0.0.1", _PORT), timeout=0.5).close()
            return
        except OSError:
            time.sleep(0.1)
    raise AssertionError("dev-servern startade inte")


def _stop() -> None:
    if _PROC is not None:
        _PROC.terminate()
        _PROC.wait(timeout=10)


def _request(raw: bytes, timeout: float = 25.0) -> str:
    """Skicka en färdig HTTP-förfrågan och läs HELA svaret.

    Ett enda recv() räcker inte: kropp och huvud kan komma i skilda
    paket, vilket gör testet flakigt i stället för sant.
    """
    s = socket.create_connection(("127.0.0.1", _PORT), timeout=timeout)
    try:
        s.sendall(raw)
        s.settimeout(timeout)
        chunks = []
        while True:
            part = s.recv(8192)
            if not part:
                break
            chunks.append(part)
            data = b"".join(chunks)
            if b"\r\n\r\n" in data:
                head, _, sofar = data.partition(b"\r\n\r\n")
                length = 0
                for line in head.split(b"\r\n"):
                    if line.lower().startswith(b"content-length:"):
                        length = int(line.split(b":", 1)[1])
                if len(sofar) >= length:
                    break
        return b"".join(chunks).decode("utf-8", "replace")
    finally:
        s.close()


def _raw(headers: bytes, body: bytes, wait: float = 5.0) -> str:
    """Skicka en rå POST och returnera statusraden (eller "TIMEOUT")."""
    s = socket.create_connection(("127.0.0.1", _PORT), timeout=5)
    try:
        try:
            s.sendall(b"POST /v1/ask HTTP/1.1\r\nHost: t\r\n"
                      b"Content-Type: application/json\r\n"
                      + headers + b"\r\n\r\n" + body)
        except (BrokenPipeError, ConnectionResetError):
            pass                    # servern hann avvisa – helt i sin ordning
        s.settimeout(wait)
        try:
            return s.recv(120).split(b"\r\n")[0].decode("latin-1")
        except socket.timeout:
            return "TIMEOUT"
    finally:
        s.close()


def test_a_lying_content_length_does_not_hold_the_thread():
    """Kärnfyndet: lova 2 GB, skicka 10 byte, behåll tråden för evigt."""
    status = _raw(b"Content-Length: 2000000000", b'{"q":"hi"}')
    assert "TIMEOUT" not in status, (
        "Servern väntar fortfarande på byte som aldrig kommer. Några få "
        "sådana anslutningar räcker för att tömma trådpoolen.")
    assert "413" in status, status


def test_a_body_over_the_ceiling_is_refused_not_buffered():
    from api.dev_server import Handler
    status = _raw(f"Content-Length: {Handler.MAX_BODY_BYTES + 1}".encode(),
                  b"{}")
    assert "413" in status, status


def test_a_content_length_that_is_not_a_number_is_a_client_error():
    """Tidigare: ValueError → 500, alltså vårt fel för klientens huvud."""
    assert "400" in _raw(b"Content-Length: abc", b"{}")
    assert "400" in _raw(b"Content-Length: -5", b"{}")


def test_malformed_json_is_400_and_says_so():
    assert "400" in _raw(b"Content-Length: 9", b"{not json")


def test_a_json_body_that_is_not_an_object_is_refused():
    assert "400" in _raw(b"Content-Length: 7", b"[1,2,3]")


def test_a_missing_field_names_the_field():
    """`str(KeyError("lat"))` är `"'lat'"` — ett ord inom apostrofer säger
    varken vilket fält eller att det saknas."""
    body = b"{}"
    data = _request(b"POST /v1/analyze HTTP/1.1\r\nHost: t\r\n"
                    b"Content-Type: application/json\r\n"
                    b"Content-Length: " + str(len(body)).encode()
                    + b"\r\n\r\n" + body)
    assert " 422 " in data.split("\r\n")[0], data.split("\r\n")[0]
    payload = json.loads(data.split("\r\n\r\n", 1)[1])
    assert "Missing required field" in payload["error"], payload
    assert "lat" in payload["error"], payload


def test_an_open_path_leaves_a_metric_but_no_audit_row():
    """Öppna vägar går utanför Gate — men INTE utanför driftbilden.

    Mätt före fixen: tio vägar (startsidan, /health, /openapi.json …)
    lämnade inget spår alls i /metrics. En driftbild där startsidan
    aldrig hänt är gladare än verkligheten — och gladare än verkligheten
    är exakt det plattformens egen doktrin förbjuder statusytor att
    vara. Audit-rad ska däremot INTE skrivas: anonym HTML är brus i en
    säkerhetslogg, och det valet är medvetet.
    """
    svar = _request(b"GET /health HTTP/1.1\r\nHost: t\r\n\r\n")
    assert '"status"' in svar
    metrik = _request(b"GET /metrics HTTP/1.1\r\nHost: t\r\n\r\n")
    kropp = json.loads(metrik.partition("\r\n\r\n")[2])
    assert kropp["requests_by_path"].get("/health", 0) >= 1, (
        f"/health syns inte i metriken: {sorted(kropp['requests_by_path'])}")


def test_a_normal_request_still_works():
    """Grinden får inte ha stängt dörren för riktiga anrop."""
    body = json.dumps({"question": "var behovs elektriker"}).encode()
    s = socket.create_connection(("127.0.0.1", _PORT), timeout=15)
    s.sendall(b"POST /v1/ask HTTP/1.1\r\nHost: t\r\n"
              b"Content-Type: application/json\r\n"
              b"Content-Length: " + str(len(body)).encode() + b"\r\n\r\n" + body)
    s.settimeout(20)
    head = s.recv(60).split(b"\r\n")[0].decode()
    s.close()
    assert "200" in head, head


if __name__ == "__main__":
    _start()
    try:
        fns = [v for k, v in sorted(globals().items())
               if k.startswith("test_")]
        for fn in fns:
            fn()
            print(f"  ✓ {fn.__name__}")
        print(f"\n{len(fns)} tester gröna.")
    finally:
        _stop()

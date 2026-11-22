"""VishaSynapse WebSocket 송신. 기준: 명세 01 §3, VishaSynapse docs/protocol/README.md §3·§4·§7.

메인 루프는 send()로 최신 패킷만 넘기고, 접속·등록·송신·재접속은 송신 스레드가 한다.
서버 ping에는 websockets 라이브러리가 자동으로 pong을 보낸다.
"""
import json
import queue
import threading

from websockets.exceptions import ConnectionClosed, WebSocketException
from websockets.sync.client import connect

from body_packet import SIG_BODY

REGISTER_MESSAGE = json.dumps({"to": 0, "from": SIG_BODY, "type": "client.register", "data": ""})
RETRY_SEC = 2.0          # 재접속 간격
OPEN_TIMEOUT_SEC = 3.0   # 접속·등록 응답 대기
POLL_SEC = 0.5           # 종료 요청 확인 간격


class SynapseSender:
    def __init__(self, url):
        self._url = url
        self._latest = queue.Queue(maxsize=1)    # 최신 패킷 1개만 (C#의 크기 1 ConcurrentQueue)
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, name="synapse-sender", daemon=True)
        self._thread.start()

    def send(self, packet):
        # 메인 루프용. 막히지 않고, 아직 안 보낸 이전 패킷은 버린다.
        try:
            self._latest.get_nowait()
        except queue.Empty:
            pass
        try:
            self._latest.put_nowait(packet)
        except queue.Full:
            pass    # 송신 스레드와 겹친 경우. 다음 프레임이 곧 온다.

    def close(self):
        self._stop.set()
        self._thread.join(timeout=OPEN_TIMEOUT_SEC + POLL_SEC + 1)

    def _run(self):
        last_error = None
        while not self._stop.is_set():
            try:
                # compression: float 데이터는 거의 줄지 않아 CPU만 씀. proxy: LAN 직결
                with connect(self._url, open_timeout=OPEN_TIMEOUT_SEC, compression=None, proxy=None) as ws:
                    self._register(ws)
                    print("[송신] VishaSynapse 등록 완료")
                    last_error = None
                    self._send_loop(ws)
            except (OSError, WebSocketException, RegisterError) as e:
                error = describe(e)
                if error != last_error:     # 같은 실패를 재시도마다 반복 출력하지 않음
                    print(f"[송신] 연결 안 됨: {error}. {RETRY_SEC:g}초마다 다시 시도")
                    last_error = error
            self._stop.wait(RETRY_SEC)

    def _register(self, ws):
        ws.send(REGISTER_MESSAGE)
        reply = json.loads(ws.recv(timeout=OPEN_TIMEOUT_SEC))
        if reply.get("type") != "client.registered":
            raise RegisterError(reply.get("data"))
        # 등록 전에 쌓인 패킷은 버린다
        try:
            self._latest.get_nowait()
        except queue.Empty:
            pass

    def _send_loop(self, ws):
        while not self._stop.is_set():
            try:
                packet = self._latest.get(timeout=POLL_SEC)
            except queue.Empty:
                continue
            ws.send(packet)


class RegisterError(Exception):
    pass


def describe(e):
    # 예외 종류와 종료 코드만 (받은 내용 전체는 남기지 않음)
    if isinstance(e, ConnectionClosed):
        rcvd = e.rcvd
        return f"연결 종료 (코드 {rcvd.code} {rcvd.reason})" if rcvd else "연결 종료 (종료 신호 없음)"
    if isinstance(e, RegisterError):
        data = e.args[0] if isinstance(e.args[0], dict) else {}
        return f"등록 실패 (에러 {data.get('code')} {data.get('message')})"
    return type(e).__name__

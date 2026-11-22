import socket
import struct


class UdpSender:
    """유니티로 포즈 데이터 전송. 패킷 = uint 시퀀스 번호 + float 배열."""

    def __init__(self, addr):
        self._addr = addr
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._seq = 0

    def send_pose(self, world_landmarks):
        # 33관절 × [x, y, z, visibility] = 132 float
        values = []
        for lm in world_landmarks:
            values += [lm.x, lm.y, lm.z, lm.visibility]

        self._seq += 1
        self._sock.sendto(struct.pack("<I132f", self._seq, *values), self._addr)

    def close(self):
        self._sock.close()

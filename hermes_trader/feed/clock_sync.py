"""Exchange clock calibration using the midpoint of a request round trip."""
import time


class ClockSynchronizer:
    def __init__(self):
        self.clock_offset_ms = 0.0

    def update_offset(self, client_send_ts_ms, server_ts_ms, client_recv_ts_ms):
        rtt = client_recv_ts_ms - client_send_ts_ms
        offset = server_ts_ms - (client_send_ts_ms + rtt / 2.0)
        self.clock_offset_ms = 0.8 * self.clock_offset_ms + 0.2 * offset

    def get_calibrated_timestamp_ms(self):
        return int(time.time() * 1000 + self.clock_offset_ms)

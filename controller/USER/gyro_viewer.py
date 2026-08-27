"""
WHEELTEC 小车陀螺仪/加速度计数据实时可视化
用法：python gyro_viewer.py [COM端口]
默认端口：COM7
MPU6050 配置: Gyro ±500°/s, Accel ±2g
"""

import sys
import threading
from collections import deque

import serial
import matplotlib.pyplot as plt
import matplotlib.animation as animation

# ========== 协议常量 ==========
FRAME_HEADER = 0x7B
FRAME_TAIL = 0x7D
FRAME_LEN = 24

# ========== MPU6050 量程换算 (来源: MPU6050.c 初始化) ==========
GYRO_SCALE  = 65.5     # ±500°/s:  1 °/s = 65.5 LSB
ACCEL_SCALE = 16384.0  # ±2g:      1 g  = 16384 LSB

# ========== 解析一帧 ==========
def parse_frame(data: bytes):
    """解析 24 字节帧，返回物理量字典。校验失败返回 None。"""
    if len(data) != FRAME_LEN:
        return None
    if data[0] != FRAME_HEADER or data[-1] != FRAME_TAIL:
        return None

    # 异或校验（字节 0~21）
    xor = 0
    for b in data[:22]:
        xor ^= b
    if xor != data[22]:
        return None

    def i16(hi, lo):
        val = (data[hi] << 8) | data[lo]
        return val if val < 32768 else val - 65536

    return {
        "flag_stop": data[1],
        "x_speed":   i16(2, 3),
        "y_speed":   i16(4, 5),
        "z_speed":   i16(6, 7),
        "accel_x":   i16(8, 9)   / ACCEL_SCALE,   # g
        "accel_y":   i16(10, 11) / ACCEL_SCALE,   # g
        "accel_z":   i16(12, 13) / ACCEL_SCALE,   # g
        "gyro_x":    i16(14, 15) / GYRO_SCALE,    # °/s
        "gyro_y":    i16(16, 17) / GYRO_SCALE,    # °/s
        "gyro_z":    i16(18, 19) / GYRO_SCALE,    # °/s
        "voltage":   (data[20] << 8 | data[21]) / 1000.0,  # V
    }


# ========== 串口读取线程 ==========
class SerialReader:
    def __init__(self, port, baud=115200):
        self.buf = bytearray()
        self.gyro_x  = deque(maxlen=500)
        self.gyro_y  = deque(maxlen=500)
        self.gyro_z  = deque(maxlen=500)
        self.accel_x = deque(maxlen=500)
        self.accel_y = deque(maxlen=500)
        self.accel_z = deque(maxlen=500)
        self.tick = 0
        self.lock = threading.Lock()
        self.running = True
        self.ser = serial.Serial(port, baud, timeout=0.5)
        self.frames = 0
        self.errors = 0

    def read_loop(self):
        """后台线程，从串口读数据并解析帧"""
        while self.running:
            try:
                chunk = self.ser.read(self.ser.in_waiting or 1)
                if not chunk:
                    continue
                self.buf.extend(chunk)

                while len(self.buf) >= FRAME_LEN:
                    if self.buf[0] != FRAME_HEADER:
                        self.buf.pop(0)
                        continue
                    frame = bytes(self.buf[:FRAME_LEN])
                    result = parse_frame(frame)
                    if result is not None:
                        with self.lock:
                            self.tick += 1
                            self.frames += 1
                            self.gyro_x.append(result["gyro_x"])
                            self.gyro_y.append(result["gyro_y"])
                            self.gyro_z.append(result["gyro_z"])
                            self.accel_x.append(result["accel_x"])
                            self.accel_y.append(result["accel_y"])
                            self.accel_z.append(result["accel_z"])
                        del self.buf[:FRAME_LEN]
                    else:
                        self.errors += 1
                        self.buf.pop(0)
            except Exception as e:
                print(f"串口错误: {e}")
                break

    def start(self):
        self.thread = threading.Thread(target=self.read_loop, daemon=True)
        self.thread.start()

    def stop(self):
        self.running = False
        self.ser.close()


# ========== Y 轴自适应 ==========
def auto_ylim(ax, data, min_span=1.0, margin=0.2):
    """根据可见数据动态调整 Y 轴范围，最小跨度 min_span，margin 百分比留白"""
    if not data:
        return
    lo, hi = min(data), max(data)
    span = hi - lo
    if span < min_span:
        center = (lo + hi) / 2
        lo, hi = center - min_span / 2, center + min_span / 2
    pad = (hi - lo) * margin
    ax.set_ylim(lo - pad, hi + pad)


# ========== 主程序 ==========
def main():
    port = sys.argv[1] if len(sys.argv) > 1 else "COM7"
    print(f"[*] 打开串口 {port} @ 115200 ...")
    reader = SerialReader(port)
    reader.start()

    # 2 行 3 列: 陀螺仪 | 加速度计
    fig, axes = plt.subplots(2, 3, figsize=(14, 7))
    fig.canvas.manager.set_window_title(f"WHEELTEC IMU — {port}")
    (ax_gx, ax_gy, ax_gz), (ax_ax, ax_ay, ax_az) = axes

    lines = {}

    def init_ax(ax, title, ylabel, color):
        line, = ax.plot([], [], lw=1.0, color=color)
        ax.set_title(title, fontsize=10, fontweight="bold")
        ax.set_xlim(0, 500)
        ax.grid(True, alpha=0.3, linestyle="--")
        ax.set_ylabel(ylabel, fontsize=9)
        ax.axhline(y=0, color="gray", lw=0.5, alpha=0.5)
        return line

    # 陀螺仪: 红绿蓝
    lines["gx"] = init_ax(ax_gx, "Gyro X",   "°/s", "#E74C3C")
    lines["gy"] = init_ax(ax_gy, "Gyro Y",   "°/s", "#2ECC71")
    lines["gz"] = init_ax(ax_gz, "Gyro Z",   "°/s", "#3498DB")
    # 加速度计: 红绿蓝
    lines["ax"] = init_ax(ax_ax, "Accel X",  "g",   "#E74C3C")
    lines["ay"] = init_ax(ax_ay, "Accel Y",  "g",   "#2ECC71")
    lines["az"] = init_ax(ax_az, "Accel Z",  "g",   "#3498DB")

    # 预设 Y 轴初始范围，防止刚启动时抖动太大
    ax_gx.set_ylim(-5, 5)
    ax_gy.set_ylim(-5, 5)
    ax_gz.set_ylim(-5, 5)
    ax_ax.set_ylim(-2, 2)
    ax_ay.set_ylim(-2, 2)
    ax_az.set_ylim(-2, 2)

    title = fig.suptitle("", fontsize=9)

    # Y 轴自适应计数器：每 N 帧更新一次 Y 轴，减少抖动
    ylim_counter = 0
    YLIM_INTERVAL = 8  # 每 8 帧 = 400ms 更新一次 Y 轴

    def update(_):
        nonlocal ylim_counter
        with reader.lock:
            t = reader.tick
            gx = list(reader.gyro_x)
            gy = list(reader.gyro_y)
            gz = list(reader.gyro_z)
            ax_d = list(reader.accel_x)
            ay   = list(reader.accel_y)
            az   = list(reader.accel_z)
            frames = reader.frames
            errors = reader.errors

        if not gx:
            return list(lines.values())

        x_range = range(max(0, t - len(gx)), t)

        # 更新曲线数据
        for key, data, line in [
            ("gx", gx, lines["gx"]),
            ("gy", gy, lines["gy"]),
            ("gz", gz, lines["gz"]),
            ("ax", ax_d, lines["ax"]),
            ("ay", ay, lines["ay"]),
            ("az", az, lines["az"]),
        ]:
            line.set_data(list(x_range)[-len(data):], data)

        # X 轴滚动
        left = max(0, t - 500)
        right = left + 500
        for ax in axes.flat:
            ax.set_xlim(left, right)

        # Y 轴自适应（每 YLIM_INTERVAL 帧一调）
        ylim_counter += 1
        if ylim_counter >= YLIM_INTERVAL:
            ylim_counter = 0
            # 陀螺 Y 轴: 最小跨度 10°/s
            auto_ylim(ax_gx, gx, min_span=10)
            auto_ylim(ax_gy, gy, min_span=10)
            auto_ylim(ax_gz, gz, min_span=10)
            # 加速度 Y 轴: 最小跨度 0.5g
            auto_ylim(ax_ax, ax_d, min_span=0.5)
            auto_ylim(ax_ay, ay, min_span=0.5)
            auto_ylim(ax_az, az, min_span=0.5)

        rate = f"({errors/frames*100:.1f}%)" if frames else ""
        title.set_text(f"接收帧: {frames}  |  丢帧: {errors} {rate}")

        return list(lines.values()) + [title]

    ani = animation.FuncAnimation(
        fig, update, interval=50,
        blit=False, cache_frame_data=False
    )

    plt.tight_layout()
    plt.subplots_adjust(top=0.92, hspace=0.35, wspace=0.3)
    plt.show()

    reader.stop()
    print("[*] 退出")


if __name__ == "__main__":
    main()

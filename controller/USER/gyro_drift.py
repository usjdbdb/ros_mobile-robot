"""
Gyro dynamic drift test: rotate 90deg -> return to 0 -> check if integrated angle returns to 0
Usage: python gyro_drift.py [COM port]
"""
import sys
import time
import threading
from collections import deque

import serial
import matplotlib
matplotlib.use('TkAgg')
import matplotlib.pyplot as plt
import matplotlib.animation as animation

HEADER, TAIL = 0x7B, 0x7D
GYRO_SCALE = 65.5
DT = 1.0 / 20  # 20Hz

def i16(b1, b2):
    v = (b1 << 8) | b2
    return v if v < 32768 else v - 65536

port = sys.argv[1] if len(sys.argv) > 1 else "COM7"
ser = serial.Serial(port, 115200, timeout=0.5)
buf = bytearray()

# data buffers
gyro_z_raw = deque(maxlen=2000)
angle_z     = deque(maxlen=2000)
times       = deque(maxlen=2000)

# state machine
STATE_IDLE, STATE_RECORD, STATE_DONE = 0, 1, 2
state = STATE_IDLE
record_start = 0
angle = 0.0
first_frame = True

fig, (ax_gyro, ax_angle) = plt.subplots(2, 1, figsize=(12, 7))
fig.canvas.manager.set_window_title(f"Gyro Drift Test - {port}")
fig.suptitle("[SPACE] Start  |  Rotate car 90deg & back  |  [SPACE] Stop",
             fontsize=12, fontweight='bold')

line_gz, = ax_gyro.plot([], [], lw=1, color='#E74C3C')
line_angle, = ax_angle.plot([], [], lw=2, color='#3498DB')

ax_gyro.set_ylabel('Gyro Z (deg/s)')
ax_gyro.set_title('Gyro Z Angular Velocity')
ax_gyro.grid(True, alpha=0.3)
ax_gyro.axhline(y=0, color='gray', lw=0.5)

ax_angle.set_ylabel('Angle (deg)')
ax_angle.set_xlabel('Time (s)')
ax_angle.set_title('Integrated Angle = sum(GyroZ * dt)')
ax_angle.grid(True, alpha=0.3)
ax_angle.axhline(y=0, color='gray', lw=0.5)

# real-time value readouts
val_gz = ax_gyro.text(0.98, 0.95, "GyroZ: --- deg/s", transform=ax_gyro.transAxes,
                       ha='right', va='top', fontsize=11, fontweight='bold',
                       color='#E74C3C', bbox=dict(boxstyle='round,pad=0.3', facecolor='white', alpha=0.85))
val_ang = ax_angle.text(0.98, 0.95, "Angle: --- deg", transform=ax_angle.transAxes,
                         ha='right', va='top', fontsize=11, fontweight='bold',
                         color='#3498DB', bbox=dict(boxstyle='round,pad=0.3', facecolor='white', alpha=0.85))

status_text = fig.text(0.5, 0.01, "WAITING - Press SPACE to start",
                       ha='center', fontsize=11, color='orange')

# serial reader thread
frame_lock = threading.Lock()
pending_frames = []

def serial_reader():
    global buf, pending_frames
    while True:
        try:
            chunk = ser.read(ser.in_waiting or 1)
            if not chunk:
                continue
            buf.extend(chunk)
            while len(buf) >= 24:
                if buf[0] != HEADER:
                    buf.pop(0); continue
                frame = bytes(buf[:24])
                if len(frame) == 24 and frame[0] == HEADER and frame[23] == TAIL:
                    xor = 0
                    for b in frame[:22]:
                        xor ^= b
                    if xor == frame[22]:
                        gz = i16(frame[18], frame[19]) / GYRO_SCALE
                        with frame_lock:
                            pending_frames.append(gz)
                del buf[:24]
        except:
            break

threading.Thread(target=serial_reader, daemon=True).start()

def on_key(event):
    global state, record_start, angle, first_frame
    if event.key == ' ':
        if state == STATE_IDLE:
            state = STATE_RECORD
            record_start = time.time()
            angle = 0.0
            first_frame = True
            gyro_z_raw.clear(); angle_z.clear(); times.clear()
            status_text.set_text("RECORDING - Rotate car 90deg & back, then SPACE to stop")
            status_text.set_color('lime')
        elif state == STATE_RECORD:
            state = STATE_DONE
            if angle_z:
                final = angle_z[-1]
                if abs(final) < 2:
                    grade = "EXCELLENT"
                elif abs(final) < 5:
                    grade = "OK"
                else:
                    grade = "POOR"
                status_text.set_text(
                    f"DONE! Final angle = {final:.2f} deg | "
                    f"Drift = {abs(final):.2f} deg [{grade}]"
                )
                status_text.set_color('gold')
            ser.close()

fig.canvas.mpl_connect('key_press_event', on_key)

def update(_):
    global angle, first_frame

    with frame_lock:
        frames = pending_frames[:]
        pending_frames.clear()

    if state == STATE_RECORD:
        for gz in frames:
            t = time.time() - record_start
            if first_frame:
                first_frame = False
                continue
            angle += gz * DT
            gyro_z_raw.append(gz)
            angle_z.append(angle)
            times.append(t)

    if gyro_z_raw:
        t_list = list(times)
        gz_list = list(gyro_z_raw)
        angle_list = list(angle_z)

        line_gz.set_data(t_list, gz_list)
        line_angle.set_data(t_list, angle_list)

        ax_gyro.set_xlim(max(0, t_list[0]), t_list[-1] + 1)
        ax_angle.set_xlim(max(0, t_list[0]), t_list[-1] + 1)

        if gz_list:
            gz_max = max(abs(min(gz_list)), abs(max(gz_list)))
            gz_span = max(gz_max, 50) * 1.2
            ax_gyro.set_ylim(-gz_span, gz_span)

        if angle_list:
            a_max = max(abs(min(angle_list)), abs(max(angle_list)))
            a_span = max(a_max, 45) * 1.2
            ax_angle.set_ylim(-a_span, a_span)

    # refresh fill area
    for coll in ax_angle.collections:
        coll.remove()
    if angle_z:
        ax_angle.fill_between(list(times), 0, list(angle_z),
                              alpha=0.15, color='#3498DB')

    # update real-time value readouts
    if gyro_z_raw:
        latest_gz = gyro_z_raw[-1]
        latest_ang = angle_z[-1]
        val_gz.set_text(f"GyroZ: {latest_gz:+.2f} deg/s")
        val_ang.set_text(f"Angle: {latest_ang:+.2f} deg")

    return [line_gz, line_angle, val_gz, val_ang, status_text]

ani = animation.FuncAnimation(fig, update, interval=50, blit=False, cache_frame_data=False)
plt.tight_layout()
plt.subplots_adjust(bottom=0.08, top=0.90)
plt.show()

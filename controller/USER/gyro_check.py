"""
快速诊断：采样 10 秒，检测陀螺仪三轴零偏
"""
import sys
import time
import serial

HEADER, TAIL = 0x7B, 0x7D
GYRO_SCALE = 65.5

def i16(b1, b2):
    v = (b1 << 8) | b2
    return v if v < 32768 else v - 65536

port = sys.argv[1] if len(sys.argv) > 1 else "COM7"
ser = serial.Serial(port, 115200, timeout=0.5)
buf = bytearray()
frames = 0
gx_list, gy_list, gz_list = [], [], []

print(f"[*] 监听 {port}，采样 10 秒...\n")
print(f"{'帧':>6}  {'Gyro X':>10}  {'Gyro Y':>10}  {'Gyro Z':>10}")
print("-" * 45)

t0 = time.time()
while time.time() - t0 < 10:
    chunk = ser.read(ser.in_waiting or 1)
    if not chunk:
        continue
    buf.extend(chunk)
    while len(buf) >= 24:
        if buf[0] != HEADER:
            buf.pop(0)
            continue
        frame = bytes(buf[:24])
        if len(frame) == 24 and frame[0] == HEADER and frame[23] == TAIL:
            xor = 0
            for b in frame[:22]:
                xor ^= b
            if xor == frame[22]:
                frames += 1
                gx = i16(frame[14], frame[15]) / GYRO_SCALE
                gy = i16(frame[16], frame[17]) / GYRO_SCALE
                gz = i16(frame[18], frame[19]) / GYRO_SCALE
                gx_list.append(gx); gy_list.append(gy); gz_list.append(gz)
                if frames <= 5 or frames % 40 == 0:  # 前5帧和每2秒一条
                    print(f"{frames:>6}  {gx:>10.3f}  {gy:>10.3f}  {gz:>10.3f}")
        del buf[:24]

ser.close()

if gx_list:
    from statistics import mean, stdev
    print(f"\n{'='*55}")
    print(f"  采样帧数: {frames}")
    print(f"{'':>8}{'X':>14}{'Y':>14}{'Z':>14}")
    print(f"  均值:     {mean(gx_list):>8.4f} °/s  {mean(gy_list):>8.4f} °/s  {mean(gz_list):>8.4f} °/s")
    print(f"  标准差:   {stdev(gx_list):>8.4f} °/s  {stdev(gy_list):>8.4f} °/s  {stdev(gz_list):>8.4f} °/s")
    print(f"  峰峰值:   {max(gx_list)-min(gx_list):>8.4f} °/s  {max(gy_list)-min(gy_list):>8.4f} °/s  {max(gz_list)-min(gz_list):>8.4f} °/s")
    print()
    zero_drift = [abs(mean(gx_list)), abs(mean(gy_list)), abs(mean(gz_list))]
    worst = max(zero_drift)
    axis  = ["X", "Y", "Z"][zero_drift.index(worst)]
    if worst < 0.5:
        print(f"  ✅ 零偏轻微，最大 {axis} 轴仅 {worst:.3f} °/s，漂移不严重")
    elif worst < 2.0:
        print(f"  ⚠️  {axis} 轴零偏 {worst:.2f} °/s，有轻微漂移但可接受")
    else:
        print(f"  ❌ {axis} 轴零偏 {worst:.2f} °/s，漂移较严重，建议重新校准")
else:
    print("未收到任何有效帧，请检查连接！")

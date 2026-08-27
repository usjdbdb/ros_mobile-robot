# ROS 移动机器人（差速小车）

基于 WHEELTEC 差速移动小车（STM32F407 + FreeRTOS）的 ROS 移动机器人项目。本仓库包含**机械结构模型**、**下位机控制器固件**和 **ROS 上位机代码**三部分。

## 仓库结构

```
ros_mobile-robot/
├── controller/                     # 下位机：STM32 控制器固件（Keil MDK 工程）
│   ├── USER/                       #   应用层代码与 Keil 工程（WHEELTEC.uvprojx）
│   ├── BALANCE/                    #   差速运动控制
│   ├── HARDWARE/                   #   外设驱动（电机/编码器/CAN/OLED 等）
│   ├── FreeRTOS/                   #   FreeRTOS V9.0.0 内核
│   ├── FWLIB/                      #   STM32F4 标准外设库
│   └── CORE/                       #   CMSIS 内核文件
├── solidworks/                     # 机械结构：SolidWorks 模型
│   └── 11号机模型/                 #   零件、装配体与 STEP 导出
└── ros/                            # 上位机：ROS（Melodic）工作空间
    └── src/
        └── turn_on_wheeltec_robot/ #   核心包：串口通信与建图/导航启动文件
```

## 各部分说明

### 1. controller/ —— STM32 控制器固件（下位机）

- 主控：STM32F407，RTOS：FreeRTOS V9.0.0
- 开发环境：Keil MDK5，工程文件：`controller/USER/WHEELTEC.uvprojx`
- 主要功能：双电机差速驱动、编码器测速、MPU6050 姿态解算、CAN 总线（电机驱动器）、OLED 显示、自动充电对接等
- 与上位机通过串口通信

### 2. solidworks/ —— 机械结构模型

- `11号机模型/`：整机零件（`.SLDPRT`）、装配体（`.SLDASM`）及 STEP 导出文件
- ⚠️ `雷达层装配.SLDASM` 超过 100 MB，使用 **Git LFS** 存储，克隆前需安装：

```bash
git lfs install
```

### 3. ros/ —— ROS 上位机代码

- 运行环境：Ubuntu 18.04 + ROS Melodic
- 核心包 `turn_on_wheeltec_robot`：
  - `wheeltec_robot.cpp`：通过 serial 串口与下位机 STM32 通信（速度指令、里程计、IMU 数据等）
  - `Quaternion_Solution.cpp`：四元数姿态解算
  - 启动文件（位于 `launch/`）：

| 类别 | launch 文件 |
| --- | --- |
| 2D 建图 / 导航 | `mapping.launch`、`navigation.launch` |
| 3D 建图 / 导航 | `3d_mapping.launch`、`3d_navigation.launch`、`pure3d_mapping.launch`、`pure3d_navigation.launch` |
| 自主探索 | `rrt_slam.launch` |
| 传感器驱动 | `wheeltec_lidar.launch`、`wheeltec_camera.launch` |
| 模型可视化 | `robot_model_visualization.launch` |

- 使用步骤：

```bash
mkdir -p ~/catkin_ws/src
cp -r ros/src/turn_on_wheeltec_robot ~/catkin_ws/src/
cd ~/catkin_ws && catkin_make
source devel/setup.bash
roslaunch turn_on_wheeltec_robot turn_on_wheeltec_robot.launch
```

- ⚠️ 依赖说明：launch 文件会调用其他 ROS 包（navigation 导航栈、slam_karto、robot_pose_ekf、teb_local_planner、rrt_exploration、激光雷达驱动 rplidar_ros / ldlidar、相机驱动 realsense / astra、rtabmap 等），这些包**不在本仓库内**，需按 WHEELTEC 官方教程或各包官方仓库自行安装。

## 克隆仓库

```bash
git lfs install
git clone https://github.com/usjdbdb/ros_mobile-robot.git
```

## 许可说明

| 目录 | 许可 |
| --- | --- |
| `controller/` | WHEELTEC 差速小车配套固件；其中 FreeRTOS（GPLv2 + 例外）、ST 标准外设库（MCD-ST Liberty）、CMSIS（ARM）等第三方库按其各自许可证分发 |
| `ros/` | `turn_on_wheeltec_robot` 的 `package.xml` 中 license 未声明（TODO），如需公开发布请补充许可证 |
| `solidworks/` | 模型文件版权归原作者所有 |

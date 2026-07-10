

from enum import IntEnum, auto
import glob
import math
from typing import Tuple
import psutil

import pyamdgpuinfo

import library.sensors.sensors as sensors
from library.sensors.sensors_python import sensors_fans, Cpu, Memory, Net
from library.log import logger

try:
    from config_bc250 import FAN_MAX_RPM, DISK_MOUNT_POINT
except ImportError:
    FAN_MAX_RPM = 3000
    DISK_MOUNT_POINT = '/var'


class GpuType(IntEnum):
    UNSUPPORTED = auto()
    AMD = auto()


DETECTED_GPU = GpuType.UNSUPPORTED


class Cpu(Cpu):

    @staticmethod
    def fan_percent(fan_name: str = 'pump') -> float:
        try:
            # Try with psutil fans
            fans = sensors_fans()
            if fans:
                for name, entries in fans.items():
                    for entry in entries:
                        if fan_name in (entry.label.lower() or name.lower()):
                            rpm = entry.current
                            percent = int(rpm / FAN_MAX_RPM * 100)
                            return 100 if percent > 100 else percent
        except Exception:
            return math.nan


class Gpu(sensors.Gpu):

    @staticmethod
    def _get_cyan_skillfish_gpu_usage() -> float:
        paths = glob.glob("/sys/class/drm/card*/device/gpu_metrics")
        if not paths:
            return "Error: GPU metrics path not found."

        try:
            with open(paths[0], "rb") as f:
                # Seek to byte 28 (the 16-bit activity field)
                f.seek(28)
                bytes_data = f.read(2)

                if len(bytes_data) == 2:
                    # Unpack little-endian 16-bit integer
                    basis_points = int.from_bytes(
                        bytes_data, byteorder='little')

                    # Filter out uninitialized driver bytes (65535 / 0xFFFF)
                    if basis_points > 10000:
                        raise ValueError(
                            f'Obtained huge load: {basis_points / 100}')

                    # Convert basis points to standard percentage (e.g., 10000 -> 100.0%)
                    load_percentage = basis_points / 100
                    return load_percentage
                raise ValueError('Could not read required bytes.')
        except Exception as e:
            logger.warning(
                "Could not obtain GPU load from Cyan Skillfish Governor."
                "Make sure it is up and running. \n"
                f"Error: {repr(e)}"
            )
            return math.nan

    @staticmethod
    def stats() -> Tuple[
        float, float, float, float, float]:  # load (%) / used mem (%) / used mem (Mb) / total mem (Mb) / temp (°C)
        # Unlike other sensors, AMD GPU with pyamdgpuinfo pulls in all the stats at once
        pyamdgpuinfo.detect_gpus()
        amd_gpu = pyamdgpuinfo.get_gpu(0)

        try:
            memory_used_bytes = amd_gpu.query_vram_usage() + \
                                amd_gpu.query_gtt_usage()
            memory_used = memory_used_bytes / 1024 / 1024
        except Exception:
            memory_used_bytes = math.nan
            memory_used = math.nan

        try:
            # Dynamically allocated memory, so this will not work correctly
            # memory_total_bytes = amd_gpu.memory_info["vram_size"]
            # Use free RAM + used VRAM or VRAM reserved memory
            memory_total_bytes = 8 * 2**30
            memory_total_bytes = \
                max(memory_used_bytes, amd_gpu.memory_info["vram_size"]) + \
                psutil.virtual_memory().available
            memory_total = memory_total_bytes / 1024 / 1024
        except Exception:
            memory_total_bytes = math.nan
            memory_total = math.nan

        try:
            memory_percentage = (memory_used_bytes / memory_total_bytes) * 100
        except Exception:
            memory_percentage = math.nan

        try:
            load = int(Gpu._get_cyan_skillfish_gpu_usage())
        except Exception:
            load = math.nan

        try:
            temperature = amd_gpu.query_temperature()
        except Exception:
            temperature = math.nan

        return load, memory_percentage, memory_used, memory_total, temperature

    @staticmethod
    def fps() -> int:
        # Not supported by Python libraries
        return -1

    @staticmethod
    def fan_percent() -> float:
        return Cpu.fan_percent()

    @staticmethod
    def frequency() -> float:
        try:
            pyamdgpuinfo.detect_gpus()
            return pyamdgpuinfo.get_gpu(0).query_sclk() / 1000000
        except:
            return math.nan

    @staticmethod
    def is_available() -> bool:
        global DETECTED_GPU
        # Check if it is BC-250 GPU
        if pyamdgpuinfo.detect_gpus() > 0:
            logger.info("Detected AMD GPU(s)")
            DETECTED_GPU = GpuType.AMD

        return DETECTED_GPU != GpuType.UNSUPPORTED


class Disk(sensors.Disk):
    @staticmethod
    def disk_usage_percent() -> float:
        try:
            return psutil.disk_usage(DISK_MOUNT_POINT).percent
        except:
            return math.nan

    @staticmethod
    def disk_used() -> int:  # In bytes
        try:
            return psutil.disk_usage(DISK_MOUNT_POINT).used
        except:
            return -1

    @staticmethod
    def disk_free() -> int:  # In bytes
        try:
            return psutil.disk_usage(DISK_MOUNT_POINT).free
        except:
            return -1

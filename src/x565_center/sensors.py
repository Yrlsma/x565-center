"""Опрос датчиков в отдельном потоке. Всё только на чтение.

Если датчик недоступен, его значение None: интерфейс скрывает плитку, программа не падает.
"""
from __future__ import annotations

import asyncio
import ctypes
import os
import subprocess
import tempfile
import time
import winreg
import xml.etree.ElementTree as ET
from ctypes import wintypes
from pathlib import Path

import psutil
from PySide6.QtCore import QObject, QTimer, Signal, Slot

from . import display

NO_WINDOW = 0x08000000
RADIO_WIFI, RADIO_BLUETOOTH = 1, 3  # Windows.Devices.Radios.RadioKind
RADIO_ON, RADIO_OFF = 1, 2  # RadioState


def cpu_name() -> str:
    try:
        with winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE, r"HARDWARE\DESCRIPTION\System\CentralProcessor\0"
        ) as key:
            name = winreg.QueryValueEx(key, "ProcessorNameString")[0]
    except OSError:
        return "Процессор"
    name = name.replace("AMD ", "").replace("with Radeon Graphics", "")
    return " ".join(name.split())


class _PowerStatus(ctypes.Structure):
    _fields_ = [
        ("ACLineStatus", ctypes.c_ubyte),
        ("BatteryFlag", ctypes.c_ubyte),
        ("BatteryLifePercent", ctypes.c_ubyte),
        ("SystemStatusFlag", ctypes.c_ubyte),
        ("BatteryLifeTime", wintypes.DWORD),
        ("BatteryFullLifeTime", wintypes.DWORD),
    ]


def read_battery() -> dict | None:
    st = _PowerStatus()
    if not ctypes.windll.kernel32.GetSystemPowerStatus(ctypes.byref(st)):
        return None
    if st.BatteryFlag & 128 or st.BatteryLifePercent > 100:  # батареи нет / неизвестно
        return None
    return {
        "percent": int(st.BatteryLifePercent),
        "plugged": st.ACLineStatus == 1,
        "charging": bool(st.BatteryFlag & 8),
    }


def read_battery_health() -> dict | None:
    """Проектная и текущая полная ёмкость (мВт·ч) из отчёта powercfg. Запись — только во временный файл."""
    path = Path(tempfile.gettempdir()) / f"x565center_battery_{os.getpid()}.xml"
    try:
        subprocess.run(
            ["powercfg", "/batteryreport", "/xml", "/output", str(path)],
            capture_output=True, timeout=30, creationflags=NO_WINDOW,
        )
        root = ET.parse(path).getroot()
        design = full = 0
        for battery in root.iter():
            if battery.tag.rsplit("}", 1)[-1] != "Battery":
                continue
            for el in battery:
                tag, text = el.tag.rsplit("}", 1)[-1], (el.text or "").strip()
                if tag == "DesignCapacity" and text.isdigit():
                    design += int(text)
                elif tag == "FullChargeCapacity" and text.isdigit():
                    full += int(text)
        if design <= 0 or full <= 0:
            return None
        return {"design": design, "full": full, "wear": max(0, round((1 - full / design) * 100))}
    except (OSError, ValueError, ET.ParseError, subprocess.TimeoutExpired):
        return None
    finally:
        path.unlink(missing_ok=True)


class _Nvidia:
    """Дискретная видеокарта через NVML."""

    def __init__(self) -> None:
        self.handle = None
        self.name = None
        try:
            import pynvml

            self._nv = pynvml
            pynvml.nvmlInit()
            self.handle = pynvml.nvmlDeviceGetHandleByIndex(0)
            name = pynvml.nvmlDeviceGetName(self.handle)
            if isinstance(name, bytes):
                name = name.decode(errors="replace")
            self.name = name.replace("NVIDIA ", "").replace(" Laptop GPU", "")
        except Exception:
            self.handle = None

    def read(self) -> tuple[int | None, int | None]:
        if self.handle is None:
            return None, None
        try:
            temp = self._nv.nvmlDeviceGetTemperature(self.handle, self._nv.NVML_TEMPERATURE_GPU)
            load = self._nv.nvmlDeviceGetUtilizationRates(self.handle).gpu
            return int(temp), int(load)
        except Exception:
            return None, None

    def close(self) -> None:
        if self.handle is not None:
            try:
                self._nv.nvmlShutdown()
            except Exception:
                pass


class _Lhm:
    """Температура процессора и обороты вентиляторов через LibreHardwareMonitorLib.

    Работает, только если программа запущена от администратора, установлен pythonnet
    и рядом лежит vendor/LibreHardwareMonitorLib.dll. Иначе значения None.
    Библиотека используется только для чтения датчиков.
    """

    def __init__(self) -> None:
        self.computer = None
        dll = Path(__file__).resolve().parents[2] / "vendor" / "LibreHardwareMonitorLib.dll"
        try:
            if not dll.exists() or not ctypes.windll.shell32.IsUserAnAdmin():
                return
            import clr  # pythonnet

            clr.AddReference(str(dll))
            from LibreHardwareMonitor import Hardware

            self._hw = Hardware
            computer = Hardware.Computer()
            computer.IsCpuEnabled = True
            computer.IsMotherboardEnabled = True
            computer.IsControllerEnabled = True
            computer.Open()
            self.computer = computer
        except Exception:
            self.computer = None

    def read(self) -> tuple[int | None, int | None]:
        """(температура процессора, обороты самого быстрого вентилятора)."""
        if self.computer is None:
            return None, None
        temp = fan = None
        try:
            stack = list(self.computer.Hardware)
            while stack:
                hw = stack.pop()
                hw.Update()
                stack.extend(hw.SubHardware)
                is_cpu = hw.HardwareType == self._hw.HardwareType.Cpu
                for s in hw.Sensors:
                    if s.Value is None:
                        continue
                    value = float(s.Value)
                    if is_cpu and s.SensorType == self._hw.SensorType.Temperature:
                        temp = value if temp is None else max(temp, value)
                    elif s.SensorType == self._hw.SensorType.Fan and value > 0:
                        fan = value if fan is None else max(fan, value)
        except Exception:
            return None, None
        return (round(temp) if temp is not None else None, round(fan) if fan is not None else None)

    def close(self) -> None:
        if self.computer is not None:
            try:
                self.computer.Close()
            except Exception:
                pass


class SensorWorker(QObject):
    snapshot = Signal(dict)
    radios = Signal(dict)  # {"wifi": bool | None, "bluetooth": bool | None}
    battery_health = Signal(object)  # dict | None

    RADIO_EVERY = 5.0  # секунд между опросами Wi‑Fi/Bluetooth

    def __init__(self) -> None:
        super().__init__()
        self._interval = 1000
        self._timer = None
        self._nvidia = None
        self._lhm = None
        self._loop = None
        self._radio_cls = None
        self._last_radio = 0.0

    @Slot()
    def start(self) -> None:
        self._nvidia = _Nvidia()
        self._lhm = _Lhm()
        try:
            from winrt.windows.devices.radios import Radio

            self._radio_cls = Radio
            self._loop = asyncio.new_event_loop()
        except Exception:
            self._radio_cls = None
        psutil.cpu_percent(None)
        self._timer = QTimer(self)
        self._timer.timeout.connect(self.poll)
        self._timer.start(self._interval)
        self.poll()
        self.battery_health.emit(read_battery_health())

    @Slot()
    def stop(self) -> None:
        if self._timer:
            self._timer.stop()
        if self._nvidia:
            self._nvidia.close()
        if self._lhm:
            self._lhm.close()
        if self._loop:
            self._loop.close()

    @Slot(int)
    def set_interval(self, ms: int) -> None:
        self._interval = ms
        if self._timer:
            self._timer.setInterval(ms)

    @Slot()
    def poll(self) -> None:
        gpu_temp, gpu_load = self._nvidia.read()
        cpu_temp, fan = self._lhm.read()
        mem = psutil.virtual_memory()
        battery = read_battery()
        self.snapshot.emit({
            "time": time.monotonic(),
            "cpu_load": round(psutil.cpu_percent(None)),
            "cpu_temp": cpu_temp,
            "gpu_name": self._nvidia.name,
            "gpu_temp": gpu_temp,
            "gpu_load": gpu_load,
            "fan_rpm": fan,
            "mem_used": mem.used,
            "mem_total": mem.total,
            "battery": battery,
            "brightness": display.get_brightness(battery["plugged"] if battery else True),
        })
        if time.monotonic() - self._last_radio >= self.RADIO_EVERY:
            self._poll_radios()

    # --- Wi‑Fi и Bluetooth (стандартный интерфейс Windows.Devices.Radios) ---

    async def _radio_states(self) -> dict:
        states = {"wifi": None, "bluetooth": None}
        for radio in await self._radio_cls.get_radios_async():
            key = {RADIO_WIFI: "wifi", RADIO_BLUETOOTH: "bluetooth"}.get(int(radio.kind))
            if key:
                states[key] = int(radio.state) == RADIO_ON
        return states

    async def _radio_set(self, kind: int, on: bool) -> None:
        from winrt.windows.devices.radios import RadioState

        await self._radio_cls.request_access_async()
        for radio in await self._radio_cls.get_radios_async():
            if int(radio.kind) == kind:
                await radio.set_state_async(RadioState(RADIO_ON if on else RADIO_OFF))

    def _poll_radios(self) -> None:
        self._last_radio = time.monotonic()
        if self._radio_cls is None:
            self.radios.emit({"wifi": None, "bluetooth": None})
            return
        try:
            self.radios.emit(self._loop.run_until_complete(self._radio_states()))
        except Exception:
            self.radios.emit({"wifi": None, "bluetooth": None})

    @Slot(str, bool)
    def set_radio(self, name: str, on: bool) -> None:
        if self._radio_cls is None:
            return
        kind = RADIO_WIFI if name == "wifi" else RADIO_BLUETOOTH
        try:
            self._loop.run_until_complete(self._radio_set(kind, on))
        except Exception:
            pass
        self._poll_radios()

    @Slot(int)
    def set_brightness(self, value: int) -> None:
        display.set_brightness(value)

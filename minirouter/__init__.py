import json
import logging
import logging.config
import os
import threading
from pathlib import Path
from socket import gethostbyname
from time import sleep, time

import requests
import requests.packages.urllib3.util.connection as urllib3_cn
import sdbus
from sdbus_block.networkmanager import (
    AccessPoint,
    DeviceState,
    DeviceType,
    IPv4Config,
    NetworkDeviceGeneric,
    NetworkDeviceWireless,
    NetworkManager,
)

from .ui.ui import Ui

urllib3_cn.HAS_IPV6 = False

log = logging.getLogger(__name__)


statuses = {
    "interfaces": None,
    "dns": None,
    "wan_ip": None,
    "time": None,
}


def get_interfaces(network_manager, interfaces=None):
    devices = {"devices": {}, "wifi": None}

    for path, device in sorted(
        [(path, NetworkDeviceGeneric(path)) for path in network_manager.devices], key=lambda item: item[1].interface
    ):
        if interfaces and device.interface not in interfaces:
            continue

        device_type = DeviceType(device.device_type)
        state = DeviceState(device.state)

        info = {
            "interface": device.interface,
            "state": state,
            "ip4": "-",
            "type": device_type,
            "ssid": "-",
        }

        if state is DeviceState.ACTIVATED:
            ip = IPv4Config(device.ip4_config)
            try:
                if ip.address_data:
                    ipa = ip.address_data[0]
                    info["ip4"] = f"{ipa['address'][1]}/{ipa['prefix'][1]}"

            except Exception as ex:
                log.info("error getting ip: %s", str(ex))
                info["ip4"] = "E"

            try:
                if device_type is DeviceType.WIFI:
                    devices["wifi"] = device.interface

                    wlan = NetworkDeviceWireless(path)
                    if wlan.active_access_point:
                        ap = AccessPoint(wlan.active_access_point)
                        info["ssid"] = ap.ssid.decode()
                        info["strength"] = ap.strength
                    else:
                        info["ssid"] = None
                        info["strength"] = None
            except Exception as ex:
                log.info("error getting ssid: %s", str(ex))
                info["ssid"] = "* error *"

        devices["devices"][device.interface] = info

    return devices


def run_interfaces_loop(interfaces, refresh):
    sdbus.set_default_bus(sdbus.sd_bus_open_system())
    network_manager = NetworkManager()

    while True:
        try:
            res = get_interfaces(network_manager, interfaces=interfaces)
            statuses["interfaces"] = res
        except Exception:
            log.exception("error in ips loop")
        sleep(refresh)


def check_dns_working(hostname):
    try:
        return gethostbyname(hostname)
    except Exception as ex:
        log.info("error checking dns: %s", str(ex))
        return None


def run_dns_loop(hostname, refresh):
    while True:
        try:
            is_dns_working = check_dns_working(hostname)
            statuses["dns"] = bool(is_dns_working)
        except Exception:
            log.exception("error in dns loop")
            statuses["dns"] = False
        sleep(refresh)


def get_wan_ip():
    is_ip = False
    if statuses["dns"]:
        res = requests.get("https://share.us.davidrios.dev/myip")
        is_ip = True
    else:
        res = requests.get("http://1.1.1.1")

    if res.status_code != 200:
        return "-error-"

    return res.content.decode() if is_ip else "online"


def run_wan_ip_loop(refresh):
    while True:
        try:
            wan_ip = get_wan_ip()
            statuses["wan_ip"] = wan_ip
        except Exception:
            log.exception("error in wan ip loop")
            statuses["wan_ip"] = "-error-"
        sleep(refresh)


def main():
    config = {}

    config_file = Path(os.environ.get("CONFIG_FILE", "config.json"))
    if config_file.is_file():
        with config_file.open() as fp:
            config.update(json.load(fp))

    logging.config.dictConfig(config.get("logging", {"version": 1}))

    log.info("starting")

    config["refresh"] = config.get("refresh", 1)

    refresh = config["refresh"]

    threading.Thread(
        target=run_interfaces_loop,
        args=(config.get("interfaces"), refresh),
        daemon=True,
    ).start()

    threading.Thread(
        target=run_dns_loop,
        args=(config.get("check_dns", "google.com"), refresh),
        daemon=True,
    ).start()

    threading.Thread(
        target=run_wan_ip_loop,
        args=(refresh,),
        daemon=True,
    ).start()

    ui = Ui(config)
    ui.initialize()

    last_debug = 0

    try:
        while True:
            if time() - last_debug > refresh:
                log.debug("statuses: %s", statuses)
                last_debug = time()

            ui.draw()
            sleep(0.01)
    except KeyboardInterrupt:
        log.info("exiting...")
        ui.cleanup()


if __name__ == "__main__":
    main()

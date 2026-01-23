import json
import logging
import logging.config
import os
from pathlib import Path
from socket import gethostbyname
from time import sleep

import requests
import requests.packages.urllib3.util.connection as urllib3_cn
import sdbus
from sdbus_block.networkmanager import (
    ActiveConnection,
    DeviceState,
    DeviceType,
    IPv4Config,
    NetworkConnectionSettings,
    NetworkDeviceGeneric,
    NetworkManager,
)

urllib3_cn.HAS_IPV6 = False

log = logging.getLogger("minirouter")


def get_ips(network_manager, interfaces=None):
    devices = []

    for device in [NetworkDeviceGeneric(path) for path in network_manager.devices]:
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
                    con = ActiveConnection(device.active_connection)
                    settings = NetworkConnectionSettings(con.connection).get_settings()
                    info["ssid"] = settings["802-11-wireless"]["ssid"][1].decode()
            except Exception as ex:
                log.info("error getting ssid: %s", str(ex))
                info["ssid"] = "E"

        devices.append(info)

    devices.sort(key=lambda item: item["interface"])

    return devices


def check_dns_working(hostname):
    try:
        return gethostbyname(hostname)
    except Exception as ex:
        log.info("error checking dns: %s", str(ex))
        return None


def get_wan_ip():
    res = requests.get("https://share.us.davidrios.dev/myip")
    if res.status_code != 200:
        return "E"
    return res.content.decode()


def main():
    config = {}

    config_file = Path(os.environ.get("CONFIG_FILE", "config.json"))
    if config_file.is_file():
        with config_file.open() as fp:
            config.update(json.load(fp))

    logging.config.dictConfig(config.get("logging", {"version": 1}))

    sdbus.set_default_bus(sdbus.sd_bus_open_system())
    network_manager = NetworkManager()

    log.info("starting")

    while True:
        log.debug("main loop iteration")

        ips = get_ips(network_manager, interfaces=config.get("interfaces"))
        log.debug(ips)

        is_dns_working = check_dns_working(config.get("check_dns", "google.com"))
        log.debug("is_dns_working: %s", is_dns_working)

        wan_ip = get_wan_ip()
        log.debug("wan_ip: %s", wan_ip)

        sleep(1)


if __name__ == "__main__":
    main()

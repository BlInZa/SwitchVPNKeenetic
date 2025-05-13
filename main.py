import paramiko
import re
import getpass
import json
import os
import sys
from paramiko.ssh_exception import AuthenticationException, NoValidConnectionsError
import socket

CONFIG_FILE = "vpn_config.json"


def ssh_exec(command, ip, username, password):
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(ip, username=username, password=password, timeout=5)
    stdin, stdout, stderr = ssh.exec_command(command)
    return stdout.read().decode(errors='ignore')


def safe_ssh_exec(command, ip, username, password):
    try:
        return ssh_exec(command, ip, username, password)
    except (AuthenticationException, NoValidConnectionsError, socket.timeout, OSError):
        return None


def list_interfaces_with_desc(ip, username, password):
    result = safe_ssh_exec("show interface", ip, username, password)
    if result is None:
        return None

    interface_blocks = result.split("\n\n")
    interfaces = []

    for block in interface_blocks:
        name_match = re.search(r"interface-name:\s+(\S+)", block)
        type_match = re.search(r"type:\s+(OpenVPN|PPTP|L2TP|IPSec)", block)
        desc_match = re.search(r"description:\s+(.+)", block)

        if name_match and type_match:
            name = name_match.group(1)
            vpn_type = type_match.group(1)
            desc = desc_match.group(1).strip() if desc_match else ""
            interfaces.append((name, vpn_type, desc))

    return interfaces


def choose_interface(ip, username, password):
    interfaces = list_interfaces_with_desc(ip, username, password)
    if interfaces is None:
        return None

    if not interfaces:
        print("❌ Не найдено VPN-интерфейсов.")
        return None

    print("\n📋 Найдены VPN-интерфейсы:")
    for idx, (name, vpn_type, desc) in enumerate(interfaces, start=1):
        desc_display = f" — {desc}" if desc else ""
        print(f"{idx}. {name}{desc_display} ({vpn_type})")

    while True:
        choice = input("Введите номер интерфейса для использования: ").strip()
        if choice.isdigit() and 1 <= int(choice) <= len(interfaces):
            return interfaces[int(choice) - 1][0]
        else:
            print("⚠ Неверный ввод. Попробуйте снова.")


def get_interface_status(interface, ip, username, password):
    result = ssh_exec(f"show interface {interface}", ip, username, password)
    link_match = re.search(r"link:\s+(up|down)", result, re.IGNORECASE)
    state_match = re.search(r"state:\s+(up|down)", result, re.IGNORECASE)

    if link_match and state_match:
        return link_match.group(1).lower(), state_match.group(1).lower()
    return None, None


def update_interface(config, password):
    new_interface = choose_interface(config['router_ip'], config['username'], password)
    if new_interface:
        config['vpn_interface'] = new_interface
        with open(CONFIG_FILE, "w") as f:
            json.dump(config, f)
        print(f"✅ Обновлён интерфейс: {new_interface}")
        return new_interface
    else:
        print("❌ Не удалось сменить интерфейс.")
        return config['vpn_interface']


def toggle_interface(password):
    config = load_config()
    ip = config["router_ip"]
    username = config["username"]
    interface = config["vpn_interface"]

    link, state = get_interface_status(interface, ip, username, password)
    if link is None or state is None:
        print(f"[!] Не удалось получить статус интерфейса {interface}.")
        return

    print(f"\n🛰️  Статус интерфейса {interface}:")
    print(f"   link:  {link}")
    print(f"   state: {state}")

    action = input(
        f"\n❔ Вы хотите {'выключить' if link == 'up' else 'включить'} интерфейс {interface}? (y/n/c = сменить): ").strip().lower()

    if action == "y":
        cmd = f"interface {interface} {'down' if link == 'up' else 'up'}"
        print(f"\n⚙ Выполняется: {cmd}")
        ssh_exec(cmd, ip, username, password)
        print("✅ Готово.")
    elif action == "c":
        config["vpn_interface"] = update_interface(config, password)
        toggle_interface(config, password)
    else:
        print("❎ Операция отменена.")


def initial_setup():
    print("🛠 Настройка подключения:")
    ip = input("Введите IP-адрес роутера (например, 192.168.1.1): ").strip()
    username = input("Введите логин: ").strip()
    password = getpass.getpass("Введите пароль: ")

    interface = choose_interface(ip, username, password)
    if interface:
        config = {
            "router_ip": ip,
            "username": username,
            "vpn_interface": interface
        }
        with open(CONFIG_FILE, "w") as f:
            json.dump(config, f)
        print(f"✅ Сохранена конфигурация: {interface} @ {ip} ({username})")
        return config, password
    else:
        print("❌ Ошибка авторизации или интерфейсы недоступны.")
        initial_setup()


def load_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE) as f:
            return json.load(f)
    return None


if __name__ == "__main__":
    config = load_config()
    if not config:
        result = initial_setup()
        if not result:
            sys.exit(1)
        config, password = result
    else:
        while True:
            print(f"🔐 Подключение к {config['router_ip']} как {config['username']}")
            password = getpass.getpass("Введите пароль: ")
            result = list_interfaces_with_desc(config['router_ip'], config['username'], password)
            if result is None:
                initial_setup()
                break
            else:
                break
    toggle_interface(password)

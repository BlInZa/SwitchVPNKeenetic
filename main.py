import paramiko
import re
import getpass

ROUTER_IP = "192.168.0.254"
USERNAME = "admin"
VPN_INTERFACE = "OpenVPN0"


def ssh_exec(command, password):
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        ssh.connect(ROUTER_IP, username=USERNAME, password=password, timeout=10)
        stdin, stdout, stderr = ssh.exec_command(command)
        output = stdout.read().decode(errors='ignore')
        return output
    finally:
        ssh.close()


def get_interface_status(interface, password):
    result = ssh_exec(f"show interface {interface}", password)
    link_match = re.search(r"link:\s+(up|down)", result, re.IGNORECASE)
    state_match = re.search(r"state:\s+(up|down)", result, re.IGNORECASE)

    if link_match and state_match:
        link = link_match.group(1).lower()
        state = state_match.group(1).lower()
        return link, state
    else:
        print(f"[!] Не удалось определить статус интерфейса {interface}.")
        return None, None


def toggle_interface(interface, password):
    link, state = get_interface_status(interface, password)
    if link is None or state is None:
        return

    print(f"\n🛰️  Статус интерфейса {interface}:")
    print(f"   link:  {link}")
    print(f"   state: {state}")

    if link == "up" and state == "up":
        action = "выключить"
    else:
        action = "включить"

    confirm = input(f"\n❔ Вы хотите {action} интерфейс {interface}? (y/n): ").strip().lower()
    if confirm == "y":
        command = f"interface {interface} {'down' if link == 'up' else 'up'}"
        print(f"\n⚙ Выполняется: {command}")
        ssh_exec(command, password)
        print("✅ Готово.")
    else:
        print("❎ Операция отменена.")


if __name__ == "__main__":
    print(f"🔐 Подключение к {ROUTER_IP} как {USERNAME}")
    password = getpass.getpass("Введите пароль: ")
    toggle_interface(VPN_INTERFACE, password)

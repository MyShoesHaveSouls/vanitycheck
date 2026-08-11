import subprocess
import re
import os
import sqlite3
import sys
import time
import threading

def init_db():
    conn = sqlite3.connect("eth_secure_vault.db")
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS matches (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            mode TEXT,
            criteria TEXT,
            address TEXT UNIQUE,
            salt_found TEXT,
            private_key TEXT
        )
    """)
    conn.commit()
    conn.close()

def log_match(mode, criteria, address, salt, private_key):
    try:
        conn = sqlite3.connect("eth_secure_vault.db")
        cursor = conn.cursor()
        cursor.execute(
            "INSERT OR IGNORE INTO matches (mode, criteria, address, salt_found, private_key) VALUES (?, ?, ?, ?, ?)",
            (mode, criteria, address, salt, private_key)
        )
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"\n[-] Database error: {e}")
        return False

def calculate_final_private_key(salt, seed_private_key):
    binary_path = "./profanity2/bin/profanity2"
    calc_cmd = [binary_path, "--calculate", "--salt", salt, "--secret", seed_private_key]
    try:
        result = subprocess.run(calc_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
        for line in result.stdout.splitlines():
            if "Private Key:" in line or "private" in line.lower():
                return line.split(":")[-1].strip()
    except Exception as e:
        print(f"\n[-] Automated calculation failed: {e}")
    return "AUTOMATION_ERROR_CHECK_MANUALLY"

def load_richlist(filepath="richlist.txt"):
    if not os.path.exists(filepath):
        with open(filepath, "w") as f:
            f.write("# Add 40-character target hex addresses (one per line, without 0x)\n")
        print(f"[!] Created empty '{filepath}'. Please add target data.")
        return set()
    with open(filepath, "r") as f:
        addresses = {line.strip().lower().replace("0x", "") for line in f if line.strip() and not line.startswith("#")}
    print(f"[✓] Successfully loaded {len(addresses)} target entries from {filepath}.")
    return addresses

def get_gpu_temperature():
    """Queries nvidia-smi directly to pull the exact hardware core temperature."""
    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=temperature.gpu", "--format=csv,noheader,nounits"],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True
        )
        return f"{result.stdout.strip()}°C"
    except:
        return "N/A"

# Thread-safe global variables for our odometer dashboard
current_hash_rate = 0.0
estimated_total_checked = 0
stop_odometer = False

def odometer_thread_worker():
    global current_hash_rate, estimated_total_checked, stop_odometer
    last_tick = time.time()
    last_temp_check = 0.0
    gpu_temp = "Checking..."
    
    while not stop_odometer:
        time.sleep(0.1)
        now = time.time()
        elapsed = now - last_tick
        last_tick = now
        
        # Smoothly query nvidia-smi only once a second so we don't stress the system bus
        if now - last_temp_check >= 1.0:
            gpu_temp = get_gpu_temperature()
            last_temp_check = now
        
        keys_processed_in_slice = int(current_hash_rate * 1_000_000 * elapsed)
        estimated_total_checked += keys_processed_in_slice
        
        # Integrated UI Update: Displays temp, speed, and total keys processed simultaneously
        sys.stdout.write(f"\r🔥 [GTX 1080 Temp: {gpu_temp} | Speed: {current_hash_rate:.2f} MH/s] | Total Keys Generated: {estimated_total_checked:,}")
        sys.stdout.flush()

def trigger_audio_chime():
    for _ in range(5):
        sys.stdout.write('\a')
        sys.stdout.flush()
        time.sleep(0.2)

def run_engine():
    global current_hash_rate, estimated_total_checked, stop_odometer
    binary_path = "./profanity2/bin/profanity2"
    if not os.path.exists(binary_path):
        print(f"[-] Error: '{binary_path}' binary not found. Verify your path setup.")
        sys.exit(1)
        
    init_db()
    
    print("=========================================================")
    print("🚀 NVIDIA GTX 1080 HYBRID PIPELINE WITH THERMAL MONITOR")
    print("=========================================================")
    
    keys = {"private": None, "public": None}
    if os.path.exists(".env"):
        with open(".env", "r") as f:
            for line in f:
                if "SEED_PRIVATE_KEY" in line: keys["private"] = line.split("=")[-1].strip().replace('"', '')
                if "SEED_PUBLIC_KEY" in line: keys["public"] = line.split("=")[-1].strip().replace('"', '')
                
    if keys["private"] and keys["public"]:
        print("[✓] Automatically loaded local credentials.")
        seed_private = keys["private"]
        seed_public = keys["public"]
    else:
        seed_private = input("Paste your Secret Seed Key: ").strip().lower()
        seed_public  = input("Paste your 128-char Public Key: ").strip().lower()
        
    if seed_public.startswith("04") and len(seed_public) == 130:
        seed_public = seed_public[2:]

    print("\nSelect Mode:")
    print("1. Prefix Matching  (Starts with...)")
    print("2. Suffix Matching  (Ends with...)")
    print("3. Keyword Matching (Contains sequence...)")
    print("4. Multi-Matching   (Complex Prefix AND Suffix pattern)")
    print("5. Rich List System (Compare against 'richlist.txt')")
    choice = input("Enter choice (1-5): ").strip()

    cmd = [binary_path, "-z", seed_public]
    mode_str, criteria_str, regex_obj = "", "", None
    rich_set = set()

    if choice == "1":
        mode_str = "Prefix"; pat = input("Enter prefix: ").strip().lower()
        cmd.extend(["--leading", pat]); regex_obj = re.compile(f"^0x{pat}", re.IGNORECASE)
    elif choice == "2":
        mode_str = "Suffix"; pat = input("Enter suffix: ").strip().lower()
        cmd.extend(["--matching", pat]); regex_obj = re.compile(f"{pat}$", re.IGNORECASE)
    elif choice == "3":
        mode_str = "Keyword"; pat = input("Enter keyword: ").strip().lower()
        cmd.extend(["--matching", pat]); regex_obj = re.compile(f"{pat}", re.IGNORECASE)
    elif choice == "4":
        mode_str = "Multi-Match"; pfx = input("Prefix: ").strip().lower(); sfx = input("Suffix: ").strip().lower()
        criteria_str = f"P:{pfx}|S:{sfx}"; cmd.extend(["--matching", pfx]); regex_obj = re.compile(f"^0x{pfx}.*{sfx}$", re.IGNORECASE)
    elif choice == "5":
        mode_str = "Rich List"; rich_set = load_richlist()
        criteria_str = f"{len(rich_set)} targets"; cmd.extend(["--matching", "00"])
    else:
        print("[-] Invalid choice."); return

    print(f"\n[*] Activating GPU Core Array. Running live thermal dashboard...")
    print("=========================================================")
    
    o_thread = threading.Thread(target=odometer_thread_worker, daemon=True)
    o_thread.start()

    try:
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)
        current_address, current_salt = None, None
        
        for line in iter(process.stdout.readline, ""):
            line = line.strip()
            if not line: continue
            
            if any(term in line.lower() for term in ["time:", "speed:", "total:", "m/s", "h/s"]):
                speed_match = re.search(r'(\d+\.?\d*)\s*[M]H/s', line, re.IGNORECASE)
                if speed_match:
                    current_hash_rate = float(speed_match.group(1))
            
            if "address:" in line.lower(): current_address = line.lower().split("address:")[-1].strip()
            if "salt:" in line.lower(): current_salt = line.lower().split("salt:")[-1].strip()
                
            if current_address and current_salt:
                is_match = False
                if choice == "5":
                    if current_address.lower().replace("0x", "") in rich_set: is_match = True
                else:
                    if regex_obj.search(current_address): is_match = True
                        
                if is_match:
                    stop_odometer = True 
                    sys.stdout.write("\r" + " " * 115 + "\r")
                    print("🎉 MATCH FOUND BY GTX 1080!")
                    print(f"Address:     {current_address}")
                    final_private_key = calculate_final_private_key(current_salt, seed_private)
                    print(f"Private Key: {final_private_key}")
                    log_match(mode_str, criteria_str, current_address, current_salt, final_private_key)
                    print("=========================================================")
                    trigger_audio_chime()
                    
                    stop_odometer = False
                    o_thread = threading.Thread(target=odometer_thread_worker, daemon=True)
                    o_thread.start()
                        
                current_address, current_salt = None, None
                
    except KeyboardInterrupt:
        stop_odometer = True
        print("\n\n[-] Safely shutting down pipeline nodes.")
        process.terminate()

if __name__ == "__main__":
    run_engine()

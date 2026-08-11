import subprocess
import re
import os
import sqlite3
import sys
import time

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
            if "Private Key:" in line:
                return line.split("Private Key:")[-1].strip()
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

def run_engine():
    binary_path = "./profanity2/bin/profanity2"
    if not os.path.exists(binary_path):
        print(f"[-] Error: '{binary_path}' binary not found. Verify your path setup.")
        sys.exit(1)
        
    init_db()
    
    print("=========================================================")
    print("🚀 NVIDIA GTX 1080 HYBRID AUTOMATED PIPELINE WITH TRACKER")
    print("=========================================================")
    seed_private = input("Paste your Step 2 Secret/Private Seed Key: ").strip().lower()
    seed_public  = input("Paste your Step 2 128-char Public Key:    ").strip().lower()
    
    # Strip leading '04' uncompressed prefix if the user included it
    if seed_public.startswith("04") and len(seed_public) == 130:
        seed_public = seed_public[2:]
        print("[*] Automatically trimmed leading '04' from Public Key.")
    
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
        mode_str = "Prefix"
        criteria_str = input("Enter leading characters (hex): ").strip().lower()
        cmd.extend(["--leading", criteria_str])
        regex_obj = re.compile(f"^0x{criteria_str}", re.IGNORECASE)
    elif choice == "2":
        mode_str = "Suffix"
        criteria_str = input("Enter trailing characters (hex): ").strip().lower()
        cmd.extend(["--matching", criteria_str]) 
        regex_obj = re.compile(f"{criteria_str}$", re.IGNORECASE)
    elif choice == "3":
        mode_str = "Keyword"
        criteria_str = input("Enter keyword (hex): ").strip().lower()
        cmd.extend(["--matching", criteria_str])
        regex_obj = re.compile(f"{criteria_str}", re.IGNORECASE)
    elif choice == "4":
        mode_str = "Multi-Match"
        pfx = input("Enter required Prefix: ").strip().lower()
        sfx = input("Enter required Suffix: ").strip().lower()
        criteria_str = f"P:{pfx} | S:{sfx}"
        cmd.extend(["--matching", pfx]) 
        regex_obj = re.compile(f"^0x{pfx}.*{sfx}$", re.IGNORECASE)
    elif choice == "5":
        mode_str = "Rich List"
        rich_set = load_richlist()
        criteria_str = f"{len(rich_set)} addresses loaded"
        # Using native '0' flag tells profanity2 to stream out every calculated item
        cmd.extend(["--matching", "0"]) 
    else:
        print("[-] Invalid execution choice.")
        return

    print(f"\n[*] Activating GPU Core Array. Pipeline stream active...")
    print("=========================================================")
    
    try:
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)
        
        current_address, current_salt = None, None
        total_checked = 0
        current_speed = "0.00 MH/s"
        last_update_time = time.time()
        
        for line in iter(process.stdout.readline, ""):
            line = line.strip()
            
            # 1. Capture speed metrics directly from the underlying OpenCL engine stream
            if "Time:" in line and "m/s" in line:
                # Extracts values like "Total: 45.23 MH/s" or counts from the hardware text
                speed_match = re.search(r'(\d+\.\d+\s*[M|G]?H/s)', line)
                if speed_match:
                    current_speed = speed_match.group(1)
            
            # 2. Parse structural keys output generated from the binary stream
            if "Address:" in line:
                current_address = line.split("Address:")[-1].strip()
            if "Salt:" in line:
                current_salt = line.split("Salt:")[-1].strip()
                
            if current_address and current_salt:
                total_checked += 1
                is_match = False
                
                if choice == "5":
                    clean_addr = current_address.lower().replace("0x", "")
                    if clean_addr in rich_set:
                        is_match = True
                else:
                    if regex_obj.search(current_address):
                        is_match = True
                        
                if is_match:
                    # Clear out the scrolling status line so the success prints cleanly
                    sys.stdout.write("\r" + " " * 80 + "\r")
                    print("🎉 MATCH FOUND BY GTX 1080!")
                    print(f"Address:     {current_address}")
                    print(f"Salt:        {current_salt}")
                    print("[*] Calculating final usable private key pair...")
                    final_private_key = calculate_final_private_key(current_salt, seed_private)
                    print(f"Private Key: {final_private_key}")
                    
                    if log_match(mode_str, criteria_str, current_address, current_salt, final_private_key):
                        print("[✓] Saved to secure local vault SQLite database.")
                    print("=========================================================")
                        
                current_address, current_salt = None, None
            
            # 3. Asynchronous Screen Refresher (updates the visual counter smoothly without slowing your card down)
            now = time.time()
            if now - last_update_time >= 0.4:
                # \r moves the cursor back to the start of the line instead of spamming down your screen
                sys.stdout.write(f"\r📊 [GTX 1080 Speed: {current_speed}] | Total Keys Extracted & Screened: {total_checked:,}")
                sys.stdout.flush()
                last_update_time = now
                
    except KeyboardInterrupt:
        print("\n\n[-] Processing safely suspended via terminal request.")
        process.terminate()

if __name__ == "__main__":
    run_engine()

import os
import psycopg2
from dotenv import load_dotenv

# Load .env file
dotenv_path = os.path.join(os.path.dirname(__file__), 'app', '.env')
if os.path.exists(dotenv_path):
    load_dotenv(dotenv_path)
    print(f"Loaded .env from {dotenv_path}")
else:
    print(f".env not found at {dotenv_path}")

DB_HOST = os.environ.get("DB_HOST", "127.0.0.1")
DB_PORT = os.environ.get("DB_PORT", "5432")
DB_NAME = os.environ.get("DB_NAME", "postgres")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "postgres")

print("\n--- Connection Settings ---")
print(f"Host: {DB_HOST}")
print(f"Port: {DB_PORT}")
print(f"DB:   {DB_NAME}")
print(f"User: {DB_USER}")
print("Password: [HIDDEN]")

print("\nAttempting connection...")
try:
    conn = psycopg2.connect(
        host=DB_HOST,
        port=DB_PORT,
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD,
        connect_timeout=5
    )
    print("✅ SUCCESS: Connected to AlloyDB!")
    
    cur = conn.cursor()
    cur.execute("SELECT version();")
    print(f"DB Version: {cur.fetchone()[0]}")
    
    cur.execute("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public';")
    tables = cur.fetchall()
    print("\nTables found:")
    for t in tables:
        print(f" - {t[0]}")
        
    cur.close()
    conn.close()

except psycopg2.OperationalError as e:
    print("\n❌ CONNECTION FAILED (OperationalError):")
    print(str(e))
    print("\n💡 Troubleshooting Tips:")
    if "Connection refused" in str(e):
        print("1. Is there an AlloyDB Authentication Proxy running locally?")
        print("2. Is the DB_HOST correct? If using PSC, it should be an internal IP (10.x.x.x).")
    elif "timeout expired" in str(e):
        print("1. Check your network/VPN connection to the cloud environment.")
        print("2. Verify Firewall rules or VPC settings.")
except Exception as e:
    print(f"\n❌ UNEXPECTED ERROR: {e}")

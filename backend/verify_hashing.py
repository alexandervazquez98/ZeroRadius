from app.core.security import get_password_hash, verify_password

try:
    print("Testing Hashing...")
    h = get_password_hash("admin")
    print(f"Hash: {h}")
    
    print("Testing Verify...")
    v = verify_password("admin", h)
    print(f"Verify: {v}")
    
    if v:
        print("SUCCESS")
    else:
        print("FAILURE")
except Exception as e:
    print(f"ERROR: {e}")
    import traceback
    traceback.print_exc()

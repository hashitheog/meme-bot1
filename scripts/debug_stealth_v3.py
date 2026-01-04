
from playwright_stealth import stealth
print(f"Debug: stealth module dir: {dir(stealth)}")
try:
    from playwright_stealth.stealth import stealth_async
    print("Found stealth_async in stealth module!")
except ImportError:
    print("stealth_async NOT in stealth module")

try:
    from playwright_stealth.stealth import stealth_sync
    print("Found stealth_sync in stealth module!")
except ImportError:
    print("stealth_sync NOT in stealth module")

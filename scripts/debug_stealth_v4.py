
from playwright_stealth import Stealth
print(f"Dir of Stealth class: {dir(Stealth)}")
print(f"Stealth init args: {Stealth.__init__.__annotations__}")
try:
    s = Stealth()
    print(f"Dir of instance: {dir(s)}")
except Exception as e:
    print(f"Init failed: {e}")

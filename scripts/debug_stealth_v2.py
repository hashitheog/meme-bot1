
import playwright_stealth
print(f"Items in package: {dir(playwright_stealth)}")
try:
    from playwright_stealth import stealth
    print(f"Type of 'stealth': {type(stealth)}")
    print(f"Callable? {callable(stealth)}")
    print(dir(stealth))
except ImportError as e:
    print(f"Import failed: {e}")

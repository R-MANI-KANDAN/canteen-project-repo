"""Diagnostic script to check Razorpay account payment methods and recent payment attempts."""
import requests
import json

key = 'rzp_test_T5yufplvwdBEZI'
secret = 'Dhsx0Do30JdzDqDI6jNPlWze'

print("=" * 60)
print("RAZORPAY ACCOUNT DIAGNOSTIC")
print("=" * 60)

# 1. Check recent payments
print("\n--- Recent Payment Attempts ---")
r = requests.get('https://api.razorpay.com/v1/payments?count=10', auth=(key, secret))
print(f"API Status: {r.status_code}")
if r.status_code == 200:
    data = r.json()
    items = data.get('items', [])
    if not items:
        print("  No payment attempts found.")
    for p in items:
        pid = p.get('id', '?')
        status = p.get('status', '?')
        method = p.get('method', '?')
        err_code = p.get('error_code', 'none')
        err_desc = p.get('error_description', 'none')
        err_reason = p.get('error_reason', 'none')
        amount = p.get('amount', 0)
        print(f"  {pid}: status={status}, method={method}, amount={amount}")
        if err_code != 'none' and err_code is not None:
            print(f"    ERROR: code={err_code}, desc={err_desc}, reason={err_reason}")
else:
    print(f"  Error: {r.text}")

# 2. Check recent orders
print("\n--- Recent Orders ---")
r2 = requests.get('https://api.razorpay.com/v1/orders?count=5', auth=(key, secret))
print(f"API Status: {r2.status_code}")
if r2.status_code == 200:
    data2 = r2.json()
    for o in data2.get('items', []):
        oid = o.get('id', '?')
        status = o.get('status', '?')
        amount = o.get('amount', 0)
        attempts = o.get('attempts', 0)
        print(f"  {oid}: status={status}, amount={amount} paise, attempts={attempts}")

# 3. Try fetching preferences/checkout config
print("\n--- Checkout Preferences ---")
r3 = requests.get(
    f'https://api.razorpay.com/v1/checkout/preferences?key_id={key}',
)
print(f"API Status: {r3.status_code}")
if r3.status_code == 200:
    data3 = r3.json()
    methods = data3.get('methods', {})
    print(f"  Card: {methods.get('card', 'N/A')}")
    print(f"  Netbanking: {type(methods.get('netbanking', 'N/A'))}")
    print(f"  UPI: {methods.get('upi', 'N/A')}")
    print(f"  Wallet: {type(methods.get('wallet', 'N/A'))}")
    
    # Check card sub-types
    card_networks = methods.get('card_networks', {})
    print(f"  Card Networks: {json.dumps(card_networks, indent=4)}")
    
    # Check if international is enabled
    if 'card' in methods and isinstance(methods['card'], bool):
        print(f"  Cards enabled: {methods['card']}")
    
    # Check international
    intl = methods.get('international', False)
    print(f"  International: {intl}")
else:
    print(f"  Error: {r3.text[:200]}")

print("\n" + "=" * 60)
print("DIAGNOSTIC COMPLETE")
print("=" * 60)

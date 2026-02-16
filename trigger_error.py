import requests

BASE_URL = "http://127.0.0.1:5000"
LOGIN_URL = f"{BASE_URL}/login"
EXCEL_URL = f"{BASE_URL}/download_excel"

session = requests.Session()

# Login
response = session.post(LOGIN_URL, data={'password': '3326'})
print(f"Login status: {response.status_code}")
if response.url.endswith('/login'):
    print("Login failed!")
else:
    print("Login successful!")

# Download Excel
print("Requesting Excel...")
response = session.get(EXCEL_URL)
print(f"Download status: {response.status_code}")

if response.status_code == 500:
    print("Reproduced 500 Error!")
else:
    print(f"Success/Other: {response.status_code}")
    print(response.text[:200])

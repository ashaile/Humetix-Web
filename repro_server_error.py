from app import app
import os

def reproduction():
    app.testing = True
    client = app.test_client()

    # Enable logging
    import logging
    logging.basicConfig(level=logging.DEBUG)

    # Login
    print("Logging in...")
    # We need to handle CSRF if it's enabled.
    # But in testing mode, we can sometimes bypass or specificy wtforms invalidation.
    # Ideally, we fetch the login page, extract csrf_token, then post.
    
    # Let's try to access the protected route directly first, verify redirect
    resp = client.get('/download_excel', follow_redirects=True)
    print(f"Direct access result: {resp.status_code}")
    if resp.status_code == 200 and b"login" in resp.data:
         print("Redirected to login as expected.")

    # Login flow
    # 1. Get login page for CSRF
    resp = client.get('/login')
    csrf_token = None
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(resp.data, 'html.parser')
    csrf_input = soup.find('input', {'name': 'csrf_token'})
    if csrf_input:
        csrf_token = csrf_input['value']
        print(f"Found CSRF token: {csrf_token}")
    
    login_data = {'password': '3326'}
    if csrf_token:
        login_data['csrf_token'] = csrf_token
        
    resp = client.post('/login', data=login_data, follow_redirects=True)
    print(f"Login POST result: {resp.status_code}")
    
    if b"humetix_master_99" in resp.data or resp.status_code == 200:
        print("Login successful (probably).")
    
    # 2. Request Excel
    print("Requesting /download_excel...")
    try:
        resp = client.get('/download_excel')
        print(f"Download status: {resp.status_code}")
        if resp.status_code == 500:
            print("Reproduced 500 Error!")
            print(resp.data.decode('utf-8'))
        elif resp.status_code == 200:
             print(f"Success! Content length: {len(resp.data)}")
        else:
             print(f"Other: {resp.status_code}")
    except Exception as e:
        print(f"Exception during request: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    reproduction()

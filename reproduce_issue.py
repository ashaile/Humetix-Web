import requests
import io
from bs4 import BeautifulSoup

def test_submit():
    session = requests.Session()
    apply_url = 'http://127.0.0.1:5000/apply'
    submit_url = 'http://127.0.0.1:5000/submit'
    
    # 1. Get CSRF Token
    response = session.get(apply_url)
    soup = BeautifulSoup(response.text, 'html.parser')
    csrf_token = soup.find('input', {'name': 'csrf_token'})
    
    if not csrf_token:
        print("Could not find CSRF token")
        return

    csrf_token = csrf_token['value']
    print(f"CSRF Token: {csrf_token}")

    # Create dummy image
    img_byte_arr = io.BytesIO()
    img_byte_arr.write(b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82')
    img_byte_arr.seek(0)
    
    files = {
        'id_card': ('test.png', img_byte_arr, 'image/png')
    }
    
    data = {
        'csrf_token': csrf_token,
        'name': 'Test User',
        'birth': '1990-01-01',
        'phone': '010-1234-5678',
        'email': 'test@example.com',
        'address': 'Test Address',
        'height': '170',
        'weight': '60',
        'vision_type': 'Left',
        'vision_value': '1.0',
        'shoes': '260',
        'tshirt': 'L',
        'shift': 'Day',
        'posture': 'Good',
        'overtime': 'Yes',
        'holiday': 'Yes',
        'interview_date': '2026-03-01',
        'start_date': '2026-03-02',
        'agree': 'on',
        'insurance_type': '4대보험'
    }
    
    try:
        response = session.post(submit_url, files=files, data=data)
        print(f"Status Code: {response.status_code}")
        print(f"Response: {response.text[:500]}")
    except Exception as e:
        print(f"Request failed: {e}")

if __name__ == "__main__":
    test_submit()

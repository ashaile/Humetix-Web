def test_home_page(client):
    """메인 페이지 접속 테스트"""
    response = client.get('/')
    assert response.status_code == 200
    assert b"Humetix" in response.data

def test_admin_login_redirect(client):
    """관리자 페이지 비로그인 접근 시 리다이렉트 테스트"""
    response = client.get('/humetix_master_99', follow_redirects=True)
    assert response.status_code == 200
    assert b"Login" in response.data or b"\ub85c\uadf8\uc778" in response.data # "로그인"

def test_404_page(client):
    """존재하지 않는 페이지 404 테스트"""
    response = client.get('/non_existent_page')
    assert response.status_code == 404
    assert b"404" in response.data

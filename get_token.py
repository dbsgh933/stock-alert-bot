import requests

REST_API_KEY = "3d40ead7908a510c36e676d3d0760825"
CLIENT_SECRET = "여기_새로_재발급한_시크릿_권장"
REDIRECT_URI = "http://localhost:8080"

# ✅ 실행할 때마다 새 code를 붙여넣게 만들기
CODE = input("Paste ONLY the code value (without 'code='): ").strip()

url = "https://kauth.kakao.com/oauth/token"

data = {
    "grant_type": "authorization_code",
    "client_id": REST_API_KEY,
    "client_secret": CLIENT_SECRET,
    "redirect_uri": REDIRECT_URI,
    "code": CODE,
}

r = requests.post(url, data=data, timeout=15)
print(r.status_code)
print(r.text)

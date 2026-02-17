import requests

REST_API_KEY = "3d40ead7908a510c36e676d3d0760825"
CLIENT_SECRET = "Bofoqi30YZX7Pdy03qBk0Sl2wgWQMySC"
REDIRECT_URI = "http://localhost:8080"
CODE = "68pcz00zGgghicOsEXpP08o1Q9j1UbFxaf30j8OCbPQ5zpbh2T2RwwAAAAQKFwFQAAABnGkKqdTo6jj-qNQmaA"

url = "https://kauth.kakao.com/oauth/token"

data = {
    "grant_type": "authorization_code",
    "client_id": REST_API_KEY,
    "client_secret": CLIENT_SECRET, 
    "redirect_uri": REDIRECT_URI,
    "code": CODE,
}

r = requests.post(url, data=data)
print(r.status_code)
print(r.text)
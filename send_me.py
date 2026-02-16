import requests
import json

ACCESS_TOKEN = "YVccoWK1diEKSgpd5VMh_J4-zpgAwaGSAAAAAQoNIJsAAAGcZsOAQ_6hmr4nKm-b"

url = "https://kapi.kakao.com/v2/api/talk/memo/default/send"
headers = {"Authorization": f"Bearer {ACCESS_TOKEN}"}

data = {
    "template_object": json.dumps({
        "object_type": "text",
        "text": "📈 20/60일 이평선 알림 테스트 성공!",
        "link": {"web_url": "https://www.naver.com"}
    }, ensure_ascii=False)
}

r = requests.post(url, headers=headers, data=data)
print(r.status_code)
print(r.text)
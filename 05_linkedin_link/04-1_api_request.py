import requests
'''
# 1. API 엔드포인트 URL
url = "https://rapidapi.com"

# 2. 쿼리 스트링 매개변수 (선택 사항)
querystring = {"query": "python", "limit": "10"}

# 3. 인증 헤더 (RapidAPI에서 제공하는 키 사용)
headers = {
	"X-RapidAPI-Key": "94ffeddf6emshf38c86084ac2cb5p13a366jsn3b2869c95dbb",
	"X-RapidAPI-Host": "example-api.p.rapidapi.com"
}

response = requests.get(url, headers=headers)
    

# 추가: 상태 코드와 실제 응답 본문을 출력해봅니다.
#print(f"Status Code: {response.status_code}")
#print(f"Response Text: {response.text}") 

print(f"상태 코드: {response.status_code}")
print(f"응답 본문 길이: {len(response.text)}")
print(f"응답 내용: '{response.text}'") # 본문 내용 확인

# 본문이 비어있는지 확인 후 JSON 파싱 - 추가한 곳
if response.text.strip():
    try:
        data = response.json()
        print(data)
    except Exception as e:
        print("JSON 파싱 에러:", e)
else:
    print("서버에서 빈 응답을 보냈습니다. (Empty Response)")

if response.status_code == 200:
    data = response.json()
else:
    print("요청에 실패했습니다.")

# 4. API 요청 보내기
response = requests.get(url, headers=headers, params=querystring)

# 5. 데이터 확인
if response.status_code == 200:
    data = response.json()
    print(data)
else:
    print(f"Error: {response.status_code}")
'''


url = "https://linkedin-job-search-api.p.rapidapi.com/active-jb-24h"

querystring = {"limit":"10","offset":"0","title_filter":"\"Data Engineer\"","location_filter":"\"United States\" OR \"United Kingdom\"","description_type":"text"}

headers = {
	"x-rapidapi-key": "94ffeddf6emshf38c86084ac2cb5p13a366jsn3b2869c95dbb",
	"x-rapidapi-host": "linkedin-job-search-api.p.rapidapi.com",
	"Content-Type": "application/json"
}

response = requests.get(url, headers=headers, params=querystring)

print(response.json())


import json

# data는 response.json()으로 받은 변수입니다.
print(json.dumps(data, indent=4, ensure_ascii=False))
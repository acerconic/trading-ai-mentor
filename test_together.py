import requests

r = requests.get('https://api.together.xyz/v1/models', headers={'Authorization': 'Bearer key_CYsqM25fVX5Ygt1W4q9wv'})
data = r.json()
if 'data' in data:
    for m in data['data']:
        if 'vision' in m['id'].lower() or 'vl' in m['id'].lower():
            print(m['id'])
elif isinstance(data, list):
    for m in data:
        if 'vision' in m['id'].lower() or 'vl' in m['id'].lower():
            print(m['id'])
else:
    print(data)

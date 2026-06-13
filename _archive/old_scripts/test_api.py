import os
from dotenv import load_dotenv
load_dotenv('.env')
api_key = os.getenv('DEEPSEEK_API_KEY', '')
base_url = os.getenv('OPENAI_BASE_URL', 'https://api.deepseek.com/v1')
model = os.getenv('PANGU_MODEL', 'deepseek-v4-flash')
print(f'API Key: {api_key[:10]}...{api_key[-5:]}')
print(f'Base URL: {base_url}')
print(f'Model: {model}')

try:
    import requests
    headers = {'Authorization': f'Bearer {api_key}', 'Content-Type': 'application/json'}
    models_url = base_url.rstrip('/') + '/models'
    resp = requests.get(models_url, headers=headers, timeout=10)
    print(f'API Status: {resp.status_code}')
    if resp.status_code == 200:
        models = resp.json().get('data', [])
        print(f'Available models: {len(models)}')
        for m in models[:5]:
            print(f'  - {m.get("id", "?")}')
except Exception as e:
    print(f'API Error: {e}')

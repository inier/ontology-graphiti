import json, urllib.request
data = json.loads(urllib.request.urlopen('http://localhost:8000/api/ontology/schema').read())
print(f"Version: {data.get('version')}")
print(f"Entity types: {list(data.get('entity_types', {}).keys())}")
print(f"Roles: {list(data.get('roles', {}).keys())}")
print(f"Business processes: {len(data.get('business_processes', []))}")
print(f"Business rules: {len(data.get('business_rules', []))}")
print(f"Business logics: {len(data.get('business_logics', []))}")
print(f"Business indicators: {len(data.get('business_indicators', []))}")

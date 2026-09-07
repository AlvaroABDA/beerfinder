import json
import os
import requests
from datetime import datetime, timedelta, timezone

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data')

def get_data_file_path(filename):
    return os.path.join(DATA_DIR, filename)

def load_data(filename):
    path = get_data_file_path(filename)
    if not os.path.exists(path):
        return []
    with open(path, 'r', encoding='utf-8') as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            return []

def save_data(filename, data):
    path = get_data_file_path(filename)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

# Geocode using Nominatim (free OpenStreetMap service)
def geocode_address(address):
    """Return (lat, lon) as floats for a given address using Nominatim.
    Returns (None, None) if the service fails or no result.
    """
    url = 'https://nominatim.openstreetmap.org/search'
    params = {'q': address, 'format': 'json', 'limit': 1}
    try:
        resp = requests.get(url, params=params, headers={'User-Agent': 'beerfinder-app'})
        if resp.status_code == 200:
            data = resp.json()
            if data:
                return float(data[0]['lat']), float(data[0]['lon'])
    except Exception:
        pass
    return None, None

def load_users():
    return load_data('users.json')

def save_users(users):
    save_data('users.json', users)

def load_beers():
    return load_data('beers.json')

def save_beers(beers):
    save_data('beers.json', beers)

def load_venues():
    return load_data('venues.json')

def save_venues(venues):
    save_data('venues.json', venues)

def load_availability():
    logs = load_data('availability.json')
    # Filter logs older than 7 days
    now = datetime.now(timezone.utc)
    filtered_logs = []
    for log in logs:
        try:
            log_time = datetime.fromisoformat(log.get('last_updated', '').replace('Z', '+00:00'))
            if now - log_time <= timedelta(days=7):
                filtered_logs.append(log)
        except ValueError:
            pass # Skip invalid dates
    return filtered_logs

def save_availability(availability):
    save_data('availability.json', availability)

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

def load_fabricantes():
    return load_data('fabricantes.json')

def save_fabricantes(fabricantes):
    save_data('fabricantes.json', fabricantes)

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

# --- New Models for Classification & Tags ---

def load_beer_families(): return load_data('beer_families.json')
def save_beer_families(data): save_data('beer_families.json', data)

def load_beer_styles(): return load_data('beer_styles.json')
def save_beer_styles(data): save_data('beer_styles.json', data)

def load_tags(): return load_data('tags.json')
def save_tags(data): save_data('tags.json', data)

def load_beer_tags(): return load_data('beer_tags.json')
def save_beer_tags(data): save_data('beer_tags.json', data)

def load_user_preferences(): return load_data('user_preferences.json')
def save_user_preferences(data): save_data('user_preferences.json', data)

def load_user_beer_preferences(): return load_data('user_beer_preferences.json')
def save_user_beer_preferences(data): save_data('user_beer_preferences.json', data)

def seed_tags_data():
    families = load_beer_families()
    if not families:
        fams = [
            {'id': 1, 'name': 'Lager', 'description': ''},
            {'id': 2, 'name': 'Ale', 'description': ''},
            {'id': 3, 'name': 'Wheat', 'description': ''},
            {'id': 4, 'name': 'Sour', 'description': ''},
            {'id': 5, 'name': 'Belgian', 'description': ''},
            {'id': 6, 'name': 'Specialty', 'description': ''},
            {'id': 7, 'name': 'Sin alcohol', 'description': ''}
        ]
        save_beer_families(fams)
        
    styles = load_beer_styles()
    if not styles:
        s = [
            {'id': 1, 'family_id': 1, 'name': 'Pilsner', 'description': ''},
            {'id': 2, 'family_id': 1, 'name': 'Pale Lager', 'description': ''},
            {'id': 3, 'family_id': 1, 'name': 'Helles', 'description': ''},
            {'id': 4, 'family_id': 1, 'name': 'Kellerbier', 'description': ''},
            {'id': 5, 'family_id': 1, 'name': 'Bock', 'description': ''},
            {'id': 6, 'family_id': 1, 'name': 'Doppelbock', 'description': ''},
            {'id': 7, 'family_id': 1, 'name': 'Märzen', 'description': ''},
            {'id': 8, 'family_id': 1, 'name': 'Vienna Lager', 'description': ''},
            {'id': 9, 'family_id': 2, 'name': 'Pale Ale', 'description': ''},
            {'id': 10, 'family_id': 2, 'name': 'IPA', 'description': ''},
            {'id': 11, 'family_id': 2, 'name': 'Session IPA', 'description': ''},
            {'id': 12, 'family_id': 2, 'name': 'New England IPA', 'description': ''},
            {'id': 13, 'family_id': 2, 'name': 'Double IPA', 'description': ''},
            {'id': 14, 'family_id': 2, 'name': 'West Coast IPA', 'description': ''},
            {'id': 15, 'family_id': 2, 'name': 'Red IPA', 'description': ''},
            {'id': 16, 'family_id': 2, 'name': 'Black IPA', 'description': ''},
            {'id': 17, 'family_id': 2, 'name': 'Amber Ale', 'description': ''},
            {'id': 18, 'family_id': 2, 'name': 'Red Ale', 'description': ''},
            {'id': 19, 'family_id': 2, 'name': 'Brown Ale', 'description': ''},
            {'id': 20, 'family_id': 2, 'name': 'English Bitter', 'description': ''},
            {'id': 21, 'family_id': 2, 'name': 'Porter', 'description': ''},
            {'id': 22, 'family_id': 2, 'name': 'Stout', 'description': ''},
            {'id': 23, 'family_id': 2, 'name': 'Imperial Stout', 'description': ''},
            {'id': 24, 'family_id': 3, 'name': 'Weissbier', 'description': ''},
            {'id': 25, 'family_id': 3, 'name': 'Hefeweizen', 'description': ''},
            {'id': 26, 'family_id': 3, 'name': 'Witbier', 'description': ''},
            {'id': 27, 'family_id': 4, 'name': 'Berliner Weisse', 'description': ''},
            {'id': 28, 'family_id': 4, 'name': 'Gose', 'description': ''},
            {'id': 29, 'family_id': 4, 'name': 'Lambic', 'description': ''},
            {'id': 30, 'family_id': 4, 'name': 'Fruit Sour', 'description': ''},
            {'id': 31, 'family_id': 5, 'name': 'Belgian Blonde', 'description': ''},
            {'id': 32, 'family_id': 5, 'name': 'Belgian Dubbel', 'description': ''},
            {'id': 33, 'family_id': 5, 'name': 'Belgian Tripel', 'description': ''},
            {'id': 34, 'family_id': 5, 'name': 'Belgian Quadrupel', 'description': ''},
            {'id': 35, 'family_id': 5, 'name': 'Saison', 'description': ''},
            {'id': 36, 'family_id': 5, 'name': 'Belgian Strong Ale', 'description': ''},
            {'id': 37, 'family_id': 6, 'name': 'Barleywine', 'description': ''},
            {'id': 38, 'family_id': 6, 'name': 'Smoked Beer', 'description': ''},
            {'id': 39, 'family_id': 6, 'name': 'Experimental', 'description': ''},
            {'id': 40, 'family_id': 7, 'name': 'Sin alcohol', 'description': ''}
        ]
        save_beer_styles(s)
        
    tags = load_tags()
    if not tags:
        t = [
            {'id': 1, 'name': 'Hoppy', 'description': ''},
            {'id': 2, 'name': 'Hazy', 'description': ''},
            {'id': 3, 'name': 'Amarga', 'description': ''},
            {'id': 4, 'name': 'Dulce', 'description': ''},
            {'id': 5, 'name': 'Cítrica', 'description': ''},
            {'id': 6, 'name': 'Tropical', 'description': ''},
            {'id': 7, 'name': 'Frutal', 'description': ''},
            {'id': 8, 'name': 'Tostada', 'description': ''},
            {'id': 9, 'name': 'Malteada', 'description': ''},
            {'id': 10, 'name': 'Ácida', 'description': ''},
            {'id': 11, 'name': 'Suave', 'description': ''},
            {'id': 12, 'name': 'Intensa', 'description': ''},
            {'id': 13, 'name': 'Sin gluten', 'description': ''},
            {'id': 14, 'name': 'Ecológica', 'description': ''},
            {'id': 15, 'name': 'Artesanal', 'description': ''}
        ]
        save_tags(t)

# Run seed on import
seed_tags_data()

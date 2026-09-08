import sys
import os

# Add backend directory to sys.path
sys.path.append(os.path.abspath(os.path.dirname(__file__)))

from app import data_access

BEERS_DATA = [
    # DUMMYBEER
    {"brewery": "DummyBeer", "name": "Arkenstout", "family": "Ale", "style": "Imperial Stout", "tags": ["Tostada", "Intensa", "Dulce", "Chocolate", "Malteada"], "abv": 8.2, "description": "Una stout oscura y profunda como las minas de Arken. Notas intensas a chocolate y malta tostada con un final dulce y reconfortante."},
    {"brewery": "DummyBeer", "name": "Blackforge", "family": "Ale", "style": "Stout", "tags": ["Tostada", "Intensa", "Café", "Malteada"], "abv": 6.4, "description": "Forjada en la oscuridad, esta stout clásica presenta un marcado carácter a café torrefacto y maltas oscuras."},
    {"brewery": "DummyBeer", "name": "Deep Rock Galactic", "family": "Ale", "style": "Porter", "tags": ["Tostada", "Café", "Chocolate", "Suave"], "abv": 5.5, "description": "Perfecta para después de una larga jornada de extracción. Suave, con sutiles toques a café y cacao."},
    {"brewery": "DummyBeer", "name": "Glyphid Gold", "family": "Lager", "style": "Helles", "tags": ["Suave", "Malteada", "Dulce"], "abv": 4.8, "description": "Dorada, brillante y peligrosa. Una Helles fácil de beber con un dulzor maltoso predominante."},
    {"brewery": "DummyBeer", "name": "Leaf Lover's Lager", "family": "Lager", "style": "Pale Lager", "tags": ["Suave", "Refrescante", "Malteada"], "abv": 4.5, "description": "Limpia, crujiente y sumamente refrescante. La opción ideal para limpiar el paladar."},
    {"brewery": "DummyBeer", "name": "Dreadnought IPA", "family": "Ale", "style": "Double IPA", "tags": ["Hoppy", "Amarga", "Intensa", "Cítrica"], "abv": 8.0, "description": "Una bomba de lúpulo indomable. Amargor asertivo con potentes notas cítricas y resinosas."},
    {"brewery": "DummyBeer", "name": "Mactera Haze", "family": "Ale", "style": "New England IPA", "tags": ["Hazy", "Hoppy", "Tropical", "Frutal"], "abv": 6.5, "description": "Zumo de lúpulo en estado puro. Turbia, sedosa y repleta de aromas a frutas tropicales."},
    {"brewery": "DummyBeer", "name": "Sandblasted IPA", "family": "Ale", "style": "West Coast IPA", "tags": ["Hoppy", "Amarga", "Cítrica", "Seca"], "abv": 6.8, "description": "Clásica IPA de la costa oeste. Final seco, amargor punzante y un vendaval de lúpulos cítricos."},
    {"brewery": "DummyBeer", "name": "Space Rig Saison", "family": "Belgian", "style": "Saison", "tags": ["Frutal", "Cítrica", "Especiada", "Seca"], "abv": 6.2, "description": "Elaborada en órbita. Una Saison tradicional con un perfil de levadura especiado, final seco y toque cítrico."},
    {"brewery": "DummyBeer", "name": "Barrel of Fun", "family": "Ale", "style": "Brown Ale", "tags": ["Tostada", "Malteada", "Dulce", "Suave"], "abv": 5.6, "description": "Agradable y reconfortante. Notas a caramelo, frutos secos y un suave fondo tostado."},
    {"brewery": "DummyBeer", "name": "Karl's Revenge", "family": "Lager", "style": "Pilsner", "tags": ["Seca", "Amarga", "Refrescante", "Herbal"], "abv": 5.0, "description": "Una Pilsner con carácter. Amargor noble, notas herbales y un perfil crujiente y seco."},
    {"brewery": "DummyBeer", "name": "Bittermantle", "family": "Ale", "style": "English IPA", "tags": ["Hoppy", "Herbal", "Amarga", "Seca"], "abv": 5.8, "description": "Equilibrio británico clásico. Lúpulos terrosos y herbales sobre una base de malta firme, con un amargor persistente."},
    {"brewery": "DummyBeer", "name": "Pogoplane Juice", "family": "Ale", "style": "New England IPA", "tags": ["Hazy", "Tropical", "Frutal", "Dulce"], "abv": 6.4, "description": "Exuberancia tropical en tu copa. Turbia y dulzona, recuerda a un batido de frutas exóticas."},
    {"brewery": "DummyBeer", "name": "Morkite Milk Stout", "family": "Ale", "style": "Milk Stout", "tags": ["Tostada", "Dulce", "Chocolate", "Cremosa"], "abv": 6.0, "description": "Oscura pero increíblemente sedosa gracias a la adición de lactosa. Notas a batido de chocolate y café con leche."},
    {"brewery": "DummyBeer", "name": "Deep Dive", "family": "Belgian", "style": "Belgian Tripel", "tags": ["Intensa", "Frutal", "Dulce", "Especiada"], "abv": 8.5, "description": "Compleja y alcohólica. Esteres frutales, fenoles especiados y un final dulce pero engañosamente ligero."},

    # FALSATICA
    {"brewery": "Falsatica", "name": "Molly's Red", "family": "Ale", "style": "Red Ale", "tags": ["Tostada", "Malteada", "Dulce"], "abv": 5.2, "description": "Color rubí profundo. Notas a caramelo y galleta con un dulzor maltoso muy equilibrado."},
    {"brewery": "Falsatica", "name": "Karl's Kölsch", "family": "Lager", "style": "Kölsch", "tags": ["Suave", "Refrescante", "Seca", "Cítrica"], "abv": 4.9, "description": "Limpia como una lager, afrutada como una ale. Sutilmente cítrica y sumamente refrescante."},
    {"brewery": "Falsatica", "name": "Rock & Stone IPA", "family": "Ale", "style": "IPA", "tags": ["Hoppy", "Cítrica", "Tropical", "Amarga"], "abv": 6.4, "description": "Sólida como una roca. Explosión de lúpulos americanos con notas a pino, pomelo y frutas de hueso."},
    {"brewery": "Falsatica", "name": "Hoxxes Hazy", "family": "Ale", "style": "New England IPA", "tags": ["Hazy", "Tropical", "Frutal", "Hoppy"], "abv": 6.7, "description": "Opaca y jugosa. Un estallido de lúpulos modernos que aportan aromas a mango, maracuyá y melocotón."},
    {"brewery": "Falsatica", "name": "Driller's Delight", "family": "Ale", "style": "Porter", "tags": ["Tostada", "Café", "Intensa", "Chocolate"], "abv": 6.0, "description": "Para perforar tus sentidos. Oscura y robusta, dominada por maltas tostadas que evocan café expreso y chocolate amargo."},
    {"brewery": "Falsatica", "name": "Scout's Wit", "family": "Wheat", "style": "Witbier", "tags": ["Cítrica", "Frutal", "Suave", "Refrescante"], "abv": 4.7, "description": "Pálida y refrescante. Elaborada con trigo, cilantro y piel de naranja para un perfil cítrico y chispeante."},
    {"brewery": "Falsatica", "name": "Gunner's Gose", "family": "Sour", "style": "Gose", "tags": ["Ácida", "Cítrica", "Suave"], "abv": 4.2, "description": "Ligeramente ácida y sutilmente salada. Una experiencia refrescante y peculiar con un final cítrico."},
    {"brewery": "Falsatica", "name": "Glyphid Sour", "family": "Sour", "style": "Fruit Sour", "tags": ["Ácida", "Frutal", "Tropical"], "abv": 5.0, "description": "Ataque ácido y frutal. Cargada de puré de frutas tropicales sobre una base marcadamente ácida."},
    {"brewery": "Falsatica", "name": "Mission Control", "family": "Belgian", "style": "Belgian Blonde", "tags": ["Frutal", "Dulce", "Suave", "Malteada"], "abv": 6.5, "description": "Elegante y equilibrada. Perfil afrutado suave de levadura belga con una base de malta ligeramente dulce."},
    {"brewery": "Falsatica", "name": "Error 404: Beer Not Found", "family": "Sin alcohol", "style": "Sin alcohol", "tags": ["Suave", "Refrescante", "Cítrica"], "abv": 0.5, "description": "Todo el sabor sin el alcohol. Ligeramente lupulada y refrescante, ideal para cuando no quieres o no puedes."},
    {"brewery": "Falsatica", "name": "Red Sugar Rush", "family": "Ale", "style": "Irish Red Ale", "tags": ["Tostada", "Dulce", "Suave", "Malteada"], "abv": 5.1, "description": "Caramelo y toffee en abundancia. Una Red Ale clásica, suave y reconfortante."},
    {"brewery": "Falsatica", "name": "Dreadnought's Cousin", "family": "Ale", "style": "Triple IPA", "tags": ["Hoppy", "Amarga", "Intensa", "Cítrica"], "abv": 9.2, "description": "Peligrosamente intensa. Un jarabe de lúpulo masivo con fuerte amargor y cuerpo denso y alcohólico."},
    {"brewery": "Falsatica", "name": "Azure Abyss", "family": "Sour", "style": "Berliner Weisse", "tags": ["Ácida", "Cítrica", "Refrescante", "Seca"], "abv": 4.0, "description": "Limpia y punzante acidez láctica. Extremadamente seca y refrescante, con sutiles notas alimonadas."},
    {"brewery": "Falsatica", "name": "Jungle Fungus", "family": "Wheat", "style": "Hefeweizen", "tags": ["Frutal", "Especiada", "Suave", "Refrescante"], "abv": 5.0, "description": "Clásica de trigo alemana. Aromas prominentes a plátano y clavo aportados por su característica levadura."},
    {"brewery": "Falsatica", "name": "Management Approved™", "family": "Ale", "style": "American Pale Ale", "tags": ["Hoppy", "Cítrica", "Floral", "Refrescante"], "abv": 5.6, "description": "El estándar de la casa. Equilibrada, con presencia moderada de maltas caramelo y un claro perfil cítrico y floral."}
]

def run_seed():
    print("Iniciando generación de datos de prueba...")
    
    # Load existing data
    fabricantes = data_access.load_fabricantes()
    families = data_access.load_beer_families()
    styles = data_access.load_beer_styles()
    tags = data_access.load_tags()
    beers = data_access.load_beers()
    beer_tags = data_access.load_beer_tags()
    
    # Track stats
    stats = {
        'fabricantes_added': 0,
        'families_added': 0,
        'styles_added': 0,
        'tags_added': 0,
        'beers_added': 0
    }
    
    # Helpers
    def get_or_create(collection, key_field, name, default_item):
        for item in collection:
            if item.get(key_field, '').lower() == name.lower():
                return item
        
        new_id = max([x.get('id', 0) for x in collection] + [0]) + 1
        new_item = default_item.copy()
        new_item['id'] = new_id
        new_item[key_field] = name
        collection.append(new_item)
        return new_item

    # Create Brewers
    brewery_names = set(b['brewery'] for b in BEERS_DATA)
    for b_name in brewery_names:
        found = False
        for f in fabricantes:
            if f.get('name', '').lower() == b_name.lower():
                found = True
                break
        if not found:
            new_id = max([f.get('id', 0) for f in fabricantes] + [0]) + 1
            fabricantes.append({
                'id': new_id,
                'name': b_name,
                'country': 'Ficción',
                'website': '',
                'description': f'Fabricante ficticio {b_name} para pruebas.',
                'logo': ''
            })
            stats['fabricantes_added'] += 1

    # Process each beer
    for data in BEERS_DATA:
        # Family
        family = get_or_create(families, 'name', data['family'], {'description': ''})
            
        # Style
        style = None
        for s in styles:
            if s.get('name', '').lower() == data['style'].lower():
                style = s
                break
        if not style:
            new_id = max([x.get('id', 0) for x in styles] + [0]) + 1
            style = {'id': new_id, 'family_id': family['id'], 'name': data['style'], 'description': ''}
            styles.append(style)
            stats['styles_added'] += 1

        # Tags
        b_tag_ids = []
        for t_name in data['tags']:
            t = get_or_create(tags, 'name', t_name, {'description': ''})
            b_tag_ids.append(t['id'])

        # Beer
        beer = None
        for b in beers:
            if b.get('name', '').lower() == data['name'].lower() and b.get('brewery', '').lower() == data['brewery'].lower():
                beer = b
                break
                
        if not beer:
            new_id = max([x.get('id', 0) for x in beers] + [0]) + 1
            beer = {
                'id': new_id,
                'name': data['name'],
                'family_id': family['id'],
                'style_id': style['id'],
                'brewery': data['brewery'],
                'abv': str(data['abv']),
                'description': data['description'],
                'image': ''
            }
            beers.append(beer)
            stats['beers_added'] += 1
            
            # Associate tags
            for t_id in b_tag_ids:
                # Check if tag exists for this beer
                exists = any(bt['beer_id'] == new_id and bt['tag_id'] == t_id for bt in beer_tags)
                if not exists:
                    beer_tags.append({'beer_id': new_id, 'tag_id': t_id})

    # To calculate how many unique entities are USED in this batch:
    used_families = set(b['family'] for b in BEERS_DATA)
    used_styles = set(b['style'] for b in BEERS_DATA)
    used_tags = set(t for b in BEERS_DATA for t in b['tags'])

    # Save everything
    data_access.save_fabricantes(fabricantes)
    data_access.save_beer_families(families)
    data_access.save_beer_styles(styles)
    data_access.save_tags(tags)
    data_access.save_beers(beers)
    data_access.save_beer_tags(beer_tags)

    print("\n--- RESULTADOS DEL SEED ---")
    print(f"Número de proveedores creados/usados: {len(brewery_names)} (Nuevos: {stats['fabricantes_added']})")
    print(f"Número de familias utilizadas: {len(used_families)}")
    print(f"Número de estilos utilizados: {len(used_styles)} (Nuevos: {stats['styles_added']})")
    print(f"Número de tags utilizados: {len(used_tags)}")
    print(f"Número de cervezas creadas: {stats['beers_added']} (Total en catálogo: {len(beers)})")
    print("---------------------------\n")

if __name__ == '__main__':
    run_seed()

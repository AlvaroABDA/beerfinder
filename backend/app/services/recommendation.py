import random
from app import data_access

# --- CONSTANTES DE CONFIGURACIÓN ---
WEIGHT_SIMILARITY = 40
WEIGHT_TAGS = 30
WEIGHT_STYLE = 15
WEIGHT_FAMILY = 10
WEIGHT_OTHER = 5

THRESHOLD_INSUFFICIENT = 4
THRESHOLD_INITIAL = 14

EXPLORATION_PERCENTAGE = 0.20

class RecommendationEngine:
    
    @staticmethod
    def build_user_profile(user_id):
        """
        Construye el perfil del usuario agregando frecuencias de sus LIKES y DISLIKES
        y recolectando sus preferencias de tags explícitas.
        """
        # 1. Obtener preferencias de BeerMatch
        all_bm_prefs = data_access.load_user_beer_preferences()
        user_bm_prefs = [p for p in all_bm_prefs if p['user_id'] == user_id]
        
        # 2. Obtener preferencias explícitas de tags
        all_prefs = data_access.load_user_preferences()
        user_tag_prefs = [p for p in all_prefs if p.get('user_id') == user_id and p.get('target_type') == 'TAG']
        
        explicit_liked_tags = {p['target_id'] for p in user_tag_prefs if p.get('preference') == 'LIKE'}
        explicit_disliked_tags = {p['target_id'] for p in user_tag_prefs if p.get('preference') == 'DISLIKE'}
        
        # 3. Cargar cervezas para cruzar datos
        beers = {b['id']: b for b in data_access.load_beers()}
        beer_tags = data_access.load_beer_tags()
        
        # Frecuencias inferidas
        family_freq = {}
        style_freq = {}
        tag_freq = {}
        
        liked_beers = set()
        disliked_beers = set()
        
        for pref in user_bm_prefs:
            beer_id = pref['beer_id']
            preference = pref['preference']
            
            if preference == 'LIKE':
                liked_beers.add(beer_id)
                weight = 1
            else:
                disliked_beers.add(beer_id)
                weight = -1 # Penaliza en el perfil
                
            beer = beers.get(beer_id)
            if not beer:
                continue
                
            # Familia
            f_id = beer.get('family_id')
            if f_id:
                family_freq[f_id] = family_freq.get(f_id, 0) + weight
                
            # Estilo
            s_id = beer.get('style_id')
            if s_id:
                style_freq[s_id] = style_freq.get(s_id, 0) + weight
                
            # Tags
            b_tags = [bt['tag_id'] for bt in beer_tags if bt['beer_id'] == beer_id]
            for t_id in b_tags:
                tag_freq[t_id] = tag_freq.get(t_id, 0) + weight
                
        return {
            'data_count': len(user_bm_prefs),
            'explicit_liked_tags': explicit_liked_tags,
            'explicit_disliked_tags': explicit_disliked_tags,
            'family_freq': family_freq,
            'style_freq': style_freq,
            'tag_freq': tag_freq,
            'liked_beers': liked_beers,
            'disliked_beers': disliked_beers
        }

    @staticmethod
    def calculate_affinity(profile, beer_candidate, beer_tags):
        """
        Calcula el score de afinidad de una cerveza candidata frente al perfil del usuario.
        Retorna (score, dominant_factor_code).
        """
        score = 0
        factors = {'SIMILARITY': 0, 'TAGS': 0, 'STYLE': 0, 'FAMILY': 0}
        
        b_family = beer_candidate.get('family_id')
        b_style = beer_candidate.get('style_id')
        b_tags = {bt['tag_id'] for bt in beer_tags if bt['beer_id'] == beer_candidate['id']}
        
        # --- 1. Afinidad por Familia (10%) ---
        if b_family and b_family in profile['family_freq']:
            freq = profile['family_freq'][b_family]
            if freq > 0:
                factors['FAMILY'] = WEIGHT_FAMILY
            elif freq < 0:
                factors['FAMILY'] = -WEIGHT_FAMILY
        
        # --- 2. Afinidad por Estilo (15%) ---
        if b_style and b_style in profile['style_freq']:
            freq = profile['style_freq'][b_style]
            if freq > 0:
                factors['STYLE'] = WEIGHT_STYLE
            elif freq < 0:
                factors['STYLE'] = -WEIGHT_STYLE
                
        # --- 3. Afinidad por Tags (30%) ---
        tag_score = 0
        tag_matches = 0
        for t_id in b_tags:
            if t_id in profile['explicit_disliked_tags']:
                tag_score -= 15 # Penalización muy fuerte
            elif t_id in profile['explicit_liked_tags']:
                tag_score += 10 # Bonus fuerte
                tag_matches += 1
            elif t_id in profile['tag_freq']:
                # Tag inferido
                freq = profile['tag_freq'][t_id]
                if freq > 0:
                    tag_score += 3
                    tag_matches += 1
                elif freq < 0:
                    tag_score -= 3
                    
        # Normalizar tag_score a MAX_WEIGHT
        factors['TAGS'] = max(-WEIGHT_TAGS, min(WEIGHT_TAGS, tag_score))

        # --- 4. Similitud con LIKES (40%) ---
        # Si coincide fuertemente en tags o en estilo con cervezas que le gustan.
        # Una forma simplificada de calcular la similitud es usar las frecuencias inferidas:
        sim_score = 0
        if b_style and profile['style_freq'].get(b_style, 0) > 0:
            sim_score += 20
        if b_family and profile['family_freq'].get(b_family, 0) > 0:
            sim_score += 5
        sim_score += min(15, tag_matches * 3)
        factors['SIMILARITY'] = min(WEIGHT_SIMILARITY, sim_score)

        # Penalización si pertenece a estilos/familias que detesta sistemáticamente
        if b_style and profile['style_freq'].get(b_style, 0) <= -2:
            factors['SIMILARITY'] -= 20
        
        # Sumar scores
        total_score = sum(factors.values())
        
        # Normalizar de 0 a 100
        # (El score podría ser negativo por las penalizaciones)
        final_score = max(0, min(100, 50 + total_score)) # Base 50, se ajusta con +/-
        
        # Determinar el factor dominante positivo
        dominant = 'NONE'
        max_val = 0
        for k, v in factors.items():
            if v > max_val:
                max_val = v
                dominant = k
                
        if final_score < 30 and (profile['style_freq'].get(b_style, 0) < 0 or any(t in profile['explicit_disliked_tags'] for t in b_tags)):
            dominant = 'PENALIZED'

        return final_score, dominant

    @staticmethod
    def generate_reason(dominant_factor):
        reasons = {
            'SIMILARITY': "Similar a cervezas que te gustaron.",
            'TAGS': "Coincide con tus preferencias de sabor.",
            'STYLE': "Te recomendamos este estilo porque suele coincidir con tus preferencias.",
            'FAMILY': "Comparte familia con otras cervezas que te han gustado.",
            'PENALIZED': "Posible conflicto con tus rechazos anteriores.",
            'NONE': "Podría ser un buen descubrimiento para ti."
        }
        return reasons.get(dominant_factor, reasons['NONE'])

    @staticmethod
    def get_recommendations(user_id, candidate_beers, limit=5):
        """
        Retorna una lista de diccionarios con {beer_id, score, reason}
        """
        profile = RecommendationEngine.build_user_profile(user_id)
        
        # 1. Fallback: Usuario Nuevo
        if profile['data_count'] <= THRESHOLD_INSUFFICIENT:
            # Retornar genérico basado en una mezcla aleatoria (o rating si lo hubiera)
            candidates_copy = list(candidate_beers)
            random.shuffle(candidates_copy)
            selected = candidates_copy[:limit]
            return [
                {'beer_id': b['id'], 'score': random.randint(70, 85), 'reason': "Recomendación general para nuevos usuarios. ¡Valora más cervezas para personalizar!"}
                for b in selected
            ]
            
        # 2. Usuarios con datos
        beer_tags = data_access.load_beer_tags()
        scored_candidates = []
        
        # Excluir las que ya ha valorado (LIKE o DISLIKE)
        already_rated = profile['liked_beers'].union(profile['disliked_beers'])
        
        for beer in candidate_beers:
            if beer['id'] in already_rated:
                continue
                
            score, factor = RecommendationEngine.calculate_affinity(profile, beer, beer_tags)
            scored_candidates.append({
                'beer_id': beer['id'],
                'score': score,
                'factor': factor,
                'reason': RecommendationEngine.generate_reason(factor)
            })
            
        # Ordenar por score desc
        scored_candidates.sort(key=lambda x: x['score'], reverse=True)
        
        # 3. Exploración vs Afinidad
        num_exploration = max(1, int(limit * EXPLORATION_PERCENTAGE)) if len(scored_candidates) >= limit else 0
        num_affinity = limit - num_exploration
        
        top_affinity = scored_candidates[:num_affinity]
        
        # Seleccionar para exploración de la mitad de la tabla (evitando las penalizadas o score muy bajo < 30)
        explorable = [c for c in scored_candidates[num_affinity:] if c['score'] >= 30 and c['factor'] != 'PENALIZED']
        discovery = []
        if explorable and num_exploration > 0:
            discovery = random.sample(explorable, min(num_exploration, len(explorable)))
            for d in discovery:
                d['reason'] = "Sugerencia de descubrimiento para probar algo nuevo."
                
        final_list = top_affinity + discovery
        # Shuffle un poco para que el descubrimiento no esté siempre al final
        random.shuffle(final_list)
        
        # Quitar el factor interno antes de devolver
        for f in final_list:
            if 'factor' in f:
                del f['factor']
                
        return final_list

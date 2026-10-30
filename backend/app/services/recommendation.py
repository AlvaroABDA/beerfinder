import random
from app import data_access
from app.models import Beer

WEIGHT_SIMILARITY = 40
WEIGHT_TAGS = 30
WEIGHT_STYLE = 15
WEIGHT_FAMILY = 10

THRESHOLD_INSUFFICIENT = 3
EXPLORATION_PERCENTAGE = 0.20

# Pesos de señal en Variante B:
# - LIKE (+1.0): probada y aprobada
# - DISLIKE (-1.0): probada y descartada
# - WISHLIST (+0.25): interés declarado ("Quiero probarla"), ayuda en arranque en frío sin eclipsar gustos probados
SIGNAL_WEIGHTS = {
    'LIKE': 1.0,
    'DISLIKE': -1.0,
    'WISHLIST': 0.25,
}


class RecommendationEngine:

    @staticmethod
    def build_user_profile(user_id):
        """Construye el perfil del usuario consultando únicamente SUS preferencias en SQL."""
        user_bm_prefs = data_access.list_user_beer_preferences(user_id)
        user_explicit_prefs = data_access.list_user_palate_preferences(user_id)

        user_tag_prefs = [p for p in user_explicit_prefs if p.get('target_type') == 'TAG']
        explicit_liked_tags = {p['target_id'] for p in user_tag_prefs if p.get('preference') == 'LIKE'}
        explicit_disliked_tags = {p['target_id'] for p in user_tag_prefs if p.get('preference') == 'DISLIKE'}

        family_freq = {}
        style_freq = {}
        tag_freq = {}

        liked_beers = set()
        disliked_beers = set()
        wishlist_beers = set()

        EXPLICIT_WEIGHT = 2.0
        for pref in user_explicit_prefs:
            weight = EXPLICIT_WEIGHT if pref.get('preference') == 'LIKE' else -EXPLICIT_WEIGHT
            if pref.get('target_type') == 'FAMILY':
                family_freq[pref['target_id']] = family_freq.get(pref['target_id'], 0.0) + weight
            elif pref.get('target_type') == 'STYLE':
                style_freq[pref['target_id']] = style_freq.get(pref['target_id'], 0.0) + weight

        rated_ids = [p['beer_id'] for p in user_bm_prefs]
        beers_by_id = (
            {b.id: b.to_dict() for b in Beer.query.filter(Beer.id.in_(rated_ids)).all()}
            if rated_ids else {}
        )
        beer_tags_map = data_access.get_beer_tags_map(rated_ids) if rated_ids else {}

        for pref in user_bm_prefs:
            beer_id = pref['beer_id']
            p_val = pref['preference']
            weight = SIGNAL_WEIGHTS.get(p_val, 0.0)

            if p_val == 'LIKE':
                liked_beers.add(beer_id)
            elif p_val == 'DISLIKE':
                disliked_beers.add(beer_id)
            elif p_val == 'WISHLIST':
                wishlist_beers.add(beer_id)

            beer = beers_by_id.get(beer_id)
            if not beer or weight == 0.0:
                continue

            f_id = beer.get('family_id')
            if f_id:
                family_freq[f_id] = family_freq.get(f_id, 0.0) + weight

            s_id = beer.get('style_id')
            if s_id:
                style_freq[s_id] = style_freq.get(s_id, 0.0) + weight

            for t_id in beer_tags_map.get(beer_id, []):
                tag_freq[t_id] = tag_freq.get(t_id, 0.0) + weight

        return {
            'data_count': len(user_bm_prefs) + len(user_explicit_prefs),
            'explicit_liked_tags': explicit_liked_tags,
            'explicit_disliked_tags': explicit_disliked_tags,
            'family_freq': family_freq,
            'style_freq': style_freq,
            'tag_freq': tag_freq,
            'liked_beers': liked_beers,
            'disliked_beers': disliked_beers,
            'wishlist_beers': wishlist_beers,
        }

    @staticmethod
    def calculate_affinity(profile, beer_candidate, candidate_tag_ids):
        factors = {'SIMILARITY': 0, 'TAGS': 0, 'STYLE': 0, 'FAMILY': 0}

        b_family = beer_candidate.get('family_id')
        b_style = beer_candidate.get('style_id')
        b_tags = set(candidate_tag_ids or [])

        if b_family and b_family in profile['family_freq']:
            freq = profile['family_freq'][b_family]
            if freq > 0:
                factors['FAMILY'] = WEIGHT_FAMILY
            elif freq < 0:
                factors['FAMILY'] = -WEIGHT_FAMILY

        if b_style and b_style in profile['style_freq']:
            freq = profile['style_freq'][b_style]
            if freq > 0:
                factors['STYLE'] = WEIGHT_STYLE
            elif freq < 0:
                factors['STYLE'] = -WEIGHT_STYLE

        tag_score = 0
        tag_matches = 0
        for t_id in b_tags:
            if t_id in profile['explicit_disliked_tags']:
                tag_score -= 15
            elif t_id in profile['explicit_liked_tags']:
                tag_score += 10
                tag_matches += 1
            elif t_id in profile['tag_freq']:
                freq = profile['tag_freq'][t_id]
                if freq > 0:
                    tag_score += 3
                    tag_matches += 1
                elif freq < 0:
                    tag_score -= 3

        factors['TAGS'] = max(-WEIGHT_TAGS, min(WEIGHT_TAGS, tag_score))

        sim_score = 0
        if b_style and profile['style_freq'].get(b_style, 0) > 0:
            sim_score += 20
        if b_family and profile['family_freq'].get(b_family, 0) > 0:
            sim_score += 5
        sim_score += min(15, tag_matches * 3)
        factors['SIMILARITY'] = min(WEIGHT_SIMILARITY, sim_score)

        if b_style and profile['style_freq'].get(b_style, 0) <= -2:
            factors['SIMILARITY'] -= 20

        total_score = sum(factors.values())
        final_score = int(round(max(0, min(100, 50 + total_score))))

        dominant = 'NONE'
        max_val = 0
        for k, v in factors.items():
            if v > max_val:
                max_val = v
                dominant = k

        if final_score < 30 and (
            profile['style_freq'].get(b_style, 0) < 0
            or any(t in profile['explicit_disliked_tags'] for t in b_tags)
        ):
            dominant = 'PENALIZED'

        return final_score, dominant

    @staticmethod
    def generate_reason(dominant_factor):
        reasons = {
            'SIMILARITY': "Similar a cervezas que te gustaron.",
            'TAGS': "Coincide con tus preferencias de sabor.",
            'STYLE': "Este estilo suele encajar con tu paladar.",
            'FAMILY': "De una familia cervecera afín a tus gustos.",
            'PENALIZED': "Posible conflicto con tus descartes anteriores.",
            'NONE': "Podría ser un buen descubrimiento para ti.",
        }
        return reasons.get(dominant_factor, reasons['NONE'])

    @staticmethod
    def score_beers(user_id, candidate_beers):
        if not user_id or not candidate_beers:
            return {b['id']: {'score': 50, 'reason': None} for b in candidate_beers}

        profile = RecommendationEngine.build_user_profile(user_id)
        if profile['data_count'] < THRESHOLD_INSUFFICIENT:
            return {b['id']: {'score': 50, 'reason': None} for b in candidate_beers}

        candidate_ids = [b['id'] for b in candidate_beers]
        tags_map = data_access.get_beer_tags_map(candidate_ids)

        result = {}
        for beer in candidate_beers:
            if beer['id'] in profile['disliked_beers']:
                result[beer['id']] = {'score': 5, 'reason': "Descartada previamente por ti."}
                continue
            score, factor = RecommendationEngine.calculate_affinity(
                profile, beer, tags_map.get(beer['id'], [])
            )
            reason = RecommendationEngine.generate_reason(factor) if factor != 'NONE' else None
            result[beer['id']] = {'score': score, 'reason': reason}
        return result

    @staticmethod
    def get_recommendations(user_id, candidate_beers, limit=5):
        profile = RecommendationEngine.build_user_profile(user_id)
        active_candidates = [b for b in candidate_beers if data_access.is_active(b)]
        already_seen = (
            profile['liked_beers']
            | profile['disliked_beers']
            | profile['wishlist_beers']
        )
        unseen = [b for b in active_candidates if b['id'] not in already_seen]

        if profile['data_count'] < THRESHOLD_INSUFFICIENT:
            candidates_copy = list(unseen)
            random.shuffle(candidates_copy)
            selected = candidates_copy[:limit]
            return [
                {
                    'beer_id': b['id'],
                    'score': random.randint(70, 85),
                    'reason': "Sugerencia inicial. ¡Valora cervezas en Match para afinar tu paladar!"
                }
                for b in selected
            ]

        tags_map = data_access.get_beer_tags_map([b['id'] for b in unseen])

        scored_candidates = []
        for beer in unseen:
            score, factor = RecommendationEngine.calculate_affinity(
                profile, beer, tags_map.get(beer['id'], [])
            )
            scored_candidates.append({
                'beer_id': beer['id'],
                'score': score,
                'factor': factor,
                'reason': RecommendationEngine.generate_reason(factor),
            })

        scored_candidates.sort(key=lambda x: x['score'], reverse=True)

        num_exploration = max(1, int(limit * EXPLORATION_PERCENTAGE)) if len(scored_candidates) >= limit else 0
        num_affinity = limit - num_exploration

        top_affinity = scored_candidates[:num_affinity]
        explorable = [c for c in scored_candidates[num_affinity:] if c['score'] >= 30 and c['factor'] != 'PENALIZED']
        discovery = []
        if explorable and num_exploration > 0:
            discovery = random.sample(explorable, min(num_exploration, len(explorable)))
            for d in discovery:
                d['reason'] = "Sugerencia para descubrir algo nuevo."

        final_list = top_affinity + discovery
        final_list.sort(key=lambda x: x['score'], reverse=True)
        for f in final_list:
            f.pop('factor', None)
        return final_list

BEERMAP — SPEC: MOTOR DE RECOMENDACIÓN V1

Implementa un sistema sencillo de recomendación de cervezas basado en afinidad.

IMPORTANTE:
- No utilizar IA.
- No utilizar Machine Learning.
- No utilizar embeddings.
- No crear sistemas de recomendación externos.
- No introducir nuevas infraestructuras.
- Mantener el sistema determinista y explicable.
- No modificar BeerMatch.
- Utilizar los datos existentes de Beer, BeerFamily, BeerStyle, Tags y UserBeerPreference.

El objetivo es responder:

"¿Qué cervezas disponibles tienen más probabilidades de gustarle a este usuario?"

==================================================
1. DATOS DE ENTRADA
==================================================

Utilizar:

USER
├── BeerMatch LIKE
├── BeerMatch DISLIKE
└── Tag Preferences
    ├── LIKE
    └── DISLIKE

BEER
├── Family
├── Style
└── Tags

No crear todavía una tabla `UserTasteProfile`.

El perfil se calculará inicialmente bajo demanda.

==================================================
2. CANDIDATAS
==================================================

El motor recibirá un usuario y un conjunto de cervezas candidatas.

Inicialmente las candidatas podrán ser:

- cervezas disponibles;
- cervezas cercanas;
- cervezas obtenidas mediante búsqueda.

La disponibilidad y la distancia NO forman parte del cálculo de afinidad.

Son filtros/contexto posteriores.

==================================================
3. AFINIDAD POR FAMILIA
==================================================

Comparar la familia de la cerveza candidata con las familias de las cervezas que el usuario ha marcado LIKE/DISLIKE.

Una coincidencia con una familia que aparece frecuentemente entre sus LIKE aumenta la afinidad.

Una coincidencia con una familia asociada a sus DISLIKE la reduce.

==================================================
4. AFINIDAD POR ESTILO
==================================================

Aplicar el mismo principio al estilo.

El estilo debe tener más peso que la familia.

Ejemplo:

Usuario:

❤️ IPA
❤️ IPA
❤️ Stout
❌ Sour

Candidata:

IPA

→ alta afinidad por estilo.

==================================================
5. AFINIDAD POR TAGS
==================================================

Comparar los tags de la cerveza candidata con:

1. Tags que aparecen en cervezas que el usuario marcó LIKE.
2. Tags que aparecen en cervezas que marcó DISLIKE.
3. Preferencias explícitas del usuario mediante UserTagPreference.

Las coincidencias positivas aumentan el score.

Las coincidencias negativas reducen el score.

Las preferencias explícitas del usuario tienen prioridad sobre las inferencias obtenidas mediante BeerMatch.

==================================================
6. SIMILITUD CON CERVEZAS QUE LE GUSTARON
==================================================

Este será uno de los factores principales.

Comparar la cerveza candidata con las cervezas que el usuario marcó LIKE.

La similitud podrá utilizar:

- misma familia;
- mismo estilo;
- tags compartidos.

Una cerveza candidata muy similar a una cerveza marcada LIKE debe recibir una puntuación elevada.

También se podrá comparar con cervezas DISLIKE para penalizar similitudes.

==================================================
7. SCORE INICIAL
==================================================

Crear un sistema de puntuación de 0 a 100.

Utilizar inicialmente esta distribución orientativa:

SIMILITUD CON LIKES       40%
AFINIDAD DE TAGS          30%
AFINIDAD DE ESTILO        15%
AFINIDAD DE FAMILIA       10%
OTROS                     5%

Los pesos deben estar centralizados en una configuración para poder modificarlos posteriormente.

NO distribuir números mágicos por diferentes archivos.

==================================================
8. PENALIZACIONES
==================================================

Una coincidencia con características asociadas a DISLIKE debe reducir el score.

Especialmente:

- tag explícitamente marcado DISLIKE;
- estilo asociado repetidamente a DISLIKE;
- familia asociada repetidamente a DISLIKE;
- similitud elevada con una cerveza marcada DISLIKE.

Una preferencia explícita DISLIKE debe tener una penalización significativa.

Una cerveza con conflictos fuertes no debe aparecer entre las primeras recomendaciones aunque tenga otras coincidencias positivas.

==================================================
9. CANTIDAD DE DATOS
==================================================

No realizar recomendaciones personalizadas agresivas con usuarios nuevos.

Estados:

0-4 BeerMatch:
    perfil insuficiente.

5-14 BeerMatch:
    perfil inicial.

15+ BeerMatch:
    perfil establecido.

Cuando no exista suficiente información:

Mostrar recomendaciones generales o de descubrimiento.

Cuando exista información suficiente:

Utilizar el motor personalizado.

==================================================
10. EXPLORACIÓN
==================================================

No recomendar únicamente cervezas extremadamente similares.

El sistema deberá reservar una pequeña parte de las recomendaciones para descubrimiento.

Inicialmente:

80% → alta afinidad
20% → descubrimiento

El porcentaje debe estar centralizado en configuración.

El objetivo es evitar:

"Te gusta IPA → solamente te mostramos IPA."

==================================================
11. EXPLICACIÓN
==================================================

Cada recomendación debe poder explicar por qué ha sido seleccionada.

Ejemplos:

"Similar a una cerveza que te gustó."

"Coincide con tus preferencias: Hoppy, Tropical y Hazy."

"Te recomendamos este estilo porque suele coincidir con tus preferencias."

No mostrar información técnica del algoritmo al usuario.

==================================================
12. RESULTADO
==================================================

El motor debe devolver una estructura sencilla similar a:

{
    beer_id,
    score,
    reason
}

Ejemplo:

{
    beer_id: 42,
    score: 87,
    reason: "Similar a una cerveza que te gustó y coincide con tus preferencias."
}

No es necesario almacenar inicialmente este resultado en base de datos.

==================================================
13. DISPONIBILIDAD Y DISTANCIA
==================================================

El motor de afinidad NO debe decidir dónde está la cerveza.

Separar responsabilidades:

RecommendationEngine
    ↓
afinidad personal

BeerSearch / Availability
    ↓
disponibilidad

GeoSearch
    ↓
distancia

La aplicación combinará posteriormente estos resultados.

Ejemplo:

🍺 STTIKA STOUT
87% afinidad
📍 450 m
🟢 Disponible

==================================================
14. USUARIO NUEVO
==================================================

Si el usuario no tiene suficientes datos:

NO inventar preferencias.

Mostrar una recomendación genérica basada en:

- popularidad;
- disponibilidad;
- proximidad;

si esos datos ya existen.

El sistema debe identificar claramente que todavía no tiene suficiente información personalizada.

==================================================
15. ARQUITECTURA
==================================================

Crear un servicio independiente:

`RecommendationService`

Debe recibir:

- user_id
- lista de cervezas candidatas

Y devolver:

- cerveza;
- score;
- explicación.

El controlador NO debe contener la lógica del algoritmo.

No realizar queries directamente desde el controlador.

Utilizar las capas existentes de la aplicación.

==================================================
16. FUTURO
==================================================

Diseñar el código de forma que posteriormente podamos sustituir o ampliar el algoritmo.

Posibles futuras versiones:

V2:
perfil de gustos persistente/cacheado.

V3:
recomendaciones basadas en comportamiento colectivo.

V4:
Machine Learning / modelos avanzados.

NO implementar ninguna de estas versiones ahora.

==================================================
CRITERIO DE FINALIZACIÓN
==================================================

Debe ser posible:

1. Obtener las preferencias BeerMatch de un usuario.
2. Obtener sus preferencias de tags.
3. Analizar las características de sus LIKE/DISLIKE.
4. Compararlas con una cerveza candidata.
5. Calcular un score 0-100.
6. Ordenar varias candidatas por score.
7. Obtener una explicación sencilla.
8. Mantener separada la afinidad de la disponibilidad y geolocalización.

PRINCIPIO:

Primero construir un recomendador sencillo, determinista y comprensible.

No intentar construir Netflix para cerveza.

Construir primero algo que diga:

"Te gustaron estas 5 cervezas.
Esta se parece bastante.
Está a 700 metros.
Prueba esta."
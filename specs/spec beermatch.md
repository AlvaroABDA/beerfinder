BEERMAP — FEATURE: BEERMATCH

Implementa una nueva funcionalidad llamada provisionalmente "BeerMatch".

IMPORTANTE:
- Mantener la aplicación sencilla.
- No modificar innecesariamente la arquitectura existente.
- No implementar todavía ningún motor de recomendación.
- BeerMatch debe limitarse a registrar las preferencias personales del usuario sobre las cervezas que ha probado.
- Mantener la estética definida en `BEERMAP_STYLE_GUIDE.md` y el mockup existente.

==================================================
1. CONCEPTO
==================================================

BeerMatch es el registro personal de cervezas del usuario.

El usuario puede indicar:

❤️ ME GUSTA

o

❌ NO ME GUSTA

La funcionalidad tiene una inspiración deliberadamente similar a Tinder:

- swipe derecha → ME GUSTA
- swipe izquierda → NO ME GUSTA

Pero el sistema debe funcionar también mediante botones, para que no dependamos exclusivamente del gesto swipe.

IMPORTANTE:

BeerMatch es una preferencia PERSONAL.

NO es la valoración pública de la cerveza.

Una cerveza puede tener:

⭐ valoración pública: 4.7

y para un usuario concreto:

❌ NO ME GUSTA

Ambos datos deben mantenerse separados.

==================================================
2. BASE DE DATOS / DATOS
==================================================

Crear una entidad:

`user_beer_preferences`

Campos mínimos:

- id
- user_id
- beer_id
- preference
- created_at
- updated_at

`preference`:

- LIKE
- DISLIKE

Crear una restricción que impida que un usuario tenga dos preferencias simultáneas para la misma cerveza.

Si el usuario cambia de opinión, actualizar el registro existente.

Ejemplo:

Usuario 15
Beer 42
LIKE

Si posteriormente selecciona DISLIKE:

Usuario 15
Beer 42
DISLIKE

No crear otro registro.

==================================================
3. PANTALLA BEERMATCH
==================================================

Añadir una sección accesible desde el menú:

`🍺 BeerMatch`

La pantalla debe presentar una cerveza cada vez.

Conceptualmente:

┌─────────────────────────────┐
│                             │
│          IMAGEN             │
│                             │
│      STTIKA STOUT           │
│      Imperial Stout         │
│      8.2%                   │
│                             │
│      ⭐ 4.6                 │
│                             │
│  Hoppy · Tostada · Intensa  │
│                             │
│                             │
│      ❌          ❤️         │
│     NO ME     ME GUSTA      │
│     GUSTA                   │
└─────────────────────────────┘

La información mostrada debe ser la necesaria para identificar y valorar rápidamente la cerveza.

No mostrar toda la información detallada de la ficha.

==================================================
4. SWIPE
==================================================

Implementar interacción táctil sencilla:

Swipe derecha:
→ LIKE

Swipe izquierda:
→ DISLIKE

La interacción debe ser opcional.

También deben existir botones visibles:

`❌ No me gusta`

`❤️ Me gusta`

Los botones deben funcionar independientemente del swipe.

No utilizar una librería compleja si puede implementarse de forma sencilla con JavaScript.

==================================================
5. CONFIRMACIÓN VISUAL
==================================================

Después de seleccionar una opción:

LIKE:

`❤️ ¡Match!`

DISLIKE:

`❌ Pasamos de esta.`

La animación debe ser breve y discreta.

Después mostrar automáticamente la siguiente cerveza.

No crear un sistema de gamificación complejo.

==================================================
6. HISTORIAL PERSONAL
==================================================

Dentro de BeerMatch debe existir acceso al historial.

Dos categorías:

`❤️ ME GUSTAN`

`❌ NO ME GUSTAN`

Mostrar las cervezas mediante BeerCards.

Ejemplo:

┌──────────────────────┐
│       IMAGEN         │
│ STTIKA STOUT         │
│ Stout · 6.5%         │
│ ❤️ Te gustó         │
│ 📅 07/09/2026        │
└──────────────────────┘

El usuario podrá entrar en la ficha de la cerveza desde la card.

==================================================
7. "YA LA HAS PROBADO"
==================================================

Cuando un usuario consulte una cerveza sobre la que ya existe una preferencia:

Mostrar discretamente:

`❤️ Te gustó`

o:

`❌ No te gustó`

Ejemplo:

STTIKA STOUT

Stout · 6.5%

❤️ Te gustó anteriormente.

Esto debe servir como memoria personal.

==================================================
8. CAMBIO DE OPINIÓN
==================================================

Desde la ficha de una cerveza o desde el historial el usuario podrá cambiar:

❤️ → ❌

o:

❌ → ❤️

No crear registros duplicados.

==================================================
9. LUGAR DONDE SE PROBÓ
==================================================

NO hacer obligatorio este dato en la primera implementación.

Sin embargo, si la cerveza fue descubierta mediante un establecimiento dentro de BeerMap, conservar la posibilidad de asociar posteriormente:

- venue_id
- fecha

No implementar todavía un sistema complejo de historial de consumiciones.

La prioridad es el LIKE/DISLIKE.

==================================================
10. RELACIÓN CON EL FUTURO MOTOR DE RECOMENDACIÓN
==================================================

BeerMatch será una de las fuentes de información para el futuro motor de recomendaciones.

Actualmente:

User
 ↓
BeerMatch
 ↓
LIKE / DISLIKE
 ↓
Beer

Más adelante podremos cruzar esto con:

Beer
 ↓
Family
Style
Tags

y:

User
 ↓
Tag Preferences

para calcular afinidad.

NO implementar todavía ningún algoritmo.

==================================================
11. HOME
==================================================

No convertir BeerMatch en el elemento dominante de la Home.

La Home sigue teniendo como objetivo:

DESCUBRIR
BUSCAR
ENCONTRAR

BeerMatch debe aparecer como una funcionalidad secundaria dentro del menú y, si encaja visualmente, como una pequeña llamada a la acción:

`🍺 ¿Has probado esta?`

==================================================
12. CRITERIOS DE ACEPTACIÓN
==================================================

Un usuario autenticado debe poder:

1. Abrir BeerMatch.
2. Ver una cerveza.
3. Pulsar ❤️ o ❌.
4. Guardar la preferencia.
5. Pasar automáticamente a otra cerveza.
6. Utilizar swipe izquierda/derecha.
7. Consultar sus cervezas favoritas.
8. Consultar sus cervezas rechazadas.
9. Entrar en la ficha de una cerveza ya valorada.
10. Ver si anteriormente indicó LIKE o DISLIKE.
11. Cambiar posteriormente su decisión.

Todo debe funcionar utilizando la sesión actual del usuario.

No implementar funcionalidades adicionales.

==================================================
PRINCIPIO
==================================================

BeerMatch no debe sentirse como un sistema de valoración.

Debe sentirse como:

"Esta cerveza me gusta."

"Esta cerveza no me gusta."

"¿Qué era aquella cerveza que probé hace tres meses?"

→ BeerMap lo recuerda.
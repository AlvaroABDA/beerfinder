# BEERMAP — MVP INICIAL

## Objetivo

Construir una primera versión **funcional y sencilla de BeerMap**, basándote en el mockup proporcionado como referencia principal de diseño y experiencia de usuario.

No queremos construir todavía una arquitectura compleja ni anticipar funcionalidades futuras.

El objetivo de esta primera versión es poder ejecutar la aplicación y utilizarla de principio a fin.

La prioridad es:

> **CERvEZAS + MAPA + DÓNDE ENCONTRARLAS**

---

# 1. Tecnología

Utilizar:

* Python
* Flask
* HTML
* CSS
* JavaScript
* JSON como almacenamiento provisional

**No utilizar todavía una base de datos.**

Los datos deberán estar organizados de forma que posteriormente podamos sustituir los JSON por MySQL sin tener que rehacer toda la aplicación.

---

# 2. Persistencia provisional

Utilizar archivos JSON para almacenar:

```text
users.json
beers.json
venues.json
availability.json
```

La aplicación deberá leer y escribir estos archivos mediante una pequeña capa de acceso a datos.

No mezclar directamente la lectura/escritura de JSON con las rutas Flask.

---

# 3. Usuarios y autenticación

La aplicación requiere autenticación.

Al entrar en BeerMap:

```text
LOGIN
   ↓
aplicación
```

Debe existir:

```text
email / usuario
password
recordarme
login
```

El sistema deberá utilizar **sesiones Flask**.

Implementar correctamente:

* login;
* logout;
* sesión;
* `remember me`;
* usuario actualmente autenticado.

No utilizar JWT en esta versión.

---

# 4. Tipos de usuario

Existirán tres tipos principales:

```text
USER
VENUE
BREWERY
```

Y un administrador:

```text
ADMIN
```

---

# 5. Registro

La pantalla de registro deberá permitir seleccionar:

```text
Usuario
Bar / Establecimiento
Proveedor / Cervecera
```

### Usuario

El registro se aprueba automáticamente.

```text
REGISTER
   ↓
USER
   ↓
ACTIVE
```

Puede utilizar la aplicación inmediatamente.

### Bar

```text
REGISTER
   ↓
VENUE
   ↓
PENDING
   ↓
ADMIN APPROVAL
   ↓
ACTIVE
```

### Proveedor / Cervecera

```text
REGISTER
   ↓
BREWERY
   ↓
PENDING
   ↓
ADMIN APPROVAL
   ↓
ACTIVE
```

Un bar o proveedor pendiente **no tendrá acceso a las funcionalidades que requieran una cuenta verificada**.

---

# 6. Administrador de prueba

Crear automáticamente un administrador inicial:

```text
username: admin
password: admin
role: ADMIN
status: ACTIVE
```

Esto es únicamente para desarrollo y pruebas.

---

# 7. Administración

Crear una pantalla administrativa sencilla.

El administrador deberá poder:

```text
ver usuarios pendientes
ver tipo de cuenta
aprobar cuenta
rechazar cuenta
```

No implementar todavía un sistema de administración complejo.

---

# 8. Cerveza

La cerveza es el objeto principal de BeerMap.

Debe poder crearse y consultarse.

Datos mínimos:

```text
id
name
brewery
style
abv
description
ingredients
gluten_free
tags
image
```

Los usuarios podrán crear nuevas cervezas.

Un proveedor/cervecera verificado también podrá crear cervezas.

---

# 9. Creación de cerveza

Debe existir una funcionalidad:

```text
Añadir cerveza
```

Formulario mínimo:

```text
Nombre
Fabricante
Tipo / estilo
Graduación
Descripción
Ingredientes
¿Sin gluten?
Tags
Imagen
```

Antes de crear una cerveza deberá comprobarse si existe otra con un nombre igual o muy similar.

No implementar todavía un algoritmo complejo de detección de duplicados.

---

# 10. Establecimientos

Un establecimiento deberá tener:

```text
id
name
description
address
city
latitude
longitude
image
owner_user_id
```

La ubicación es **fundamental**.

El establecimiento deberá poder representarse mediante coordenadas geográficas.

---

# 11. Mapa

El mapa es una funcionalidad principal del MVP.

La aplicación deberá poder:

* mostrar establecimientos;
* utilizar coordenadas;
* obtener la ubicación del usuario cuando este conceda permiso;
* calcular distancia aproximada;
* mostrar establecimientos cercanos.

La experiencia principal debe ser:

```text
Cerveza
   ↓
¿Dónde puedo encontrarla?
   ↓
Mapa
   ↓
Establecimientos cercanos
```

Utilizar una solución de mapas sencilla y adecuada para desarrollo.

No introducir todavía infraestructura GIS compleja.

---

# 12. Disponibilidad

Necesitamos representar dónde se ha visto una cerveza.

Un usuario podrá indicar:

```text
"He visto esta cerveza aquí"
```

Esto creará una relación:

```text
BEER
  +
VENUE
  +
fecha/hora
```

También deberá existir un estado sencillo:

```text
AVAILABLE
SOLD_OUT
```

La información deberá permitir posteriormente saber:

```text
Cerveza X
   ↓
Bar Y
   ↓
Vista / disponible
   ↓
hace 2 horas
```

---

# 13. Oferta de un establecimiento

Un bar podrá indicar qué cervezas tiene en su oferta.

Diferenciar:

```text
OFERTA
=
el bar trabaja / ofrece esta cerveza

DISPONIBILIDAD
=
alguien ha confirmado que está disponible
```

No confundir ambos conceptos.

---

# 14. Flujo principal del usuario

El flujo más importante de toda la aplicación debe ser:

```text
LOGIN
  ↓
BUSCAR CERVEZA
  ↓
SELECCIONAR CERVEZA
  ↓
VER INFORMACIÓN
  ↓
"¿DÓNDE ENCONTRARLA?"
  ↓
MAPA
  ↓
ESTABLECIMIENTOS CERCANOS
  ↓
DISPONIBILIDAD
```

Este flujo tiene prioridad sobre cualquier otra funcionalidad.

---

# 15. Frontend

Utilizar el mockup proporcionado como **referencia visual principal**.

No inventar una interfaz completamente diferente.

Mantener:

* diseño sencillo;
* navegación rápida;
* mobile-first;
* pocos elementos;
* información clara;
* protagonismo absoluto de la cerveza;
* mapa fácilmente accesible.

La aplicación debe funcionar correctamente en escritorio y móvil.

---

# 16. Arquitectura mínima

No sobredimensionar el proyecto.

Utilizar una estructura sencilla y comprensible.

Conceptualmente:

```text
Browser
   ↓
Flask
   ↓
Routes
   ↓
Data layer
   ↓
JSON
```

La autenticación/sesiones deberá estar separada de las rutas de negocio.

No crear capas innecesarias si no aportan valor en esta fase.

---

# 17. Preparación para MySQL

Aunque utilizaremos JSON inicialmente, diseñar la capa de datos de forma que posteriormente podamos sustituir:

```text
JSON
```

por:

```text
MySQL
```

sin modificar el frontend ni la lógica principal de la aplicación.

---

# 18. Fuera de alcance

NO implementar todavía:

```text
JWT
OAuth
Google Login
Apple Login
recomendaciones
IA
reputación
ranking
notificaciones
chat
red social
estadísticas avanzadas
Android nativo
motor GIS avanzado
Elasticsearch
microservicios
Docker obligatorio
CI/CD
arquitectura distribuida
```

---

# 19. Criterio de éxito

Consideraremos terminado este MVP cuando podamos:

```text
1. Abrir BeerMap

2. Hacer login

3. Registrar un usuario

4. Registrar un bar/proveedor

5. Aprobarlo desde admin

6. Crear una cerveza

7. Ver la cerveza

8. Asociarla a un establecimiento

9. Indicar que está disponible

10. Ver el establecimiento en el mapa

11. Utilizar nuestra ubicación

12. Ver dónde encontrar la cerveza
```

Todo debe ser **funcional**, aunque visualmente pueda existir margen para mejorar posteriormente.

---

# REGLA PRINCIPAL PARA EL DESARROLLO

**No sobrearquitecturar.**

Si una funcionalidad puede resolverse de forma sencilla, utilizar la solución sencilla.

No implementar funcionalidades futuras "por si acaso".

Primero queremos tener una BeerMap pequeña pero completamente funcional.

Después iremos añadiendo funcionalidades una a una.

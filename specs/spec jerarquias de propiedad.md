# BEERMAP — SPEC 11
# Entidades, propiedad y reclamación
# ACTUALIZACIÓN / REGLAS DE CONTROL

Esta SPEC define el sistema de propiedad de las entidades de BeerMap.

Las entidades actuales son:

    BRAND   → Marca
    BEER    → Cerveza
    VENUE   → Bar / establecimiento

Los usuarios son cuentas.
Las entidades son objetos independientes que pueden tener un propietario.

La propiedad determina quién puede gestionar una entidad.

============================================================
1. CREACIÓN DE ENTIDADES
============================================================

Cualquier usuario registrado puede crear:

- Marcas
- Cervezas
- Bares

Al crear una entidad se debe conservar:

    created_by
    owner_user_id

Inicialmente:

    created_by = usuario creador
    owner_user_id = NULL

Ejemplo:

    Usuario Pepe crea "Bar Kukai"

    created_by = Pepe
    owner_user_id = NULL

La entidad queda HUÉRFANA / SIN PROPIETARIO.

El hecho de haber creado una entidad NO convierte automáticamente al
usuario en propietario.

============================================================
2. ENTIDADES HUÉRFANAS
============================================================

Una entidad sin propietario NO puede ser modificada libremente por
cualquier usuario.

Mientras:

    owner_user_id = NULL

solo pueden modificar sus datos protegidos:

- `created_by`
- administrador

Esto evita vandalismo o modificaciones arbitrarias sobre entidades
que todavía no han sido reclamadas.

Ejemplo:

    Bar Kukai
        created_by = Pepe
        owner_user_id = NULL

Pepe puede editarlo.

Un usuario cualquiera NO puede editarlo.

Admin puede editarlo.

============================================================
3. RECLAMACIÓN
============================================================

Cualquier usuario registrado puede solicitar reclamar una entidad que
actualmente NO tenga propietario.

La reclamación significa:

    "Quiero adquirir la propiedad de esta entidad."

No significa simplemente "verificarla".

La reclamación debe registrar como mínimo:

    entity
    requesting_user
    created_at
    status

Estados:

    PENDING
    APPROVED
    REJECTED

Opcionalmente:

    resolved_by
    resolved_at
    note

============================================================
4. APROBACIÓN
============================================================

Las reclamaciones requieren aprobación administrativa.

Si Admin aprueba:

    entity.owner_user_id = requesting_user

La entidad pasa a estar bajo propiedad del usuario.

Ejemplo:

ANTES:

    Bar Kukai
        created_by = Pepe
        owner_user_id = NULL

DESPUÉS:

    Bar Kukai
        created_by = Pepe
        owner_user_id = Kukai

Pepe sigue siendo el creador original.

Kukai pasa a ser el propietario.

============================================================
5. CONTROL DE UNA ENTIDAD CON PROPIETARIO
============================================================

Cuando:

    owner_user_id != NULL

solo pueden modificar los datos protegidos:

- propietario actual
- administrador

El creador original pierde la capacidad de edición si no es también
el propietario.

Ejemplo:

    created_by = Pepe
    owner_user_id = Kukai

Pepe NO puede modificar libremente la entidad.

Kukai SÍ puede modificarla.

Admin SÍ puede modificarla.

============================================================
6. UNA ENTIDAD → UN PROPIETARIO
============================================================

Una entidad solo puede tener un propietario activo.

Si:

    owner_user_id != NULL

la entidad NO puede ser reclamada por otro usuario mediante el flujo
normal de reclamación.

No implementar todavía transferencias de propiedad entre usuarios.

============================================================
7. REVOCACIÓN DE PROPIEDAD
============================================================

Debe existir un mecanismo administrativo para corregir una propiedad
asignada incorrectamente.

Solo el administrador puede utilizar:

    "Revocar propiedad"

Al revocar:

    owner_user_id = NULL

La entidad vuelve a quedar huérfana y puede volver a ser reclamada.

El historial de la reclamación anterior debe conservarse.

Ejemplo:

    Bar Kukai
        owner_user_id = Troll

Admin detecta que la reclamación fue incorrecta.

Admin pulsa:

    REVOCAR PROPIEDAD

Resultado:

    owner_user_id = NULL

Ahora Kukai puede solicitar reclamar nuevamente el bar.

IMPORTANTE:

La revocación NO elimina la entidad.

La revocación NO modifica `created_by`.

La revocación NO debe borrar el historial de reclamaciones.

============================================================
8. MARCAS Y CERVEZAS
============================================================

Marca y cerveza son entidades independientes.

Ejemplo:

    Marca:
        Laugar
        owner_user_id = Usuario Laugar

    Cerveza:
        Cerveza X
        marca = Laugar
        owner_user_id = NULL

La propiedad de la marca NO implica automáticamente la propiedad de
sus cervezas.

Durante el MVP cada entidad se reclama individualmente.

Por tanto, si Laugar tiene:

    1 marca
    50 cervezas

actualmente tendría que realizar:

    1 claim de la marca
    50 claims de cerveza

Esto es INTENCIONADO para el MVP y NO debe solucionarse mediante una
arquitectura adicional en esta SPEC.

FUTURO:

Se podrá implementar una acción:

    "Reclamar marca y sus cervezas huérfanas"

que permita al propietario de una marca reclamar automáticamente las
cervezas asociadas que todavía no tengan propietario.

NO implementar esta funcionalidad ahora.

============================================================
9. BARES
============================================================

Los bares son entidades de tipo:

    VENUE

Ejemplo:

    Bar Kukai
        type = VENUE
        latitude = ...
        longitude = ...
        owner_user_id = Usuario Kukai

La localización forma parte de los datos del establecimiento.

El propietario es el usuario que controla la entidad.

============================================================
10. USUARIOS Y ROLES
============================================================

NO crear roles específicos como:

    BRAND
    BREWERY
    VENUE
    BEER_OWNER

Un usuario sigue siendo simplemente un usuario.

Puede ser propietario de cualquier número y combinación de entidades.

Ejemplo:

    Usuario X
        ├── Marca X
        ├── Bar X
        └── Cerveza X

Los permisos se derivan de la propiedad de la entidad.

El administrador mantiene control global.

============================================================
11. DUPLICADOS
============================================================

Antes de crear una nueva entidad debe intentarse detectar si ya existe
una entidad equivalente.

Especialmente importante para:

- marcas
- cervezas
- bares

Para el MVP utilizar una búsqueda sencilla por nombre y otros datos
básicos cuando corresponda.

No implementar matching avanzado.

============================================================
12. INTERFAZ
============================================================

Una entidad debe indicar claramente su estado.

SIN PROPIETARIO:

    "Sin propietario"
    "Reclamar entidad"

CON PROPIETARIO:

    "Propiedad verificada"

El usuario propietario debe poder acceder a las opciones de edición.

El creador de una entidad huérfana debe poder editarla.

Un usuario sin relación con la entidad no debe poder editarla.

Admin debe poder editar cualquier entidad.

Para una entidad con propietario NO mostrar una opción normal de
reclamación a otros usuarios.

Admin debe disponer de:

    Aprobar reclamación
    Rechazar reclamación
    Revocar propiedad

============================================================
13. TRAZABILIDAD
============================================================

Mantener siempre:

    created_by

aunque la entidad cambie de propietario.

Ejemplo:

    Entidad:
        Bar Kukai

    created_by:
        Pepe

    owner_user_id:
        Kukai

Si posteriormente Admin revoca la propiedad:

    created_by:
        Pepe

    owner_user_id:
        NULL

El historial de reclamaciones conserva quién tuvo o solicitó la
propiedad anteriormente.

============================================================
14. REGLAS DE PERMISOS — RESUMEN
============================================================

                    EDITAR
------------------------------------------------
Entidad huérfana    created_by + admin
Entidad propiedad   owner + admin
Otro usuario        NO
------------------------------------------------

                    RECLAMAR
------------------------------------------------
Sin propietario     Cualquier usuario
Con propietario     NO
------------------------------------------------

                    REVOCAR
------------------------------------------------
Admin               SÍ
Propietario         NO
Usuario normal      NO
------------------------------------------------

============================================================
15. CRITERIOS DE ACEPTACIÓN
============================================================

El flujo completo debe permitir:

1. Pepe crea "Bar Kukai".
2. `created_by = Pepe`.
3. `owner_user_id = NULL`.
4. Pepe puede editar el bar.
5. Otro usuario NO puede editarlo.
6. Kukai solicita reclamarlo.
7. Admin recibe la solicitud.
8. Admin la aprueba.
9. `owner_user_id = Kukai`.
10. Kukai puede editarlo.
11. Pepe deja de poder editarlo.
12. Otro usuario no puede reclamarlo.
13. Admin puede revocar la propiedad.
14. Tras revocarla:
        owner_user_id = NULL
15. El bar vuelve a estar disponible para reclamación.
16. El historial de la reclamación anterior permanece.
17. `created_by` sigue siendo Pepe.

Repetir el mismo flujo para:

- Marca
- Cerveza

============================================================
16. RESTRICCIONES
============================================================

NO implementar todavía:

- múltiples propietarios
- transferencia entre usuarios
- reclamación automática de productos de una marca
- jerarquías de usuarios
- roles de negocio
- permisos granulares
- reputación
- verificación documental
- disputas complejas
- moderadores

La base del sistema debe ser simplemente:

    USER
      │
      └── owns ──> ENTITY

y:

    ENTITY
      ├── created_by
      └── owner_user_id
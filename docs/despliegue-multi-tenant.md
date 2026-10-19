# Despliegue multi-tenant por esquemas (un solo droplet)

Este documento describe cómo se despliega la plataforma cuando **todos los
clientes viven en el mismo droplet** y se aíslan con un esquema de PostgreSQL
cada uno (`django-tenants`). La graduación de un cliente grande a su propio
droplet es opcional y vive en el [apéndice](#apéndice-graduar-un-cliente-a-su-propio-droplet).

## Modelo de despliegue

- **Un droplet, N esquemas, un solo despliegue.** Un servicio `django`, un
  `celery`, un `celerybeat` y una base de datos. Cada cliente es un esquema
  (`acme`, `marco`, …) dentro de esa única base.
- **El esquema `public` es el registro, no un cliente.** Guarda
  `tenancy_tenant`/`tenancy_domain` y los datos de referencia compartidos
  (`cities_light`, `constance`, los content types). No guarda datos de negocio:
  hay una regla dura, ninguna app de `SHARED_APPS` puede tener una clave foránea
  hacia un modelo de `TENANT_APPS`.
- **El aislamiento de datos es por esquema.** El `search_path` de una petición
  es siempre `<tenant>, public`, así que un cliente nunca ve las tablas de otro.
  Un host sin fila en `tenancy_domain` responde **404**; no hay tenant por
  defecto.
- **El aislamiento de datos no es aislamiento de recursos.** Los esquemas
  separan filas, no CPU, ni conexiones, ni workers: un informe pesado de un
  cliente comparte máquina con los demás. Si un cliente exige garantías de
  rendimiento, la respuesta es graduarlo a su propio droplet
  ([apéndice](#apéndice-graduar-un-cliente-a-su-propio-droplet)), no crear más
  esquemas.
- **La consola de plataforma vive en el tenant `ops`**, no en `public`:
  `auth`, `admin` y `sessions` son apps TENANT y el esquema público no tiene
  sesión. La consola (`/tenancy/`) sólo responde en el subdominio de `ops` y
  exige el permiso `tenancy.*`; en cualquier otro tenant esas rutas dan 404.

## Requisitos de entorno

```bash
# Obligatorio: PostgreSQL (no hay fallback SQLite)
DATABASE_URL=postgres://usuario:clave@db:5432/lubeai

# Host del landing público de la plataforma (el tenant `public`).
PLATFORM_DOMAIN=lubeai.pe

# Sufijo para derivar el host de un cliente cuando se omite --domain.
# Debe quedarse vacío si los clientes usan dominios que no comparten tu dominio.
TENANT_HOST_SUFFIX=lubeai.pe

# Hosts aceptados. El punto inicial es el comodín de subdominios de Django.
# Cubre `acme.lubeai.pe` y `ops.lubeai.pe`. Cada dominio propio de un cliente
# hay que añadirlo aquí explícitamente.
ALLOWED_HOSTS=.lubeai.pe
```

> **Atención con el valor por defecto.** El proyecto trae
> `.midominio.com,localhost` como valor base para que un entorno local arranque
> sin configuración. `config/settings/production.py` **rechaza el arranque** si
> `ALLOWED_HOSTS` está vacío o todavía contiene `midominio.com`: copiar la
> plantilla tal cual y desplegar no funciona, y ese es el comportamiento
> buscado.

### `PLATFORM_DOMAIN` y `TENANT_HOST_SUFFIX` no son lo mismo

Son dos responsabilidades distintas y conviene no confundirlas:

| Ajuste | Para qué sirve | Quién lo usa |
| --- | --- | --- |
| `PLATFORM_DOMAIN` | Host del **landing público** de la plataforma | El `Domain` del tenant `public` |
| `TENANT_HOST_SUFFIX` | **Sólo** para derivar `<slug>.<sufijo>` cuando se omite `--domain` | `provision_tenant` |

El host que realmente enruta una petición es la fila en `tenancy_domain`, no
ninguno de los dos ajustes. Por defecto el sufijo es igual a `PLATFORM_DOMAIN`,
que es lo cómodo cuando todos los clientes son subdominios tuyos. **Si tus
clientes usan dominios ajenos, vacía `TENANT_HOST_SUFFIX`**: entonces
`provision_tenant` exigirá `--domain` en lugar de inventarse un host.

### TLS y reverse proxy (producción)

La aplicación **no termina TLS**: lo hace un reverse proxy (nginx, Caddy,
Traefik) que debe reenviar el esquema y el host originales. Los ajustes ya
declaran `SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")` y
`USE_X_FORWARDED_HOST = True`; sin ellos Django creería que toda petición es
HTTP, generaría enlaces `http://` (recuperación de contraseña, correos de
allauth) y compararía el origen de CSRF con el esquema equivocado.

Certificado: usa uno **comodín** (`*.lubeai.pe`) para cubrir todos los tenants
de una vez. Un cliente con dominio propio necesita su propio certificado.

```nginx
# En el proxy: el host debe llegar intacto a Django.
server {
    listen 443 ssl;
    server_name ~^(?<tenant>.+)\.lubeai\.pe$;

    ssl_certificate     /etc/letsencrypt/live/lubeai.pe/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/lubeai.pe/privkey.pem;

    location / {
        proxy_pass http://django:8000;
        proxy_set_header Host              $host;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header X-Forwarded-For   $proxy_add_x_forwarded_for;
    }
}
```

> **No configures `SESSION_COOKIE_DOMAIN` ni `CSRF_COOKIE_DOMAIN`.** `sessions`,
> `auth` y `admin` son apps TENANT: cada esquema tiene su propia tabla
> `django_session`. Una cookie de sesión compartida entre subdominios sería
> inservible en el esquema de otro tenant, y con una clave coincidente leería la
> **sesión de otro cliente**. Dejarlas sin definir es lo que hace que las
> cookies sean host-only (por subdominio), que es lo correcto. Los ajustes de
> producción **fallan al arrancar** si detectan la variable definida.

`CSRF_TRUSTED_ORIGINS` puede quedarse vacío: se deriva de `ALLOWED_HOSTS` como
orígenes `https`, expandiendo el comodín (`.lubeai.pe` →
`https://*.lubeai.pe` y `https://lubeai.pe`). Si algún cliente usa un dominio
propio que no quieres añadir a `ALLOWED_HOSTS`, declara la lista a mano.

## Un servicio, N esquemas

`docker-compose.yml` define el servicio `django` con la imagen de la aplicación y
la `DATABASE_URL` del droplet. **No hay un servicio por cliente**: añadir un
cliente no toca la infraestructura, sólo crea un esquema.

Las migraciones se aplican en dos pasos, y el orden importa:

```bash
# 1. Sólo apps SHARED, en el esquema public (el registro).
docker compose exec django python manage.py migrate_schemas --shared

# 2. Todas las demás, una vez por esquema de cliente.
docker compose exec django python manage.py migrate_schemas
```

`migrate_schemas` recorre esquema por esquema, así que **el tiempo de despliegue
crece con el número de clientes**. Con 30 esquemas el paso 2 es 30 veces el
trabajo de un cliente; tenlo en cuenta antes de hacerlo en caliente.

## DNS y subdominios

1. Registro **A** comodín para los subdominios de tus clientes:

   ```text
   *.lubeai.pe.  300  IN  A  <IP del droplet>
   ```

   Cubre `acme.lubeai.pe`, `ops.lubeai.pe`, etc. Si un cliente usa un dominio
   propio (`lubricantes-cliente.com`), crea un A/CNAME hacia el mismo droplet y
   registra ese host en el `Domain` del tenant (paso 3).

2. Confirma que `ALLOWED_HOSTS` incluye cada dominio (`.lubeai.pe` cubre los
   subdominios; un dominio propio se añade aparte).

3. Registra el host en el tenant. `provision_tenant` ya crea
   `<slug>.<TENANT_HOST_SUFFIX>` como dominio primario; para añadir otro:

   ```bash
   docker compose exec django python manage.py shell -c "
   from apps.tenancy import models
   tenant = models.Tenant.objects.get(slug='acme')
   models.Domain.objects.create(tenant=tenant, domain='lubricantes-cliente.com', is_primary=False)
   "
   ```

4. Un host sin `Domain` responde **404**. Es el comportamiento esperado, no un
   error de configuración.

### Acceso en desarrollo

Los navegadores resuelven `*.localhost` a `127.0.0.1` por convención, así que
`http://acme.localhost:8000/` funciona sin tocar nada. **`curl` y `wget` no lo
hacen**: ahí hay que enviar el host a mano o usar `/etc/hosts`.

```bash
# Opción A: header explícito
curl -H 'Host: acme.localhost:8000' http://127.0.0.1:8000/

# Opción B: /etc/hosts
127.0.0.1 acme.localhost ops.localhost
```

En local `ALLOWED_HOSTS=*` (valor de `.env.example`) acepta cualquier host, así
que los tres hosts anteriores funcionan sin más.

## Alta de un tenant

### Desde la consola (tenant `ops`)

1. Entrar en `https://ops.lubeai.pe/` con un usuario con permisos
   `tenancy.add_tenant`.
2. Menú **Clientes → Tenants → Crear tenant**.
3. Completar nombre, slug (será el nombre del esquema), tipo, dominio (opcional),
   correo del administrador, **contraseña del administrador** y branding.

La contraseña del administrador es **obligatoria y validada** con los
validadores del proyecto: no existe una contraseña por defecto, y tampoco debe
existir, porque una contraseña publicada en el repositorio no puede levantar un
cliente real.

La creación reutiliza `apps.tenancy.services.provision_tenant`, que deja al
cliente operativo: esquema migrado, dominio, `Site`, organización raíz,
administrador y tipos de componente por defecto.

### Desde la línea de comandos

```bash
docker compose exec django python manage.py provision_tenant \
  --slug acme \
  --name "ACME" \
  --kind final \
  --admin-email admin@acme.pe
```

Si omites `--password` se **genera una contraseña aleatoria y se imprime una
sola vez**; guárdala o ejecuta el comando con `--password '...'`.

`--domain` es opcional mientras `TENANT_HOST_SUFFIX` tenga valor; con el sufijo
vacío es **obligatorio**:

```bash
# Cliente con dominio ajeno a la plataforma
docker compose exec django python manage.py provision_tenant \
  --slug acme --name "ACME" --kind final \
  --admin-email admin@acme.pe --domain lubricantes-cliente.com
```

El comando es idempotente: volver a ejecutarlo actualiza el registro y restaura
lo que falte sin duplicar datos ni recrear el esquema. Un administrador
**preexistente no se modifica**: si necesitas elevar a administrador a una
cuenta que ya existía, hay que pedirlo de forma explícita con `--promote`. Sin
esa bandera, reprovisionar nunca escala privilegios.

Para crear el tenant de operaciones (una sola vez por plataforma):

```bash
docker compose exec django python manage.py provision_tenant \
  --slug ops \
  --name "Operations" \
  --kind platform \
  --admin-email ops@lubeai.pe
```

## Migrar una base legada (cut-over a esquemas)

Una base anterior a `django-tenants` guarda las tablas de negocio
(`TENANT_APPS`) **dentro de `public`**, donde el `search_path` de ningún cliente
las alcanza. Si se provisiona un cliente sobre esa base, `provision_tenant`
crea un esquema vacío y los datos existentes quedan varados en silencio. La
guarda de sistema `tenancy.E001` detecta ese estado (tablas de negocio en
`public` a la vez que `tenancy_tenant`) y **falla** con `DEBUG=False`; en
desarrollo sólo emite un `Warning` (`tenancy.W001`). Este runbook es el
procedimiento que la guarda señala en su `hint`.

> **Orden obligatorio:** respaldo → registrar tenant → mover tablas → reparar
> `django_migrations` → migrar lo pendiente → registrar el `Domain` → verificar
> → limpiar residuos.
> No ejecutar `provision_tenant` sobre el slug legado antes del paso 2: crearía
> el esquema y su organización raíz, y el movimiento de tablas chocaría con
> esas filas recién sembradas.

Se asume que el slug del cliente coincide con el nombre del esquema destino
(por ejemplo `marco`) y que `DATABASE_URL` apunta a la base legada.

### 1. Respaldo

```bash
pg_dump -Fc "$DATABASE_URL" > pre-cutover.dump
```

### 2. Registrar el tenant y crear el esquema vacío

Se crea la fila del registro sin `auto_create_schema`: el esquema se llena con
las tablas movidas, no con esquema recién migrado.

```bash
docker compose exec django python manage.py shell -c "
from apps.tenancy import models
tenant = models.Tenant(slug='marco', name='MARCO', kind='lab')
tenant.auto_create_schema = False
tenant.save()
print('tenant registrado:', tenant.schema_name)
"
psql "$DATABASE_URL" -c 'CREATE SCHEMA marco;'
```

### 3. Mover las tablas de negocio de `public` al esquema del tenant

La lista se genera desde el propio código para no depender de un inventario a
mano: se excluyen las apps que están también en `SHARED_APPS` (por ejemplo
`django_celery_beat`, que vive en ambos), cuyas tablas se quedan en `public`.

```bash
docker compose exec django python manage.py shell -c "
from django.apps import apps
from django.conf import settings
shared = set(settings.SHARED_APPS)
for config in apps.get_app_configs():
    if config.name in settings.TENANT_APPS and config.name not in shared:
        for model in config.get_models():
            print(model._meta.db_table)
" | sort -u > tenant_tables.txt

while read -r table; do
  psql "$DATABASE_URL" -v ON_ERROR_STOP=1 \
    -c "ALTER TABLE public.\"$table\" SET SCHEMA marco;"
done < tenant_tables.txt
```

`ALTER TABLE ... SET SCHEMA` mueve la tabla **con su data, índices y las
secuencias que son propiedad de sus columnas**, así que los `id` conservan su
último valor y no hace falta `setval`. Las claves foráneas que apuntan a tablas
compartidas de `public` (por ejemplo `django_content_type`) siguen apuntando a
`public`, que es exactamente lo que espera un esquema TENANT. Si alguna
secuencia **no** fuera propiedad de una columna, moverla a mano:

```bash
psql "$DATABASE_URL" -c 'ALTER SEQUENCE public.<secuencia> SET SCHEMA marco;'
```

### 4. Reparar `django_migrations` del esquema del tenant

El esquema del cliente necesita su propio libro de migraciones para que
`migrate_schemas` no intente recrear tablas ya presentes. Se copian **sólo** las
filas de apps TENANT desde `public.django_migrations`:

```bash
psql "$DATABASE_URL" <<'SQL'
CREATE TABLE marco.django_migrations (LIKE public.django_migrations INCLUDING ALL);
INSERT INTO marco.django_migrations
SELECT * FROM public.django_migrations
WHERE app IN (
  'auth', 'admin', 'sessions', 'sites', 'messages', 'staticfiles', 'humanize',
  'allauth', 'account', 'easyaudit', 'widget_tweaks', 'django_filters',
  'django_extensions', 'rest_framework', 'authtoken', 'sesame', 'dal',
  'dal_select2', 'tailwind', 'core', 'authentication', 'users', 'theme',
  'organizations', 'equipment', 'reports', 'alerts', 'dashboard'
);
SQL
```

### 5. Aplicar lo pendiente en el tenant

```bash
docker compose exec django python manage.py migrate_schemas --schema=marco
```

Debe aplicar sólo las migraciones que la base legada no tenía registradas (y
crear las tablas de apps que viven en `public` y en cada tenant, como
`django_celery_beat`). Si intenta crear tablas de negocio ya movidas, revisar el
paso 4.

### 6. Registrar el `Domain` del cliente

Este paso es imprescindible y es el que más se olvida: al no haber usado
`provision_tenant` (paso 2), la fila del tenant **no tiene dominio**, y sin
dominio el host responde **404**.

```bash
docker compose exec django python manage.py shell -c "
from apps.tenancy import models
tenant = models.Tenant.objects.get(slug='marco')
models.Domain.objects.get_or_create(tenant=tenant, domain='marco.lubeai.pe', defaults={'is_primary': True})
"
```

### 7. Verificar y limpiar

```bash
# Sin tenancy.E001: no quedan tablas de negocio en public.
docker compose exec django python manage.py check --database default

# public debe listar sólo tablas compartidas.
psql "$DATABASE_URL" -c "SELECT table_name FROM information_schema.tables \
  WHERE table_schema = 'public' ORDER BY table_name;"
```

Cualquier tabla de negocio que hubiera quedado en `public` (por ejemplo, una
añadida a mano después de generar `tenant_tables.txt`) se mueve con el mismo
`ALTER TABLE ... SET SCHEMA` o se elimina si ya se movió su contenido. Retirar
también los registros de `tenancy.Domain`/`tenancy.Tenant` de prueba, si los
hubiera, antes de dar el cut-over por cerrado.

Para llevar el esquema ya movido a **otro** droplet (graduación), usar el dump y
la restauración por esquema del
[apéndice](#apéndice-graduar-un-cliente-a-su-propio-droplet).

## Operación en un solo droplet

### Respaldos

Hay una sola base de datos: si se rompe, se rompe todo. Dos niveles de respaldo,
no uno:

```bash
# Base completa (registro + todos los esquemas).
pg_dump -Fc "$DATABASE_URL" > lubeai-$(date +%F).dump

# Un cliente concreto: permite restaurarlo sin tocar a los demás.
pg_dump -Fc --schema=acme "$DATABASE_URL" > acme-$(date +%F).dump
```

El respaldo por esquema es la ventaja práctica de este modelo: restaurar o
exportar "sólo los datos del cliente X" es un `pg_dump --schema`, no un ejercicio
de filtrar filas. El dump completo **debe** incluir `public`, porque ahí está el
registro de tenants: sin él, los esquemas no se resuelven.

### Coste por cliente

`TenantService.consumption(tenant)` mide el consumo de un esquema (bytes,
filas y conteos por modelo) y se muestra en la consola y en el admin. Es la
base para facturar sin inventar métricas.

### Vecinos ruidosos

Comparten máquina los workers de Celery, el pool de conexiones y la CPU. Lo que
conviene vigilar cuando crezca el número de clientes:

- **Conexiones**: cada worker mantiene las suyas; con varios esquemas y
  `CONN_MAX_AGE` alto, el límite de PostgreSQL es el primer techo que se toca.
- **Cola de Celery**: un cliente que encola un informe pesado retrasa a los
  demás. Si pasa, se separa ese cliente en su propia cola o en su propio
  droplet.
- **Espacio en disco**: el consumo se mide por esquema, así que un cliente que
  crece se ve antes de llenar el disco de todos.

## Suspender y reactivar un cliente

La consola expone **Suspender/Activar** en el listado y en el detalle. La acción
alterna `Tenant.is_active`, que las tareas de Celery ya respetan (sólo procesan
tenants activos).

Para retirarlo **también del tráfico** hay que quitar su `Domain`:

```bash
docker compose exec django python manage.py shell -c "
from apps.tenancy import models
models.Domain.objects.filter(tenant__slug='acme').delete()
"
```

> **No apagues el servicio para retirar un cliente.** Con un solo droplet eso
> tumba a todos los demás tenants. `is_active` detiene el trabajo programado;
> borrar el `Domain` corta el acceso. No hay un tercer mecanismo.

## Consumo por tenant (facturación)

`TenantService.consumption(tenant)` devuelve:

| clave | significado |
| --- | --- |
| `bytes` | suma de `pg_total_relation_size` de las tablas del esquema (datos, índices y TOAST) |
| `rows` | suma de las filas de los modelos facturables |
| `organizations`, `users`, `machines`, `reports` | conteo por modelo dentro del esquema |

Se muestra en el detalle del tenant y en el admin. Ejemplo por consola:

```bash
docker compose exec django python manage.py shell -c "
from apps.tenancy import models, services
tenant = models.Tenant.objects.get(slug='acme')
print(services.TenantService.consumption(tenant))
"
```

Si el esquema de un tenant de registro no existe todavía, `consumption` devuelve
ceros en vez de fallar.

## Apéndice: graduar un cliente a su propio droplet

**No aplica si usas un solo droplet.** Sirve para cuando un cliente exige
aislamiento de recursos (rendimiento garantizado, residencia de datos, o un
contrato que lo pida). El cliente conserva su URL y sus datos: sólo cambia la
`DATABASE_URL` de la instancia que lo sirve, sin tocar código.

1. Crear el droplet y su PostgreSQL, con la misma imagen de la aplicación.
2. Copiar **sólo el esquema** del cliente (el registro de tenants se recrea en el
   destino con `provision_tenant` o se copia `public`):

   ```bash
   pg_dump --schema=acme --no-owner --format=custom "$ORIGEN" > acme.dump
   pg_restore --no-owner --schema=acme -d "$DESTINO" acme.dump
   ```

3. En el droplet nuevo, apuntar la instancia a la base de datos destino
   (`DATABASE_URL=.../lubeai_acme`) y ejecutar `migrate_schemas`.
4. Crear en el destino el registro `Tenant`/`Domain` de `acme` (o restaurar
   `public`), con `ALLOWED_HOSTS` limitado a los hosts de ese cliente, y
   comprobar `https://acme.lubeai.pe/`.
5. Bajar el TTL del DNS, cambiar el registro `acme.lubeai.pe` a la IP nueva y
   retirar el esquema `acme` del droplet original cuando el tráfico haya migrado.

```yaml
# docker-compose.yml del droplet graduado
services:
  django:
    image: lubeai-system-django:latest
    restart: unless-stopped
    environment:
      DJANGO_SETTINGS_MODULE: config.settings.production
      DATABASE_URL: postgres://usuario:clave@db-graduado:5432/lubeai_acme
      PLATFORM_DOMAIN: acme.lubeai.pe
      ALLOWED_HOSTS: acme.lubeai.pe
      # Sin sufijo: en este droplet el cliente es el único tenant y su host
      # nunca se deriva de un slug.
      TENANT_HOST_SUFFIX: ""
```

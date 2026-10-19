# Despliegue multi-tenant por esquemas

Este documento describe cómo se despliega la plataforma cuando cada cliente vive
en su propio esquema de PostgreSQL (`django-tenants`) y cómo se gradúa un cliente
grande a su propio droplet sin tocar código.

## Modelo de despliegue

- **Un droplet puede alojar N esquemas.** El esquema `public` guarda el registro
  de tenants (`tenancy_tenant`, `tenancy_domain`) y los datos compartidos; cada
  cliente tiene su propio esquema (`acme`, `marco`, `ops`, …) con sus usuarios,
  organizaciones, equipos, informes y alertas.
- **El aislamiento es por esquema.** El `search_path` de una petición es siempre
  `<tenant>, public`: un cliente nunca ve las tablas de otro.
- **Un cliente grande se gradúa a su propio droplet** moviendo su esquema a otra
  base de datos y apuntando **solo** su instancia a la nueva `DATABASE_URL`. El
  código, la imagen y las migraciones son los mismos.
- **La consola de plataforma vive en el tenant `ops`**, no en `public`: `auth`,
  `admin` y `sessions` son apps TENANT y el esquema público no tiene sesión. La
  consola (`/tenancy/`) sólo responde en el subdominio de `ops` y exige el
  permiso `tenancy.*`.

## Requisitos de entorno

```bash
# Obligatorio: PostgreSQL (no hay fallback SQLite)
DATABASE_URL=postgres://usuario:clave@db:5432/lubeai

# Dominio de la plataforma: cada cliente se sirve en <slug>.<PLATFORM_DOMAIN>
PLATFORM_DOMAIN=midominio.com

# Hosts aceptados (el punto inicial es el comodín de subdominios de Django)
ALLOWED_HOSTS=.midominio.com,ops.midominio.com
```

## Un servicio por droplet, misma imagen

`docker-compose.yml` define el servicio `django` con la imagen de la aplicación y
la `DATABASE_URL` del droplet. Para un segundo droplet (cliente graduado) se
reutiliza la misma imagen y se cambia únicamente la base de datos, por ejemplo
en un `docker-compose.graduated.yml` o en el `.env` del droplet:

```yaml
services:
  django:
    image: lubeai-system-django:latest
    restart: unless-stopped
    environment:
      DJANGO_SETTINGS_MODULE: config.settings.production
      DATABASE_URL: postgres://usuario:clave@db-graduado:5432/lubeai_marco
      PLATFORM_DOMAIN: midominio.com
      ALLOWED_HOSTS: marco.midominio.com
    command: gunicorn config.wsgi:application --bind 0.0.0.0:8000 --workers 3
```

Cada droplet ejecuta sus propias migraciones:

```bash
docker compose exec django python manage.py migrate_schemas --shared
docker compose exec django python manage.py migrate_schemas
```

## Alta de un tenant

### Desde la consola (tenant `ops`)

1. Entrar en `https://ops.midominio.com/` con un usuario con permisos
   `tenancy.add_tenant`.
2. Menú **Clientes → Tenants → Crear tenant**.
3. Completar nombre, slug (será el nombre del esquema), tipo, dominio (opcional),
   correo del administrador y branding.

La creación reutiliza `apps.tenancy.services.provision_tenant`, que deja al
cliente operativo: esquema migrado, dominio, `Site`, organización raíz,
administrador y tipos de componente por defecto.

### Desde la línea de comandos

```bash
python manage.py provision_tenant \
  --slug acme \
  --name "ACME" \
  --kind final \
  --admin-email admin@acme.pe
# Opcional: --domain acme.midominio.com --default-password '...'
```

El comando es idempotente: volver a ejecutarlo actualiza el registro y restaura
lo que falte sin duplicar datos ni recrear el esquema.

Para crear el tenant de operaciones (una sola vez por plataforma):

```bash
python manage.py provision_tenant \
  --slug ops \
  --name "Operations" \
  --kind platform \
  --admin-email ops@midominio.com
```

## DNS y subdominios

1. Crear un registro **A** comodín en el proveedor de DNS:

   ```text
   *.midominio.com.  300  IN  A  <IP del droplet>
   ```

   Ese comodín cubre todos los tenants (`acme.midominio.com`,
   `ops.midominio.com`, …). Si un cliente usa un dominio propio
   (`lubricantes-cliente.com`), se crea un registro A/CNAME hacia el mismo
   droplet y se registra ese host en el `Domain` del tenant.

2. Confirmar que `ALLOWED_HOSTS` incluye el dominio (`.midominio.com` cubre los
   subdominios).

3. Registrar el host en el tenant. `provision_tenant` ya crea
   `<slug>.<PLATFORM_DOMAIN>` como dominio primario; para añadir otro:

   ```bash
   python manage.py shell -c "
   from apps.tenancy import models
   tenant = models.Tenant.objects.get(slug='acme')
   models.Domain.objects.create(tenant=tenant, domain='lubricantes-cliente.com', is_primary=False)
   "
   ```

4. Un host sin `Domain` responde **404** (no hay tenant por defecto); es el
   comportamiento esperado.

> En desarrollo, `*.localhost` no siempre resuelve. Añadir los hosts a
> `/etc/hosts`:
>
> ```text
> 127.0.0.1 acme.localhost ops.localhost
> ```

## Suspender y reactivar un cliente

La consola expone **Suspender/Activar** en el listado y en el detalle. La acción
alterna `Tenant.is_active`, que las tareas de Celery ya respetan (sólo procesan
tenants activos). El subdominio sigue resolviendo, pero el cliente deja de
recibir trabajo programado; para retirarlo también del tráfico, quitar su
`Domain` o apagar la instancia que lo sirve.

## Consumo por tenant (facturación)

`TenantService.consumption(tenant)` devuelve:

| clave | significado |
| --- | --- |
| `bytes` | suma de `pg_total_relation_size` de las tablas del esquema (datos, índices y TOAST) |
| `rows` | suma de las filas de los modelos facturables |
| `organizations`, `users`, `machines`, `reports` | conteo por modelo dentro del esquema |

Se muestra en el detalle del tenant y en el admin. Ejemplo por consola:

```bash
python manage.py shell -c "
from apps.tenancy import models, services
tenant = models.Tenant.objects.get(slug='acme')
print(services.TenantService.consumption(tenant))
"
```

## Graduar un cliente a su propio droplet

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
   `public`) y comprobar `https://acme.midominio.com/`.
5. Bajar el TTL del DNS, cambiar el registro `acme.midominio.com` a la IP nueva y
   retirar el esquema `acme` del droplet original cuando el tráfico haya migrado.

El cliente conserva su URL y sus datos: sólo cambió la `DATABASE_URL` de la
instancia que lo sirve.

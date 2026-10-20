# MCP para asistentes conectados

La plataforma expone un servidor **Model Context Protocol (MCP)** por cada tenant.
Los clientes pueden conectar ChatGPT, Claude o Gemini para consultar, en modo
lectura, sus equipos, componentes, reportes y alertas.

La implementación usa [`django-mcpz`](https://django-mcpz.readthedocs.io/) 1.1.0
con la app `django_mcpz.oauth`. El servidor habla MCP 2026-07-28 en modo
stateless y también atiende clientes de las versiones 2025 en modo stateless.
Funciona sobre el despliegue WSGI existente (gunicorn); no requiere ASGI.

## Flujo de conexión

1. El usuario entra a **Integraciones → Asistentes conectados** en el panel.
2. Copia la URL del servidor MCP de su tenant:
   `https://<tenant>.dominio.com/mcp`.
3. En ChatGPT, Claude o Gemini añade un conector/servidor MCP personalizado con
   esa URL.
4. El asistente abre la página de autorización de la plataforma. Si el usuario no
   tiene sesión, inicia sesión primero.
5. El usuario revisa el asistente, el destino de la redirección y los módulos a
   los que su rol tiene acceso, y pulsa **Permitir acceso**.
6. El asistente recibe un access token (1 hora) y un refresh token (90 días) y
   puede llamar a las tools.
7. El usuario puede desconectar el asistente desde **Asistentes conectados**.

No se muestra ningún token al usuario: el asistente lo obtiene y renueva por
OAuth. Esto es lo que permite conectar asistentes hospedados que no aceptan un
token pegado manualmente.

## Endpoints

| Endpoint | Uso |
| --- | --- |
| `POST /mcp` | Servidor MCP (JSON-RPC) |
| `GET /oauth/authorize` | Login y consentimiento |
| `POST /oauth/token` | Canje de código y refresh |
| `POST /oauth/register` | Registro dinámico de clientes |
| `POST /oauth/revoke` | Revocación desde el asistente |
| `GET /.well-known/oauth-protected-resource/mcp` | Metadatos del recurso MCP |
| `GET /.well-known/oauth-authorization-server/oauth` | Metadatos del authorization server |
| `GET /integrations/mcp/` | Interfaz de asistentes conectados |

Cada tenant tiene su propio issuer OAuth y sus tokens están ligados al host y a
la URL `/mcp`. Un token emitido para `https://cliente-a/mcp` no funciona en
`https://cliente-b/mcp`.

## Tools disponibles

Todas son de solo lectura (`readOnlyHint`) y están limitadas al subárbol de la
organización del usuario autenticado.

| Tool | Permiso Django | Descripción |
| --- | --- | --- |
| `get_account_overview` | autenticado | Organización, conteos de los módulos permitidos y módulos accesibles |
| `list_equipment` | `equipment.view_machine` | Lista de máquinas, con componentes opcionales |
| `get_equipment` | `equipment.view_machine` | Detalle de máquina y componentes; último reporte y alertas abiertas solo con sus permisos |
| `list_components` | `equipment.view_machine` | Componentes filtrables por máquina |
| `list_reports` | `reports.view_report` | Reportes filtrables por máquina, componente, fechas, estado y condición |
| `get_report` | `reports.view_report` | Reporte con análisis de laboratorio; alertas solo con `alerts.view_alert` |
| `list_alerts` | `alerts.view_alert` | Alertas filtrables por estado, severidad, máquina y fechas |
| `get_alert` | `alerts.view_alert` | Detalle de alerta y reporte origen |

Si el usuario pierde un permiso, la tool deja de aparecer en `tools/list` y las
llamadas directas se rechazan. La organización se toma siempre del usuario
autenticado; ninguna tool acepta un `organization_id` externo. Los datos de un
módulo no se incluyen en tools de otro módulo: por ejemplo, `get_equipment` no
devuelve el último reporte sin `reports.view_report` ni el conteo de alertas sin
`alerts.view_alert`.

## Configuración

En `config/settings/base.py`:

- `MCPZ_OAUTH_ACCESS_TOKEN_LIFETIME`: 1 hora.
- `MCPZ_OAUTH_REFRESH_TOKEN_LIFETIME`: 90 días.
- `MCPZ_OAUTH_DYNAMIC_REGISTRATION`: `True` para que los asistentes se registren
  dinámicamente.
- `MCP_TOOL_DEFAULT_PAGE_SIZE`: 25.
- `MCP_TOOL_MAX_PAGE_SIZE`: 100.

Las apps `django_mcpz`, `django_mcpz.oauth` y `apps.integrations` viven en
`TENANT_APPS`, por lo que las tablas OAuth se crean en cada schema de cliente.

`LOGIN_URL` es `/`. La página de login conserva `next` para volver al
consentimiento después de autenticarse.

## Seguridad

- OAuth 2.1 con PKCE y redirect URIs exactas; no hay client secrets.
- El consentimiento se muestra en cada autorización, incluso si el cliente ya fue
  autorizado, para que el usuario pueda detectar un impostor.
- Los tokens se guardan como digest SHA-256.
- Desactivar un usuario corta sus tokens en la siguiente petición.
- Desconectar un asistente revoca access tokens, refresh tokens y códigos
  pendientes de ese usuario y cliente.
- El acceso es de solo lectura y se filtra por organización y permisos Django.
- En producción se requiere HTTPS. El proyecto ya configura
  `SECURE_PROXY_SSL_HEADER` detrás del proxy.

## Limpieza

`django-mcpz` conserva códigos y tokens expirados/revocados para auditoría. El
comando del proyecto recorre todos los tenants:

```bash
docker compose exec django python manage.py clear_mcp_oauth
```

Programarlo a diario con cron, systemd timer o el mecanismo de tareas del
despliegue.

## Pruebas

```bash
docker compose exec django coverage run manage.py test --settings=config.settings.testing
docker compose exec django coverage report --fail-under=85
```

Las pruebas de integración cubren descubrimiento OAuth, registro dinámico,
consentimiento, canje de código, refresh, revocación, protocolo 2026 y 2025,
aislamiento por tenant/organización y la interfaz de asistentes conectados.

## Prueba manual con `curl`

Con un access token OAuth obtenido por el flujo normal:

```bash
curl -sS https://<tenant>.dominio.com/mcp \
  -H "Authorization: Bearer mcp_..." \
  -H "Content-Type: application/json" \
  -H "MCP-Protocol-Version: 2026-07-28" \
  -H "Mcp-Method: tools/list" \
  -d '{
    "jsonrpc": "2.0",
    "id": 1,
    "method": "tools/list",
    "params": {
      "_meta": {
        "io.modelcontextprotocol/protocolVersion": "2026-07-28",
        "io.modelcontextprotocol/clientCapabilities": {}
      }
    }
  }'
```

Para clientes 2025 se puede omitir `MCP-Protocol-Version` y comenzar con
`initialize`.

## Limitaciones

- Los asistentes hospedados deben aceptar conectores MCP personalizados; la
  disponibilidad depende del plan y la versión de cada asistente.
- No hay tools de escritura ni de reconocimiento de alertas.
- No hay tokens manuales para uso técnico en esta etapa. Si se necesitan, se
  pueden añadir con `django_mcpz.bearer_tokens` como sección “Avanzado”.
- No se ofrece streaming SSE; el servidor responde con JSON, suficiente para
  tools síncronas.

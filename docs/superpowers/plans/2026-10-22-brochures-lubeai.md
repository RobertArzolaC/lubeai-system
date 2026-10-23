# Kit de brochures LubeAI — Plan de implementación

> **Para el agente ejecutor:** usar `superpowers:executing-plans` (o `subagent-driven-development`) y marcar cada paso. El plan está en español; el copy final y el README también. Los comentarios de CSS siguen la regla del repositorio (inglés).

**Objetivo:** Reemplazar los 4 brochures actuales por un kit comercial de 5 documentos coherente con la marca, con el producto real y con el sitio `lubeai.tech`: 4 brochures de 2 páginas por segmento + 1 resumen ejecutivo de una página, un índice del kit y un README de uso.

**Arquitectura:** HTML estático imprimible en `docs/brochures/`, sin Django ni JavaScript. Una sola hoja de estilos compartida (`assets/brochure.css`) define tokens de marca, hojas A4, componentes y reglas de impresión. Cada brochure es un archivo autónomo que enlaza esa hoja y el logo local. La verificación se hace renderizando cada hoja con Playwright en modo print y exportando a PDF para comprobar que no hay recortes.

**Stack:** HTML5 + CSS3 (A4, `@page`, `@media print`), Google Fonts (Montserrat + IBM Plex Sans), Playwright MCP para verificación visual/PDF, `pdfinfo` para contar páginas.

**Insumos:** `docs/summary.md`, `https://lubeai.tech/`, código del repositorio (apps `reports`, `alerts`, `equipment`, `organizations`, `tenancy`, `integrations`).

**Skills aplicadas:** `superpowers:brainstorming` (alcance y decisiones), `copywriting` (ángulo, jerarquía y CTA), `page-cro` (claridad de propuesta, prueba y objeciones), `writing-plans` (este documento).

---

## Decisiones ya tomadas

| Tema | Decisión |
|---|---|
| Ubicación | Solo HTML estático dentro de `docs/brochures/`. No se agregan vistas, URLs ni modelos Django. |
| Canales | **Eliminar WhatsApp y Telegram** de todos los brochures. Las alertas se describen solo por correo y panel. |
| Ingesta | No prometer conexión automática con equipos/LIMS. Redactar como “carga de resultados y PDFs; evaluamos la conexión con su flujo actual según el origen de los datos”. |
| Estructura | 4 brochures de 2 páginas + 1 resumen ejecutivo de 1 página + índice + README. |
| Precios | Ninguno. Sí plazos: demo en una semana, respuesta en menos de 24 horas. |
| Teléfono | Único: **+51 993 373 231**. Eliminar `+51 924 138 978`. |
| Correo | **solutions@lubeai.tech** (no usar el Gmail del pie del sitio). |
| Tratamiento | “Usted” en todo el copy. Sin “tú”, sin imperativos informales. |
| Idioma | Copy, índice y README en español. Nombres de archivo en español, kebab-case. |
| Código sin uso | Se eliminan los 4 HTML antiguos y su CSS duplicado; no queda CSS embebido repetido. |

## Reglas globales de contenido

- **Beneficio antes que función.** Cada bloque responde “qué cambia para el cliente”, no “qué tecnología usamos”.
- **Especificidad.** Nada de “optimice”, “potencie”, “solución integral” como argumento principal. Sí: “un tablero”, “alerta por correo”, “historial por componente”.
- **Sin cifras inventadas.** Solo se permiten: +10,000 análisis procesados, laboratorios en 5 países, demo en una semana, respuesta < 24 h, y la estimación aritmética de 667 h/mes (declarada como estimación).
- **Sin testimonios inventados.** Solo los publicados en `lubeai.tech`, citados textualmente y con la atribución del sitio. El testimonio de Ricardo B. menciona WhatsApp: **no usar**.
- **Sin promesas de disponibilidad.** Nada de “soporte 24/7”, “tiempo real” ni “backups automáticos”.
- **Una sola llamada a la acción por documento**, repetida al final de la página 1 como banda y desarrollada en la página 2.
- **Español neutro de Perú/LatAm**, sin regionalismos. “Reporte” para el documento del laboratorio; “equipo” para la máquina; “componente”; “umbral”; “tablero”.
- Términos técnicos con traducción la primera vez: “marca blanca (white-label)”, “tablero (dashboard)”, “conexión con asistentes de IA (MCP)”.

### Matriz de afirmaciones

**Se puede afirmar (verificado en el repositorio):**
- Tablero con equipos, flotas, sucursales y componentes.
- Normalización de parámetros y unidades de uno o más laboratorios.
- Historial y tendencias por equipo y componente.
- Umbrales configurables por tipo de componente.
- Alertas con severidad, estado, historial, notas y adjuntos; notificación por correo.
- Exportación de reportes a Excel y de gráficas a PDF.
- Jerarquía organizacional multinivel (laboratorio → intermediario → cliente final).
- Branding por organización/tenant: logo y colores.
- Aislamiento de datos por empresa (multi-tenant) y permisos por rol.
- Servidor MCP con OAuth y herramientas de solo lectura para ChatGPT, Claude y Gemini.
- Carga de reportes en PDF y registro estructurado de resultados.

**No afirmar:**
- WhatsApp, Telegram o cualquier canal distinto de correo/panel.
- Ingesta automática desde equipos, LIMS o archivos del laboratorio.
- Backups automáticos, cifrado extremo a extremo, SLA o uptime.
- Precios, descuentos o plazos de implementación distintos de “demo en una semana”.
- “Tiempo real”: usar “actualizado con cada reporte”.

## Sistema de marca

Extraído de `https://lubeai.tech/static/assets/css/landing.css`:

```css
--lubeai-navy: #1a2332;
--lubeai-navy-dark: #0f1823;
--lubeai-navy-light: #2a3847;
--lubeai-gold: #d4a574;
--lubeai-gold-dark: #b8935f;
--lubeai-gold-light: #e5c29d;
--lubeai-amber: #f0a500;
--lubeai-steel: #6b7280;
--lubeai-line: #e5e7eb;
--lubeai-off-white: #f9fafb;
--lubeai-success: #10b981;
--lubeai-danger: #ef5350;
--font-heading: "Montserrat", Arial, sans-serif;   /* 600/700/800 */
--font-body: "IBM Plex Sans", Helvetica, Arial, sans-serif; /* 400/500/600 */
```

- Logo oficial: `https://lubeai.tech/static/assets/images/logos/normal-logo.png` (1.4 MB). Descargarlo y reducirlo a máximo 600 px de ancho con `sips`; el archivo final debe pesar menos de 120 KB.
- No hay logo blanco publicado: sobre fondos navy usar el wordmark tipográfico “LUBEAI” + punto dorado, no una imagen recoloreada.
- Densidad: cuerpo 9.5–10 pt, texto auxiliar 8–8.5 pt, H1 24–28 pt, H2 13–15 pt. Interlineado 1.35–1.45.
- Jerarquía sin depender solo del color: reglas doradas, numeración y bloques con borde.

## Arquitectura de archivos

```
docs/brochures/
├── index.html                  # Portada del kit + instrucciones de impresión
├── clientes-finales.html       # 2 páginas
├── laboratorios.html           # 2 páginas
├── intermediarios.html         # 2 páginas
├── lubeai-360.html             # 2 páginas
├── resumen-ejecutivo.html      # 1 página
├── README.md                   # Uso, edición, reglas de marca y de copy
└── assets/
    ├── brochure.css            # Tokens, hojas A4, componentes, print
    └── logo-lubeai.png         # Logo optimizado
```

Se eliminan: `Brochure Clientes Finales.html`, `Brochure Intermediarios.html`, `Brochure Laboratorios.html`, `Brochure Servicio Integral LubeAI 360.html` (renombrados con `git mv` y luego reescritos).

### Contrato de la hoja de estilos

`brochure.css` debe exponer, como mínimo:

- `.sheet` (210 × 297 mm), `.sheet--cover` si hace falta, `.sheet__body`, `.sheet__foot`.
- `.masthead`, `.logo`, `.tag`, `.kicker`.
- `.hero`, `.hero--navy`, `.hero__title`, `.hero__lede`, `.hero__spark`.
- `.stat-row`, `.stat`, `.stat__value`, `.stat__label`.
- `.section-title`, `.section-title--gold`.
- `.cols-2`, `.panel`, `.panel--gold`, `.panel--navy`.
- `.list-check`, `.list-cross` (marcas con pseudo-elementos, sin iconos externos).
- `.feature-grid`, `.feature`, `.feature__title`.
- `.steps`, `.step`, `.step__num`, `.step__title`.
- `.compare` (tabla), `.compare th`, `.compare td`.
- `.quote`, `.quote__text`, `.quote__author`.
- `.faq`, `.faq dt`, `.faq dd`.
- `.cta`, `.cta__title`, `.cta__actions`, `.contact`.
- `.footer-meta`, `.page-number`, `.no-print`.

Reglas clave:
- `@page { size: A4; margin: 0; }`.
- En pantalla: fondo gris claro, hojas centradas con sombra y separación; ancho fluido por debajo de 820 px (sin altura fija).
- En impresión: `width/height` exactos, `break-after: page`, sin sombras, `print-color-adjust: exact`.
- `overflow: hidden` solo en `.sheet`, nunca en `.sheet__body`; así la verificación de recortes es medible.
- Sin `position: fixed` ni elementos que se repitan mal entre páginas.
- Un solo `<h1>` por hoja; secciones con `<h2>`; listas reales; `lang="es"`.

---

## Copy deck (decisiones cerradas)

Los textos entre comillas son el copy aprobado. El ejecutor puede ajustar puntuación, no el ángulo ni las afirmaciones.

### 1. `clientes-finales.html`

- **Kicker:** “PARA EQUIPOS DE MANTENIMIENTO Y CONFIABILIDAD”
- **H1:** “Todas sus máquinas en un solo tablero. La falla, avisada a tiempo.”
- **Lede:** “LubeAI reúne los reportes de todos sus laboratorios, los normaliza y convierte cada valor fuera de rango en una alerta con responsable y acción.”
- **Stats:** “+10,000 análisis procesados” · “Laboratorios en 5 países” · “1 tablero para toda la operación”
- **El costo de esperar:** el PDF enterrado en el correo; tres laboratorios con tres formatos; el conocimiento en una sola persona; la alerta cuando la falla ya paró la operación.
- **Qué cambia:** un tablero para toda la flota; datos de todos los laboratorios comparables; el umbral correcto por componente; alerta por correo antes de la falla.
- **La plataforma, en concreto (6):** tablero multi-laboratorio; historial y tendencias por componente; umbrales configurables; alertas con seguimiento (severidad, estado, notas, adjuntos); exportación a Excel y PDF; consulta con IA en ChatGPT, Claude o Gemini, solo lectura.
- **Cómo funciona (5):** llega el reporte → se normaliza y vincula → se compara con el umbral → se dispara la alerta por correo → se actúa y queda registro.
- **Antes / Con LubeAI:** PDFs dispersos / un tablero; unidades incompatibles / parámetros normalizados; revisión manual / alerta automática; Excel para tendencias / gráficas por componente; conocimiento en una persona / consulta con IA y permisos por rol.
- **Testimonio:** Jose M., Jefe de Mantenimiento · Planta Industrial, Lima — “Desde que LubeAI normaliza los reportes de los tres laboratorios que usamos, mi equipo dejó de perder horas cada semana en hojas de cálculo. Ahora vemos el estado de todos los equipos en un solo dashboard.”
- **Seguridad:** “Sus datos, en su espacio”: aislamiento por empresa, permisos por rol, PDFs privados, IA de solo lectura con autorización revocable.
- **FAQ (4):** ¿Debo cambiar de laboratorio? No. · ¿Sirve con un solo equipo? Sí. · ¿Quién define los umbrales? Usted, por tipo de componente. · ¿Cuánto tarda? Demo con sus datos en una semana.
- **CTA:** “Vea su operación en LubeAI” / “Solicite una demo con reportes reales. Le mostramos su flota, sus umbrales y sus alertas en una semana.” · Sin costo ni tarjeta · Respuesta en menos de 24 horas · Soporte en español desde Lima, Perú.

### 2. `laboratorios.html`

- **Kicker:** “PARA LABORATORIOS DE ANÁLISIS DE LUBRICANTES”
- **H1:** “Su laboratorio ya tiene los datos. LubeAI los convierte en un servicio que sus clientes usan a diario.”
- **Lede:** “Publique resultados, configure umbrales y entregue alertas y tendencias bajo su propia marca, sin construir software ni sumar horas de digitación.”
- **Lo que frena al laboratorio:** cada informe se arma a mano y se envía por correo; el cliente pide tendencias y recibe otro PDF; las alertas dependen de que alguien revise a tiempo; abrir un portal propio exige un desarrollo que no es el negocio.
- **Su laboratorio, con plataforma:** resultados publicados para cada cliente; alertas automáticas por correo; historial y tendencias de autoservicio; una nueva línea de ingreso recurrente; su marca, no la nuestra.
- **Portal de resultados (6):** cada cliente ve solo su operación; umbrales reutilizables por tipo de componente; alertas al responsable; historial y tendencias sin Excel; marca blanca; consulta con IA de solo lectura.
- **Cómo funciona (5):** recibe la orden y la muestra → registra los resultados → define umbrales → publica y alerta → el cliente consulta y actúa.
- **Impacto (declarado como estimación):** “Si hoy procesa 5,000 reportes al mes y dedica 8 minutos a cada uno, son cerca de 667 horas de trabajo repetitivo. Ese es el tiempo que LubeAI devuelve a su equipo.”
- **Nueva línea de ingreso:** revenda a clientes finales o intermediarios; usted define sus precios; su cartera sigue siendo suya; sin desarrollo.
- **Seguridad:** aislamiento por laboratorio, permisos por rol, PDFs privados, IA de solo lectura.
- **FAQ (5):** ¿Reemplaza mi LIMS? No, se suma a su operación. · ¿Debo cambiar mi forma de trabajar? No al inicio. · ¿Puedo usar mi marca? Sí, logo y colores. · ¿Mis clientes ven datos de otros? No. · ¿Cómo empiezo? Demo con un reporte real y carga piloto.
- **CTA:** “Traiga un reporte real” / “Le mostramos cómo se vería publicado, con su marca, y qué alertas generaría.”

### 3. `intermediarios.html`

- **Kicker:** “PARA DISTRIBUIDORES, CONSULTORES Y PARTNERS”
- **H1:** “Venda monitoreo de condición sin construir ni operar una plataforma.”
- **Lede:** “LubeAI le entrega la tecnología, el aislamiento de datos y el soporte. Usted aporta la relación comercial y define su margen.”
- **El PDF ya no diferencia:** su cliente recibe el mismo informe de tres proveedores; pide tablero y recibe un archivo; competir en tecnología exige desarrollo y soporte; cada cliente nuevo suma carga operativa.
- **Su negocio, un nivel arriba:** marca propia sobre una plataforma lista; clientes finales y sub-intermediarios bajo el mismo panel; ingreso recurrente; escala sin sumar personal técnico; diferenciación real.
- **Qué obtiene (6):** marca blanca; jerarquía multinivel; panel único de cartera; tableros y alertas para sus clientes; sin desarrollo ni servidores; acompañamiento y material comercial.
- **Cómo funciona (5):** define su oferta → abrimos su espacio con su marca → incorpora clientes, equipos y usuarios → sus clientes reciben accesos y alertas → escala la cartera.
- **Qué incluye la alianza:** plataforma marca blanca, onboarding, capacitación comercial y técnica, soporte en español, material de venta, ruta para sub-intermediarios.
- **Su margen, sus reglas:** usted fija el precio a su cliente; LubeAI cobra por volumen/plan; sin inversión en desarrollo; su cartera es suya.
- **Stats:** +10,000 análisis · 5 países · demo en una semana.
- **FAQ (4):** ¿Necesito laboratorio propio? No. · ¿Puedo vender a otros intermediarios? Sí. · ¿Quién da el soporte? LubeAI; usted mantiene la relación comercial. · ¿Cuánto tardo en lanzar? Demo en una semana; alta y carga piloto coordinadas.
- **CTA:** “Armemos su plan de alianza” / “Una reunión de 30 minutos para dimensionar su cartera y definir su oferta.”

### 4. `lubeai-360.html`

- **Kicker:** “SERVICIO INTEGRAL: ANÁLISIS + PLATAFORMA”
- **H1:** “Un solo proveedor para el análisis y para las decisiones.”
- **Lede:** “LubeAI 360 combina el análisis de sus muestras con la plataforma que convierte los resultados en alertas, tendencias y acciones concretas.”
- **Cuando el análisis vive en piezas sueltas:** la muestra por un lado y el informe por otro; el PDF llega después de la reunión; nadie conecta el resultado con el historial; cambiar de proveedor es empezar de cero.
- **Qué incluye (6):** plan de muestreo; logística coordinada; análisis de laboratorio; resultados en plataforma; alertas y seguimiento; acompañamiento técnico.
- **Cómo funciona (5):** definimos el plan de muestreo → coordinamos la recolección → analizamos las muestras → publicamos en su tablero → alertamos y priorizamos la acción.
- **Comparativa Laboratorio tradicional / LubeAI 360:** informe PDF / tablero con historial; alerta manual / alerta automática por correo; sin tendencias / tendencias por componente; soporte puntual / acompañamiento técnico; varios proveedores / un solo contrato.
- **Para quién:** empresas sin laboratorio propio; operaciones con equipos críticos; equipos de mantenimiento sin especialista dedicado; quien quiere consolidar proveedores.
- **Cobertura:** “Coordinamos la logística según ubicación y volumen; confirmamos cobertura en la evaluación.” (No prometer cobertura nacional.)
- **FAQ (5):** ¿Puedo seguir con mi laboratorio actual? Sí. · ¿Quién toma la muestra? Lo coordinamos con su equipo. · ¿Qué cubre el contrato? Muestreo, análisis, plataforma, alertas y acompañamiento. · ¿Hay cobertura en mi planta? Se confirma en la evaluación. · ¿En cuánto tiempo veo resultados? Su tablero queda operativo desde el inicio; la primera muestra sigue el plan acordado.
- **CTA:** “Solicite una evaluación de su plan de muestreo” / “Revisamos sus equipos, puntos críticos y frecuencia ideal antes de cotizar.”

### 5. `resumen-ejecutivo.html` (1 página)

- **H1:** “Del reporte de laboratorio a la decisión.”
- **Lede:** “LubeAI centraliza el análisis de lubricantes, normaliza los datos de uno o más laboratorios y convierte cada valor fuera de rango en una alerta accionable.”
- **Cuatro perfiles:** Laboratorio (publique resultados y abra una nueva línea de ingreso) · Intermediario (revenda con su marca y escale sin operar software) · Cliente final (un tablero para todos sus equipos y laboratorios) · LubeAI 360 (análisis y plataforma bajo un solo contrato).
- **El problema en tres líneas:** PDFs dispersos; formatos incompatibles; alertas tardías.
- **La plataforma (6):** tablero, umbrales, alertas por correo, tendencias, exportación, IA.
- **En 5 pasos:** llega el reporte → se normaliza → se compara con el umbral → se alerta → se actúa.
- **Prueba:** +10,000 análisis procesados · laboratorios en 5 países · demo en una semana · respuesta < 24 h.
- **CTA:** “Solicite una demo personalizada” + contacto. Nota: “Pida el brochure de su perfil.”

### 6. `index.html`

- Título: “Kit comercial LubeAI”.
- Subtítulo: “Cinco documentos para explicar la plataforma según con quién está hablando.”
- Tarjetas: los 5 documentos, con una línea de “para quién” y enlace “Abrir documento”.
- Bloque de instrucciones en español: imprimir a PDF en A4, márgenes “Ninguno”, activar “Gráficos de fondo”, compartir la carpeta `brochures/` o el PDF (no solo el HTML).
- Sin llamadas a la acción comerciales; es una página interna de ventas.

---

## Tareas

### Tarea 1: Sistema de diseño y assets

**Archivos:**
- Crear: `docs/brochures/assets/brochure.css`
- Crear: `docs/brochures/assets/logo-lubeai.png`

**Interfaces:**
- Produce: todas las clases listadas en “Contrato de la hoja de estilos”, usadas por las tareas 2–7.

- [ ] Descargar el logo y optimizarlo:
  ```bash
  mkdir -p docs/brochures/assets
  curl -L -o /tmp/lubeai-logo.png https://lubeai.tech/static/assets/images/logos/normal-logo.png
  sips -Z 600 /tmp/lubeai-logo.png --out docs/brochures/assets/logo-lubeai.png
  ```
- [ ] Comprobar el resultado: `du -h docs/brochures/assets/logo-lubeai.png` debe dar menos de 120 KB y el logo debe verse nítido sobre blanco.
- [ ] Escribir `brochure.css` con los tokens, la hoja A4, los componentes y las reglas de impresión del contrato. Incluir el import de Google Fonts con `display=swap` y fallbacks.
- [ ] Verificar que el CSS no tenga colores fuera de los tokens de marca:
  ```bash
  grep -nE "#(0f172a|d97706|1e293b|64748b|334155|475569|e2e8f0|f8fafc)" docs/brochures/assets/brochure.css
  ```
  Esperado: sin resultados.

### Tarea 2: Brochure de clientes finales

**Archivos:**
- Renombrar: `docs/brochures/Brochure Clientes Finales.html` → `docs/brochures/clientes-finales.html`
- Reescribir el contenido completo.

**Interfaces:**
- Consume: `assets/brochure.css`, `assets/logo-lubeai.png`.

- [ ] `git mv "docs/brochures/Brochure Clientes Finales.html" docs/brochures/clientes-finales.html`
- [ ] Reescribir el archivo con 2 `.sheet`, el copy deck 1 y el pie con teléfono/email/web y “1 / 2”, “2 / 2”.
- [ ] Servir y renderizar:
  ```bash
  python3 -m http.server 8765 --directory docs/brochures
  ```
  Abrir `http://localhost:8765/clientes-finales.html`, revisar las 2 hojas y capturar pantalla.
- [ ] Verificar recortes en modo print. En Playwright: `emulateMedia({media:'print'})`, esperar `document.fonts.ready` y evaluar:
  ```js
  [...document.querySelectorAll('.sheet')].map((s, i) => ({
    page: i + 1,
    overflow: s.scrollHeight - s.clientHeight,
    sheets: document.querySelectorAll('.sheet').length
  }))
  ```
  Esperado: `sheets: 2` y `overflow <= 1` en ambas.
- [ ] Exportar a PDF con Chrome headless (no hay tool de PDF en Playwright MCP) y contar páginas:
  ```bash
  "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" \
    --headless=new --disable-gpu --no-pdf-header-footer \
    --virtual-time-budget=5000 \
    --print-to-pdf=/tmp/clientes-finales.pdf \
    "file://$PWD/docs/brochures/clientes-finales.html"
  pdfinfo /tmp/clientes-finales.pdf | grep Pages
  ```
  Esperado: `Pages: 2`.
- [ ] Revisar visualmente el PDF: sin texto cortado, sin elementos fuera de margen, logo nítido, contraste legible.

### Tarea 3: Brochure de laboratorios

**Archivos:** renombrar `Brochure Laboratorios.html` → `laboratorios.html` y reescribir.

- [ ] `git mv "docs/brochures/Brochure Laboratorios.html" docs/brochures/laboratorios.html`
- [ ] Reescribir con 2 `.sheet` y el copy deck 2.
- [ ] Repetir las 4 verificaciones de la tarea 2 (render, overflow en print, PDF de 2 páginas, revisión visual).

### Tarea 4: Brochure de intermediarios

**Archivos:** renombrar `Brochure Intermediarios.html` → `intermediarios.html` y reescribir.

- [ ] `git mv "docs/brochures/Brochure Intermediarios.html" docs/brochures/intermediarios.html`
- [ ] Reescribir con 2 `.sheet` y el copy deck 3.
- [ ] Repetir las 4 verificaciones de la tarea 2.

### Tarea 5: Brochure LubeAI 360

**Archivos:** renombrar `Brochure Servicio Integral LubeAI 360.html` → `lubeai-360.html` y reescribir.

- [ ] `git mv "docs/brochures/Brochure Servicio Integral LubeAI 360.html" docs/brochures/lubeai-360.html`
- [ ] Reescribir con 2 `.sheet` y el copy deck 4.
- [ ] Repetir las 4 verificaciones de la tarea 2.

### Tarea 6: Resumen ejecutivo de una página

**Archivos:** crear `docs/brochures/resumen-ejecutivo.html`.

- [ ] Crear el archivo con 1 sola `.sheet` y el copy deck 5.
- [ ] Verificar `sheets: 1`, `overflow <= 1` y PDF de 1 página.
- [ ] Revisar que los 4 perfiles se lean como caminos distintos y que el CTA sea único.

### Tarea 7: Índice, README y limpieza

**Archivos:**
- Crear: `docs/brochures/index.html`
- Crear: `docs/brochures/README.md`
- Eliminar: cualquier HTML antiguo restante en `docs/brochures/`.

- [ ] Crear `index.html` con las 5 tarjetas, el bloque de instrucciones de impresión y enlaces relativos.
- [ ] Crear `README.md` en español con: propósito del kit, mapa de segmentos, cómo imprimir a PDF, cómo editar copy, tokens de marca, matriz de afirmaciones permitidas/prohibidas, convención para agregar un segmento y advertencia de compartir la carpeta completa.
- [ ] Confirmar que no quedan archivos antiguos: `ls docs/brochures` debe mostrar solo los 6 HTML, `README.md` y `assets/`.
- [ ] Auditar afirmaciones prohibidas:
  ```bash
  grep -RniE "whatsapp|telegram|924[[:space:]]*138|tiempo real|24/7|backups? autom|white-?label" docs/brochures
  ```
  Esperado: sin resultados (se permite “marca blanca (white-label)” solo si el grep se ajusta; idealmente usar solo “marca blanca”).
- [ ] Auditar consistencia de contacto:
  ```bash
  grep -RnoE "\+51[[:space:]]*[0-9[:space:]]+|solutions@lubeai\.tech|lubeai\.platform@gmail\.com" docs/brochures | sort | uniq -c
  ```
  Esperado: solo `+51 993 373 231` y `solutions@lubeai.tech`.
- [ ] Auditar enlaces y assets: abrir `index.html` y comprobar que las 5 tarjetas y el logo cargan (sin 404 en la consola de red).
- [ ] Verificar responsive: a 390 px de ancho no debe haber scroll horizontal y el texto debe seguir legible.

### Tarea 8: Cerrar la decisión de naming en `docs/summary.md`

**Archivos:** modificar `docs/summary.md`.

- [ ] Agregar al final un párrafo breve: el servicio directo de análisis + plataforma se comercializa como **LubeAI 360 — Análisis + Plataforma**, y los perfiles comerciales son laboratorio, intermediario y cliente final. No reescribir el resto del documento.

---

## Verificación final (una sola pasada)

- [ ] `ls -R docs/brochures` coincide con la arquitectura de archivos.
- [ ] Cada documento tiene `lang="es"`, `<title>`, `meta description` y un solo `<h1>` por hoja.
- [ ] Los 5 documentos exportan exactamente 2, 2, 2, 2 y 1 páginas A4, sin recortes.
- [ ] El kit completo pesa menos de 1.5 MB (sin contar PDFs generados).
- [ ] No hay CSS embebido duplicado ni referencias a archivos eliminados.
- [ ] `index.html` y `README.md` están en español y explican cómo generar los PDF.
- [ ] `git status` solo muestra los archivos del kit y `docs/summary.md`.

## Review Focus

1. **Recorte de texto al imprimir** (métricas de fuente distintas a las de pantalla): cada tarea mide `scrollHeight - clientHeight` en modo print.
2. **Abrir un HTML suelto sin la carpeta `assets/`**: el documento se ve sin estilos; el README y el índice deben advertir que se comparte la carpeta o el PDF.
3. **Fuentes sin internet**: el PDF debe conservar la jerarquía con los fallbacks; revisar una exportación con la red deshabilitada o simular el fallback.
4. **Reaparición de canales retirados** (WhatsApp/Telegram) al copiar texto del sitio: el grep final lo bloquea.
5. **Impresión sin “Gráficos de fondo”**: la jerarquía debe seguir funcionando por bordes y reglas, no solo por bloques de color.

## Criterios de aceptación

- Existen 5 documentos comerciales + índice + README, todos en español y con la marca del sitio.
- Los 4 brochures tienen 2 páginas y el resumen ejecutivo 1, sin contenido cortado al exportar a PDF.
- No se promete ningún canal, integración o garantía que el producto no tenga.
- El teléfono es único (`+51 993 373 231`) y el correo es `solutions@lubeai.tech`.
- El copy usa “usted” de forma consistente y cada segmento tiene una propuesta y un CTA distintos.
- El CSS duplicado de los 4 archivos originales desapareció; queda una sola hoja compartida.

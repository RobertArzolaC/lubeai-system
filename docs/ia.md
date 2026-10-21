# Conexión de asistentes de IA por MCP

LubeAI expone un servidor **Model Context Protocol (MCP)** por cada tenant. Desde
la pantalla **Integraciones → Asistentes conectados** puedes autorizar a ChatGPT,
Claude o Gemini para consultar, en modo de solo lectura, los equipos, componentes,
reportes y alertas de tu organización.

La conexión usa **OAuth**: no se pega ningún token manualmente. El asistente abre
la página de autorización de LubeAI, el usuario inicia sesión y pulsa **Permitir
acceso**.

> **Última verificación:** 21/10/2026 contra las interfaces oficiales de ChatGPT,
> Claude y Gemini. Los nombres de los menús pueden variar según el plan, el idioma
> y la versión del proveedor.

## Antes de empezar

1. Entra a **Integraciones → Asistentes conectados** y copia la URL del servidor
   MCP de tu organización. Tiene la forma `https://<tu-dominio>/mcp` y **no lleva
   barra final**.
2. Comprueba que tu usuario tenga una organización asignada y al menos un módulo
   habilitado: Equipos, Reportes o Alertas.
3. Ten a mano tu cuenta de LubeAI. El asistente abrirá una pestaña para iniciar
   sesión y autorizar el acceso.
4. El acceso es de **solo lectura** y queda limitado a los datos que tu usuario ya
   puede ver en el panel.

## ChatGPT

### Requisitos

- Solo se puede crear desde la **web** de ChatGPT; la app móvil no muestra la
  opción de agregar servidores MCP personalizados.
- Los planes **Business, Enterprise y Edu** tienen compatibilidad completa. Los
  usuarios **Pro** pueden conectar el servidor con permisos de solo lectura.
- En un espacio de trabajo, un administrador debe permitir **Crear complementos
  con MCP**.

### Paso a paso

1. **Complementos**
   Abre [chatgpt.com](https://chatgpt.com) e inicia sesión. En el menú lateral entra
   a **Complementos**.
2. **Agregar +**
   Pulsa el botón **+**.
3. **Agregar servidor MCP personalizado**
   Completa el formulario:
   - **Foto:** opcional; puedes usar el logo de LubeAI.
   - **Nombre:** `LubeAI`.
   - **Descripción:** `Consulta de equipos, reportes y alertas de lubricación.`
   - **Conexión (URL):** pega la URL copiada en el paso previo.
4. **Configura la autenticación**
   Elige la autenticación OAuth. Si ChatGPT lo solicita, inicia sesión y continúa
   en la página de autorización de LubeAI.
5. **Crea el complemento**
   Revisa la advertencia de riesgo, acepta y pulsa **Crear como complemento**.
   Después revisa las herramientas que ChatGPT detectó.

### Cómo usarlo

En una conversación, escribe `@` y selecciona el complemento **LubeAI**. También
puedes pedir directamente: “Consulta los equipos de mi organización”.

### Fuente oficial

[Conectar servidores MCP personalizados en ChatGPT](https://help.openai.com/es-419/articles/12584461-connecting-custom-mcp-servers-in-chatgpt)

## Claude

### Requisitos

- Disponible en **Claude web** y **Claude Desktop**. En móvil, la instalación de
  conectores personalizados está en beta.
- Disponible en planes gratis, Pro, Max, Team y Enterprise. El plan gratuito
  permite **un solo conector personalizado**.
- En planes **Team y Enterprise**, un Owner debe habilitar el conector para la
  organización antes de que los miembros lo usen.

### Paso a paso

1. **Configuración**
   Abre [claude.ai](https://claude.ai) e inicia sesión. Entra a **Configuración**
   (en inglés: **Customize**).
2. **Conectores**
   Abre **Conectores** (en inglés: **Connectors**).
3. **Agregar +**
   Pulsa el botón **+** que está junto a Conectores.
4. **Agregar conector personalizado**
   Elige **Personalizado → Web** (en inglés: **Custom → Web**) y completa:
   - **Nombre:** `LubeAI`.
   - **URL del servidor MCP:** pega la URL copiada en el paso previo.
   Pulsa **Continuar**.
5. **Autoriza el acceso**
   Revisa la autenticación que Claude detectó y pulsa **Continuar**. En
   **Autenticación** elige **Iniciar sesión ahora** (en inglés: **Sign in now**).
   En **Cliente OAuth** deja la opción recomendada, **Usar la identidad publicada
   de Claude**. Pulsa **Agregar** y completa el inicio de sesión en LubeAI.

### Team y Enterprise

Un Owner debe entrar a **Configuración de la organización → Conectores**, buscar
el conector y pulsarlo para agregarlo al equipo. Después, cada persona autoriza su
propia cuenta.

### Cómo usarlo

Abre el menú **+** del chat, entra a **Conectores** y activa **LubeAI** para esa
conversación. También puedes escribir `/` y elegir Conectores.

### Fuente oficial

[Get started with custom connectors using remote MCP](https://support.claude.com/en/articles/11175166-get-started-with-custom-connectors-using-remote-mcp)

## Gemini

### Requisitos

- La conexión se crea únicamente desde la **web** de Gemini; después queda
  disponible en la app móvil y en la web.
- Requiere una **cuenta personal de Google**. Las cuentas de trabajo o escuela no
  pueden agregar aplicaciones personalizadas.
- Requiere tener **18 años o más**, estar en **Estados Unidos**, usar la interfaz
  en **inglés** y tener **Keep Activity** activo.
- Google no controla, monitorea ni audita los servidores MCP de terceros.

### Paso a paso

1. **Ajustes**
   Abre [gemini.google.com](https://gemini.google.com) en la web e inicia sesión
   con una cuenta personal de Google. Pulsa **Ajustes**.
2. **Inteligencia Personalizada**
   Entra a **Inteligencia Personalizada** (en inglés: **Personal Intelligence**).
3. **Personalizado +**
   En **Personalizado** (en inglés: **Custom apps**), pulsa **+**. Si no ves esa
   opción, entra a **Aplicaciones conectadas** (en inglés: **Connected Apps**) y
   busca la sección de aplicaciones personalizadas.
   - **URL del servidor MCP:** pega la URL copiada en el paso previo.
   Pulsa **Siguiente**.
4. **Autoriza el acceso**
   Completa el inicio de sesión y concede los permisos que Gemini solicite.
5. **Invoca la aplicación**
   En el chat, escribe `@` y selecciona la aplicación **LubeAI**.

### Fuente oficial

[Connect & manage custom apps for Gemini Apps](https://support.google.com/gemini/answer/17209137?hl=es)

## Cómo verificar la conexión

Después de autorizar el acceso, prueba con preguntas concretas:

- “¿Qué equipos tengo registrados?”
- “Muéstrame los reportes del equipo …”
- “¿Qué alertas abiertas hay?”

El asistente debe llamar primero a `get_account_overview` y luego a las
herramientas de listado o detalle. Si no aparecen herramientas:

1. Confirma que la URL termina en `/mcp` y no tiene barra final.
2. Vuelve a autorizar el acceso desde el asistente.
3. Revisa que tu usuario tenga organización y módulos habilitados.
4. En ChatGPT y Gemini, invoca el complemento o la aplicación con `@`.

## Cómo desconectar un asistente

- **Desde LubeAI:** entra a **Integraciones → Asistentes conectados**, busca la
  conexión y pulsa **Desconectar**. Los tokens se revocan de inmediato.
- **ChatGPT:** abre **Complementos**, selecciona el complemento y elimínalo o
  desactívalo.
- **Claude:** entra a **Configuración → Conectores**, abre el conector y elige
  desconectarlo.
- **Gemini:** entra a **Ajustes → Aplicaciones conectadas**, abre la aplicación y
  elige **Desconectar** o **Eliminar aplicación**.

## Problemas frecuentes

| Problema | Qué revisar |
| --- | --- |
| No aparece la opción de agregar un servidor MCP | El plan, la región o el tipo de cuenta no la habilitan. ChatGPT requiere web y plan compatible; Gemini requiere cuenta personal, EE. UU., inglés y Keep Activity. |
| La autorización falla o se queda cargando | Inicia sesión nuevamente, permite ventanas emergentes y confirma que la URL no lleva barra final. |
| El asistente conecta pero no devuelve datos | Verifica que tu usuario tenga organización y permisos sobre Equipos, Reportes o Alertas. |
| El asistente no llama a las herramientas | Indica el módulo en el prompt y, en ChatGPT o Gemini, selecciona el complemento o la aplicación con `@`. |
| La conexión dejó de funcionar | Puede haber expirado o sido revocada. Desconecta y vuelve a autorizar desde el asistente. |

## Fuentes oficiales

- **ChatGPT:** [Conectar servidores MCP personalizados](https://help.openai.com/es-419/articles/12584461-connecting-custom-mcp-servers-in-chatgpt)
- **Claude:** [Custom connectors using remote MCP](https://support.claude.com/en/articles/11175166-get-started-with-custom-connectors-using-remote-mcp)
- **Gemini:** [Connect & manage custom apps](https://support.google.com/gemini/answer/17209137?hl=es)

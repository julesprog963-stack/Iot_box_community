# Suite IoT Community: continuidad entre máquinas

Fecha de corte: 6 de octubre de 2026. Este checkpoint conserva trabajo en curso; **no es una release aprobada**.

## Repositorios y ramas

Todos pertenecen a `https://github.com/julesprog963-stack/`.

| Repositorio | Ramas necesarias |
|---|---|
| Iot_box_community | 17.0, 18.0, 19.0 |
| community_iot_agent | feature/iot-agent-v0.3 |
| community_iot_printing | 17.0, 18.0, 19.0 |
| pos_community_iot | 17.0, 18.0, 19.0 |
| community_iot_integrations | 17.0, 18.0, 19.0 |

Clonar cada repositorio por separado. Para trabajar simultáneamente en las tres versiones, usar clones separados o `git worktree`. No mezclar addons de distintas versiones en un mismo servidor.

```bash
git clone --branch 17.0 https://github.com/julesprog963-stack/Iot_box_community.git
git clone --branch feature/iot-agent-v0.3 https://github.com/julesprog963-stack/community_iot_agent.git
git clone --branch 17.0 https://github.com/julesprog963-stack/community_iot_printing.git
git clone --branch 17.0 https://github.com/julesprog963-stack/pos_community_iot.git
git clone --branch 17.0 https://github.com/julesprog963-stack/community_iot_integrations.git
```

## Alcance y reglas para continuar

Cerrar impresión PDF/POS con `community_iot_box`, `community_iot_printing`, `pos_community_iot` y el agente en Odoo 17/18/19. ZPL, báscula, comercialización y Raspberry Pi no bloquean este cierre.

- Solo emuladores y bases temporales independientes. Nunca enviar trabajos a impresoras físicas.
- No tocar producción, especialmente `arsenio-odoo-app`.
- Preservar cambios y diseños `.superdesign/` y `design/`.
- No publicar una release ni declarar APROBADO mientras falten puertas críticas.
- No reutilizar credenciales/tokens de esta máquina; generar secretos nuevos localmente.
- Usar las skills `modelo-actual-con-luna` y `desarrollo-modulos-odoo` si están disponibles. Luna se delega con modelo `gpt-6-luna`, esfuerzo `max`, verificando metadatos efectivos.

## Evidencia previa preservada en los resúmenes

- Agente: suite completa de 291 pruebas y 10 pruebas PDF previamente correctas tras la corrección local de streaming. No equivalen a E2E del daemon.
- PDF17: QWeb real, lista y formulario, ApiClient, CUPS-PDF, ACK, `done`, eliminación de adjunto y temporal. Se usó helper, no daemon persistente.
- Printing18/19: menús y asistente desde formulario/lista, copias editables, cancelación; inicialmente sin impresión PDF ejecutada. Consultar el handoff de printing para avances posteriores.
- POS17: instalación/actualización, tres pruebas backend, pago/recibo/reimpresión/recarga y jobs raster confirmados. El ticket sintético no prueba los totales reales. Hubo 40 errores 404 de fuentes externas.
- POS18: instalación y actualización; tres pruebas post-install reales correctas. El primer selector `/pos_community_iot:post_install` no seleccionó pruebas y NO cuenta. El selector correcto fue `post_install/pos_community_iot`.
- Daemon17: CLI real, API HTTP, journal aislado y ESC/POS emulado; un ticket confirmado `done`, `success`, un intento. Consultar handoff del agente para reinicio/ACK y límites posteriores.
- Integraciones: 39/39 verificaciones de permisos en17 y 21/21 en18/19; 48 pruebas lease por versión18/19 y 16 trabajos ZPL/báscula emulados. Parte del recorrido usa ORM, no HTTP completo. Reglas de grupo combinan por OR con otros grupos: la visibilidad solo se verificó en combinaciones documentadas.

## Cambios guardados

- Agente: errores de streaming PDF sanitizados, sin causa sensible en traceback normal; pruebas de interrupción, cabeceras inválidas, descarga incompleta y exceso de tamaño.
- Printing17/18/19: versión `*.0.1.0.1` y acceso IoT Print desde CogMenu; 18/19 extienden también FormCogMenu.
- Integraciones17/18/19: versión `*.0.1.0.1`, lectura de cajas para grupos específicos y reglas por compañías permitidas para cajas/dispositivos.

El agente está basado en `d467bf1`, versión 0.5.0. El tag v0.4.0 apunta a `86a159c`, ancestro de v0.5.0. No hay bifurcación; no mover ni sobrescribir tags existentes. El objetivo histórico «impresión v0.4.0» describe alcance, no autoriza retroceder el código actual.

## Pendientes críticos

1. PDF18/19 completo: asistente → QWeb → HTTP claim/download → CUPS-PDF → ACK → limpieza.
2. POS18/19 y faltantes17: pago, automático/manual, reimpresión, cocina, cajón, copias, offline, fallback y totales reales.
3. Aceptación visual del raster y fuentes externas: emulador ESC/POS0.3.0 tiene parser GS v0 defectuoso y no dibuja bitmaps. No alterar driver para adaptarlo. Usar renderizador existente o decoder QA acotado de bytes capturados a PNG.
4. Daemon/API: journal, reinicio, lease vencido, descarga interrumpida, resultado desconocido y no duplicación.
5. Regresión final y dictamen por versión con evidencia; los commits de checkpoint no implican aprobación.

El core POS recopila todas las reglas `@font-face` para el raster, incluidas fuentes Noto en `fonts.odoocdn.com` con HTTP404. CSS scoped no evita la recopilación; el wrapper `htmlToCanvas` no propaga `skipFonts`/`fontEmbedCSS`. No suprimir fuentes globalmente sin comprobar Unicode y fidelidad.

## Entornos y artefactos

El laboratorio portable está en `community_iot_agent/tools/iot_emulator_lab/`. Revisar su README y sus requisitos en una máquina nueva. Sus smoke tests no equivalen a aceptación E2E.

Las bases Docker, volúmenes, journal, logs crudos, PDFs temporales, claims/results, cookies y credenciales de QA **no están en GitHub**. Los claims contienen lock tokens. Recrear bases/secretos y fixtures; no esperar que `git clone` restaure Docker.

En la máquina original, los informes históricos están bajo `tmp/iot-qa-20261004-status.md`, `tmp/iot-pdf-e2e-20261004/`, `tmp/iot-pos-e2e-20261004/`, `tmp/iot-integrations-e2e-20261004/` y `tmp/iot-integrations-security17-20261004/`. Sus hechos comprobados se resumen arriba. Los handoffs por componente añaden los avances de esta sesión sin divulgar secretos.

Consultar también:

- `community_iot_agent/docs/qa/HANDOFF-20261006-agent.md`
- `community_iot_printing/docs/qa/HANDOFF-20261006.md` (rama19.0)
- `pos_community_iot/docs/qa/HANDOFF-20261006.md` (rama19.0)

Dictamen de continuidad: **NO VERIFICADO para cierre completo de impresión**, hasta completar todas las pruebas críticas pendientes.

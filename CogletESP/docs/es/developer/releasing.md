# Publicar versiones

[Documentación](../README.md) · [English](../../en/developer/releasing.md) · [Deutsch](../../de/developer/releasing.md) · **Español** · [日本語](../../ja/developer/releasing.md)

Las versiones las compila GitHub Actions (`.github/workflows/firmware.yml`) y
se publican en la página Coglet Updater y como versiones de GitHub.

## Configuración única del repositorio

Hacen falta permisos de administración:

1. **Settings → Pages → Build and deployment → Source: GitHub Actions**.
2. **Settings → Environments → github-pages → Deployment branches and tags →
   Add rule → Ref type: Tag, patrón `v*`**. Sin esta regla, una etiqueta se
   compila pero su despliegue se rechaza («not allowed to deploy to
   github-pages due to environment protection rules»).

## Publicar una versión

1. Sube `PROJECT_VER` en `CogletESP/CMakeLists.txt` (lo usan las compilaciones
   locales y las que no tienen etiqueta).
2. Sube una etiqueta:

```bash
git tag v2.4.0
git push origin v2.4.0
```

Las etiquetas tienen la forma `v2.4.0` o `v2.4.0-beta1`; cualquier otra se
rechaza. La etiqueta sin `v` se convierte en la versión del firmware
(`-D PROJECT_VER=2.4.0`), que **Comprobar mi Coglet** vuelve a leer. Usa solo
números: la comprobación OTA los compara uno a uno. Volver a ejecutar una
etiqueta compila el commit al que apunta; para código nuevo, crea una etiqueta
nueva.

## Qué hace el flujo de trabajo

1. Compila cuatro veces en el contenedor `espressif/idf:v5.5.3`: Estándar con el
   `sdkconfig` del repositorio y luego Navidad, Duende y Muñeco de nieve en
   `build-<edition>/` con `sdkconfig.<edition>` encima. Cada compilación incluye
   el programa del RP2040 y guarda el commit corto
   (`-D COGLET_BUILD_COMMIT=…`; las compilaciones locales guardan `local`).
2. Copia las partes de la flash desde `build/flasher_args.json` y escribe con
   `tools/web_flasher/make_manifest.py` `firmware/manifest.json` (direcciones,
   tamaños, MD5, edición, ubicación de los ajustes y de la biblioteca de
   canciones, enlace a las notas de la versión), y lo mismo en
   `firmware-christmas/`, `firmware-elf/` y `firmware-snowman/`.
3. Despliega la página, el firmware y los archivos del RP2040 en GitHub Pages.
4. Adjunta a la versión `coglet-firmware-<version>.zip` y un zip por cada
   edición navideña, cada uno con las partes y una línea de comandos de esptool.

Si se inicia a mano desde la pestaña **Actions**, compila y despliega una
versión `dev-<commit>` sin crear una versión de GitHub.

## Lista de comprobación

- Compila en local con ESP-IDF **v5.5.3**, las cuatro ediciones.
- Probado en un Coglet: actualización desde la versión anterior con el Coglet
  Updater, actualización de la placa de servos, palabra de activación, un baile,
  un recordatorio.
- ¿Cambiaron archivos del RP2040? Cada Coglet los volverá a enviar al actualizar.
- Notas de la versión escritas (la página enlaza a ellas).

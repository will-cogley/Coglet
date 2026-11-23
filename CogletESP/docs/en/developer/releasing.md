# Releasing

[Documentation home](../../README.md) · **English** · [Deutsch](../../de/developer/releasing.md) · [Español](../../es/developer/releasing.md) · [日本語](../../ja/developer/releasing.md)

Releases are built by GitHub Actions (`.github/workflows/firmware.yml`) and
published on the Coglet Updater page and as GitHub releases.

## One-time repository setup

Admin rights needed:

1. **Settings → Pages → Build and deployment → Source: GitHub Actions**.
2. **Settings → Environments → github-pages → Deployment branches and tags →
   Add rule → Ref type: Tag, pattern `v*`**. Without it, a tag builds but its
   deploy is rejected ("not allowed to deploy to github-pages due to
   environment protection rules").

## Publishing a release

1. Raise `PROJECT_VER` in `CogletESP/CMakeLists.txt` (used by local and
   untagged builds).
2. Push a tag:

```bash
git tag v2.4.0
git push origin v2.4.0
```

Tags look like `v2.4.0` or `v2.4.0-beta1`; anything else is refused. The tag
without `v` becomes the firmware version (`-D PROJECT_VER=2.4.0`), which
**Check my Coglet** reads back. Keep it plain numbers: the OTA check compares
them one by one. Re-running a tag builds the commit it points to; for new
code, make a new tag.

## What the workflow does

1. Builds four times in the `espressif/idf:v5.5.3` container: Standard with the
   repository's `sdkconfig`, then Christmas, Elf and Snowman in
   `build-<edition>/` with `sdkconfig.<edition>` on top. Every build includes
   the RP2040 program and stores the short commit
   (`-D COGLET_BUILD_COMMIT=…`; local builds store `local`).
2. Copies the flash parts from `build/flasher_args.json` and writes
   `firmware/manifest.json` (offsets, sizes, MD5, edition, settings and song
   library location, release notes link) with
   `tools/web_flasher/make_manifest.py`, likewise `firmware-christmas/`,
   `firmware-elf/` and `firmware-snowman/`.
3. Deploys the page, the firmware and the RP2040 files to GitHub Pages.
4. Attaches `coglet-firmware-<version>.zip` and one zip per holiday edition to
   the release, each with the parts and an esptool command line.

Started by hand from the **Actions** tab, it builds and deploys a
`dev-<commit>` version without a release.

## Checklist

- Builds with ESP-IDF **v5.5.3** locally, all four editions.
- Tested on a Coglet: update from the previous release with the Coglet
  Updater, servo board update, wake word, a dance, a reminder.
- RP2040 files changed? Every Coglet will re-send them after updating.
- Release notes written (the page links to them).

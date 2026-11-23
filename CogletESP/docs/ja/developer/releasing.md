# リリースの公開

[ドキュメント](../README.md) · [English](../../en/developer/releasing.md) · [Deutsch](../../de/developer/releasing.md) · [Español](../../es/developer/releasing.md) · **日本語**

リリースはGitHub Actions（`.github/workflows/firmware.yml`）でビルドされ、Coglet Updater
ページとGitHubのリリースで公開されます。

## リポジトリの初回設定

管理者権限が必要です：

1. **Settings → Pages → Build and deployment → Source: GitHub Actions**。
2. **Settings → Environments → github-pages → Deployment branches and tags →
   Add rule → Ref type: Tag、パターン `v*`**。このルールがないと、タグのビルドは
   通ってもデプロイが拒否されます（「not allowed to deploy to github-pages due to
   environment protection rules」）。

## リリースを公開する

1. `CogletESP/CMakeLists.txt` の `PROJECT_VER` を上げます（ローカルビルドとタグなしの
   ビルドで使われます）。
2. タグをプッシュします：

```bash
git tag v2.4.0
git push origin v2.4.0
```

タグは `v2.4.0` や `v2.4.0-beta1` の形にします。それ以外は拒否されます。`v` を除いた
タグがファームウェアのバージョン（`-D PROJECT_VER=2.4.0`）になり、**Cogletの状態を確認**
で読み取れます。数字だけにしてください。OTAのチェックが1つずつ比べます。同じタグを
再実行すると、そのタグが指すコミットがビルドされます。新しいコードには新しいタグを
作ってください。

## ワークフローの処理

1. `espressif/idf:v5.5.3` コンテナーで4回ビルドします：リポジトリの `sdkconfig` で
   スタンダード、続いて `sdkconfig.<edition>` を重ねてクリスマス、エルフ、雪だるまを
   `build-<edition>/` で。どのビルドにもRP2040のプログラムが入り、短いコミットを記録します
   （`-D COGLET_BUILD_COMMIT=…`。ローカルビルドは `local`）。
2. `build/flasher_args.json` からフラッシュのパーツをコピーし、
   `tools/web_flasher/make_manifest.py` で `firmware/manifest.json`（オフセット、サイズ、
   MD5、エディション、設定と曲ライブラリーの位置、リリースノートへのリンク）を書きます。
   `firmware-christmas/`、`firmware-elf/`、`firmware-snowman/` も同様です。
3. ページ、ファームウェア、RP2040のファイルをGitHub Pagesにデプロイします。
4. `coglet-firmware-<version>.zip` と、季節のエディションごとのzipをリリースに添付します。
   どのzipにもパーツとesptoolのコマンドラインが入っています。

**Actions** タブから手動で実行すると、リリースを作らずに `dev-<commit>` のバージョンを
ビルドしてデプロイします。

## チェックリスト

- ESP-IDF **v5.5.3** で、4つのエディションすべてをローカルでビルドできる。
- 実機のCogletでテスト済み：Coglet Updaterで前のリリースからアップデート、サーボボードの
  更新、ウェイクワード、ダンス1回、リマインダー1件。
- RP2040のファイルを変更した？ すべてのCogletがアップデート後にそれを送り直します。
- リリースノートを書いた（ページからリンクされます）。

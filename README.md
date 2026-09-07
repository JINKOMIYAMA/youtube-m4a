# YouTube → M4A Web App

iPad / iPhone / PC のブラウザから、YouTube URLを入力してM4Aを生成するWebアプリです。

## 機能

- YouTube URLから動画情報を取得
- 動画タイトルを初期「タイトル」に設定
- チャンネル名を初期「アーティスト」に設定
- タイトル / アーティストをダウンロード前に編集可能
- YouTubeサムネイルを中央1:1クロップ → 1000×1000 JPEG化
- M4Aにタイトル / アーティスト / ジャケットを埋め込み
- iPad Safariから直接ダウンロード
- PWA対応（ホーム画面に追加可能）

## 必要なもの

- Python 3.12+
- FFmpeg / ffprobe
- Deno 2.3+（現在のyt-dlpのYouTube JS challenge処理用）

## ローカル起動

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\\Scripts\\activate
pip install -r requirements.txt
uvicorn app:app --reload --host 0.0.0.0 --port 8000
```

ブラウザで `http://localhost:8000` を開きます。

## Docker

```bash
docker build -t youtube-m4a .
docker run --rm -p 8000:8000 youtube-m4a
```

## Railway

このフォルダをGitHubへアップロードし、Railwayでリポジトリを選択すればDockerfileでビルドできます。

## 補足

YouTube側の仕様変更に追従するため、yt-dlpは定期的に更新してください。公開動画でも、地域制限・年齢制限・ログイン必須・配信形式などによって取得できない場合があります。このプロジェクトにはログイン制限やDRM等を回避する仕組みは含めていません。

コンテンツの権利・利用条件を確認し、自分が権利を持つ、またはダウンロードが許可されているコンテンツに使用してください。

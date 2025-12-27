# DocuMind セットアップガイド

このガイドでは、DocuMindをローカル環境で起動し、基本的な使い方を説明します。

## 📋 必要なもの

- **Docker Desktop** (最新版)
  - Mac: https://www.docker.com/products/docker-desktop
  - Windows: https://www.docker.com/products/docker-desktop
- **OpenAI APIキー**
  - https://platform.openai.com/api-keys で取得

## 🚀 5分でスタート

### ステップ1: プロジェクトの準備

```bash
# プロジェクトディレクトリに移動
cd documind

# 環境変数ファイルを作成
cp .env.example .env
```

### ステップ2: OpenAI APIキーを設定

`.env`ファイルを開いて、以下の行を編集:

```env
OPENAI_API_KEY=sk-your-actual-api-key-here
```

> **ヒント**: OpenAI APIキーは https://platform.openai.com/api-keys で作成できます

### ステップ3: テスト用ドキュメントを配置

```bash
# データフォルダを作成
mkdir -p data

# テスト用のPDFファイルをdataフォルダに配置
# 例: cp ~/Documents/sample.pdf data/
```

### ステップ4: Docker Composeで起動

```bash
# すべてのサービスを起動
docker-compose up -d

# ログを確認
docker-compose logs -f
```

起動には3-5分かかります。以下のメッセージが表示されたら準備完了です:

```
backend_1    | INFO:     Application startup complete.
frontend_1   | ▲ Next.js 14.2.3
frontend_1   | - Local:        http://localhost:3000
```

### ステップ5: アクセス

ブラウザで以下のURLを開く:

🌐 **http://localhost:3000**

## 🎯 基本的な使い方

### 1. ダッシュボードにアクセス

初回は認証をスキップして直接ダッシュボードにアクセスできます:

http://localhost:3000/dashboard

### 2. ドキュメントのインデックス確認

左サイドバーから「ドキュメント」をクリック。
`data`フォルダに配置したファイルが自動的にインデックスされます。

### 3. AIチャットで質問

1. 左サイドバーから「チャット」をクリック
2. 質問を入力 (例: 「このドキュメントの概要を教えて」)
3. Enterキーまたは「送信」ボタンをクリック
4. AIが関連ドキュメントから回答を生成します

### 4. 設定のカスタマイズ

「設定」メニューから:
- LLMモデルの変更 (GPT-4o, GPT-4-turbo など)
- 検索パラメータの調整
- データソースの追加

## 🔧 トラブルシューティング

### ポート競合エラー

```
Error: port is already allocated
```

**解決方法**: `.env`ファイルでポートを変更

```env
# フロントエンドのポートを変更
FRONTEND_PORT=3001
```

### OpenAI APIエラー

```
Error: Incorrect API key provided
```

**解決方法**: `.env`ファイルのAPIキーを確認

### ドキュメントがインデックスされない

**確認事項**:
1. `data`フォルダにファイルがあるか
2. ファイル形式は対応しているか (.pdf, .docx, .pptx)
3. バックエンドのログを確認: `docker-compose logs backend`

## 📊 サンプルデータ

テスト用のサンプルドキュメントをダウンロード:

```bash
# サンプルPDFをダウンロード
curl -o data/sample_financial_report.pdf \
  https://www.example.com/sample.pdf
```

## 🛑 停止と再起動

```bash
# すべてのサービスを停止
docker-compose down

# データを保持したまま停止
docker-compose stop

# 再起動
docker-compose start

# データを完全に削除して停止
docker-compose down -v
```

## 📚 次のステップ

- [README.md](README.md) - 詳細なドキュメント
- [設定ガイド](docs/configuration.md) - 高度な設定
- [デプロイガイド](docs/deployment.md) - 本番環境へのデプロイ

## 💡 よくある質問

### Q: 無料で使えますか?

A: はい、ただしOpenAI APIの利用料金が発生します。
   GPT-4o-miniを使用すれば低コストで運用可能です。

### Q: 日本語の文書に対応していますか?

A: はい、完全対応しています。日本語の質問・回答も可能です。

### Q: どのくらいのドキュメント量に対応できますか?

A: ローカル環境では数千ファイル程度。
   本番環境では数百万ページまでスケール可能です。

### Q: Google Driveと連携できますか?

A: はい、設定ファイルで有効化できます。
   詳細は[データソース設定ガイド](docs/datasources.md)を参照。

## 🆘 サポート

問題が解決しない場合:

1. GitHubのIssueを検索: https://github.com/your-org/documind/issues
2. 新しいIssueを作成
3. Discordコミュニティに参加: https://discord.gg/documind

---

**DocuMindを楽しんでください！** 🎉

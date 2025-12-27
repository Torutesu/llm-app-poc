# 🔌 コネクタ設定ガイド

企業のアプリ（Slack、Google Driveなど）を接続して、全社横断検索を実現します。

## 📋 目次

1. [概要](#概要)
2. [コネクタの種類](#コネクタの種類)
3. [設定方法](#設定方法)
4. [使い方](#使い方)

---

## 概要

このシステムは、Gleanのような企業検索サービスと同じアーキテクチャを採用しています:

```
┌─────────────────────────────────────────┐
│   ユーザー                                │
│   ↓                                      │
│   ログイン & 認証 (JWT + 2FA)             │
└─────────────────────────────────────────┘
              ↓
┌─────────────────────────────────────────┐
│   コネクタ管理                            │
│   ・Slack                                │
│   ・Google Drive                         │
│   ・Notion                               │
│   ・GitHub                               │
│   ・Confluence                           │
│   ・Jira                                 │
└─────────────────────────────────────────┘
              ↓ OAuth認証
┌─────────────────────────────────────────┐
│   外部サービス                            │
│   ・メッセージ取得                        │
│   ・ファイル取得                          │
│   ・権限チェック                          │
└─────────────────────────────────────────┘
              ↓
┌─────────────────────────────────────────┐
│   インデックス & ベクトルDB                │
│   ・コンテンツの埋め込み生成               │
│   ・メタデータ保存                        │
│   ・アクセス制御                          │
└─────────────────────────────────────────┘
              ↓
┌─────────────────────────────────────────┐
│   RAG検索                                │
│   ・セマンティック検索                     │
│   ・LLM回答生成                           │
│   ・ソース表示                            │
└─────────────────────────────────────────┘
```

---

## コネクタの種類

### ✅ 実装済み

#### 1. **Slack** 💬
- **同期対象**:
  - パブリックチャンネル
  - プライベートチャンネル（アクセス権あり）
  - ダイレクトメッセージ
  - ファイル・添付ファイル

- **必要な権限**:
  - `channels:history` - チャンネルメッセージ読み取り
  - `channels:read` - チャンネル情報取得
  - `groups:history` - プライベートチャンネル履歴
  - `groups:read` - プライベートチャンネル情報
  - `im:history` - DM履歴
  - `im:read` - DM情報
  - `files:read` - ファイル読み取り
  - `users:read` - ユーザー情報
  - `team:read` - ワークスペース情報

#### 2. **Google Drive** 📁
- **同期対象**:
  - Google Docs（テキスト形式でエクスポート）
  - Google Sheets（CSV形式でエクスポート）
  - Google Slides（テキスト形式でエクスポート）
  - PDFファイル
  - テキストファイル
  - 共有ドライブ

- **必要な権限**:
  - `https://www.googleapis.com/auth/drive.readonly` - ファイル読み取り専用
  - `https://www.googleapis.com/auth/drive.metadata.readonly` - メタデータ読み取り

### 🚧 Coming Soon

- **Notion** 📝
- **GitHub** 🐙
- **Confluence** 🌐
- **Jira** 📊
- **Dropbox** 📦
- **OneDrive** ☁️

---

## 設定方法

### Slackコネクタの設定

#### 1. Slack Appを作成

1. [Slack API](https://api.slack.com/apps)にアクセス
2. 「Create New App」→「From scratch」を選択
3. App名とワークスペースを選択

#### 2. OAuth & Permissionsを設定

1. 左メニューから「OAuth & Permissions」を選択
2. **Redirect URLs**に追加:
   ```
   http://localhost:3000/oauth-callback.html
   ```
3. **Scopes**を追加（上記の必要な権限を全て追加）

#### 3. 認証情報を取得

1. 左メニューから「Basic Information」を選択
2. **Client ID**をコピー
3. **Client Secret**を表示してコピー

#### 4. アプリで接続

1. http://localhost:3000/connectors.html にアクセス
2. Slackカードをクリック
3. Client IDとClient Secretを入力
4. 「Connect」をクリック
5. Slackの認証画面で「許可」

---

### Google Driveコネクタの設定

#### 1. Google Cloud Projectを作成

1. [Google Cloud Console](https://console.cloud.google.com/)にアクセス
2. 新しいプロジェクトを作成

#### 2. Google Drive APIを有効化

1. 「APIとサービス」→「ライブラリ」を開く
2. 「Google Drive API」を検索して有効化

#### 3. OAuth 2.0認証情報を作成

1. 「APIとサービス」→「認証情報」を開く
2. 「認証情報を作成」→「OAuth クライアント ID」を選択
3. アプリケーションの種類: **ウェブアプリケーション**
4. **承認済みのリダイレクトURI**に追加:
   ```
   http://localhost:3000/oauth-callback.html
   ```
5. クライアントIDとクライアントシークレットをコピー

#### 4. OAuth同意画面を設定

1. 「OAuth同意画面」を開く
2. ユーザータイプ: **外部**（テストユーザーを追加）
3. スコープを追加（上記の必要な権限）

#### 5. アプリで接続

1. http://localhost:3000/connectors.html にアクセス
2. Google Driveカードをクリック
3. Client IDとClient Secretを入力
4. 「Connect」をクリック
5. Googleの認証画面で「許可」

---

## 使い方

### コネクタの接続

```bash
# 1. サーバーを起動
bash START_SERVERS.sh

# 2. ブラウザでアクセス
open http://localhost:3000/login.html

# 3. ログイン後、Connectorsページへ
open http://localhost:3000/connectors.html
```

### 手動同期

各コネクタカードの「Sync Now」ボタンをクリック:
```
✅ 同期開始
📥 コンテンツ取得
🔄 インデックス化
✅ 完了
```

### 自動同期

デフォルト設定:
- 同期間隔: **60分**
- 自動同期: **有効**

設定を変更する場合:
```bash
# API経由で設定変更
curl -X PATCH http://localhost:8000/connectors/{connector_id}/sync-settings \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "sync_enabled": true,
    "sync_interval_minutes": 30
  }'
```

---

## APIエンドポイント

### コネクタ管理

```bash
# コネクタ一覧
GET /connectors/

# コネクタ作成
POST /connectors/
{
  "connector_type": "slack",
  "settings": {
    "client_id": "...",
    "client_secret": "..."
  }
}

# コネクタ詳細
GET /connectors/{connector_id}

# コネクタ削除
DELETE /connectors/{connector_id}
```

### OAuth

```bash
# OAuth開始
POST /connectors/{connector_id}/oauth/start?redirect_uri=...

# OAuth完了
POST /connectors/{connector_id}/oauth/callback
{
  "code": "...",
  "state": "..."
}
```

### 同期

```bash
# 手動同期
POST /connectors/{connector_id}/sync

# 全コネクタ同期
POST /connectors/sync-all

# 接続テスト
GET /connectors/{connector_id}/test
```

---

## トラブルシューティング

### OAuth認証エラー

**問題**: `invalid_redirect_uri`
- **解決**: リダイレクトURIが正確に設定されているか確認
  - Slack: `http://localhost:3000/oauth-callback.html`
  - Google: 末尾のスラッシュに注意

**問題**: `access_denied`
- **解決**: 必要な権限（スコープ）が全て設定されているか確認

### 同期エラー

**問題**: `Token expired`
- **解決**: コネクタを再接続（トークンが自動更新されます）

**問題**: `Rate limit exceeded`
- **解決**: 同期間隔を長くする（60分以上推奨）

### 権限エラー

**問題**: `Insufficient permissions`
- **解決**:
  1. コネクタを削除
  2. Slack/Google側でアプリの権限を再設定
  3. 再度接続

---

## セキュリティ

### トークン管理

- **アクセストークン**: 暗号化してDBに保存
- **リフレッシュトークン**: 暗号化してDBに保存
- **トークン有効期限**: 自動更新

### アクセス制御

- コネクタは**テナント単位**で管理
- 各ユーザーは自分のテナントのコネクタのみアクセス可能
- ドキュメントの権限も保持

### CSRF対策

- OAuthフローで`state`パラメータを使用
- サーバー側で検証

---

## 次のステップ

1. ✅ コネクタを設定
2. ✅ 同期を実行
3. 🚧 RAG検索機能を実装（次のフェーズ）
4. 🚧 チャットUIを実装

---

## 参考リンク

- [Slack API Documentation](https://api.slack.com/)
- [Google Drive API Documentation](https://developers.google.com/drive)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)

---

質問やissueがあれば、GitHubでissueを作成してください。

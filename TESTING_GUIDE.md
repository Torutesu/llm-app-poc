# ローカルテストガイド

認証システムをローカル環境でテストする方法です。

## 🚀 クイックスタート

### 1. サーバーを起動

```bash
# プロジェクトルートで実行
bash START_SERVERS.sh
```

これで以下が起動します：
- **APIサーバー**: http://localhost:8000
- **フロントエンド**: http://localhost:3000

### 2. ブラウザでテスト

#### オプション A: フロントエンドUI を使う

1. **ブラウザで開く**: http://localhost:3000/login.html

2. **新規ユーザー登録**:
   - 「Create Account」をクリック
   - メールアドレス、パスワードを入力
   - 登録完了

3. **ログイン**:
   - メールアドレスとパスワードでログイン
   - ダッシュボードにリダイレクト

4. **ダッシュボードで確認**:
   - ユーザープロフィール
   - アクティブセッション
   - 2FA設定

#### オプション B: Swagger UI を使う

1. **Swagger UI を開く**: http://localhost:8000/docs

2. **エンドポイントをテスト**:
   - `POST /auth/register` - ユーザー登録
   - `POST /auth/login` - ログイン
   - `GET /auth/me` - プロフィール取得

3. **認証が必要なエンドポイント**:
   - 右上の「Authorize」ボタンをクリック
   - ログインで取得したトークンを入力
   - 認証後、保護されたエンドポイントにアクセス可能

### 3. cURLでテスト

#### ユーザー登録
```bash
curl -X POST http://localhost:8000/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "email": "demo@example.com",
    "password": "Demo123",
    "name": "Demo User",
    "tenant_id": "tenant_demo"
  }'
```

#### ログイン
```bash
curl -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "email": "demo@example.com",
    "password": "Demo123"
  }'
```

レスポンスから`access_token`を取得します。

#### ユーザープロフィール取得
```bash
TOKEN="your_access_token_here"

curl http://localhost:8000/auth/me \
  -H "Authorization: Bearer $TOKEN"
```

### 4. 統合テストスクリプト実行

自動で全機能をテスト：

```bash
python3 test_integration.py
```

これで以下がテストされます：
- ✓ ユーザー登録
- ✓ ログイン
- ✓ ユーザープロフィール取得
- ✓ セッション管理
- ✓ 2FA状態確認
- ✓ ログアウト
- ✓ OpenAPI ドキュメント

---

## 🎯 主要なテストシナリオ

### シナリオ 1: 基本的な認証フロー

1. **ユーザー登録** → ユーザーIDとメールを取得
2. **ログイン** → JWTトークンを取得
3. **プロフィール表示** → ユーザー情報を確認
4. **ログアウト** → セッション無効化

### シナリオ 2: 2要素認証

1. **ログイン後、ダッシュボードで「Manage 2FA」**
2. **TOTP設定**:
   - QRコードをスキャン
   - Google Authenticatorなどでコードを取得
   - コードを入力して有効化
3. **ログアウトして再ログイン**:
   - メール/パスワードで認証
   - 2FAコードの入力を要求される
   - コード入力後、ログイン完了

### シナリオ 3: セッション管理

1. **複数デバイスからログイン**:
   - デスクトップでログイン
   - スマホでログイン（別ブラウザで模擬）
2. **ダッシュボードでセッション確認**:
   - 全アクティブセッションを表示
   - デバイス情報、IP、最終アクティビティ時刻を確認
3. **特定デバイスからログアウト**:
   - 不要なセッションを個別に無効化
4. **全デバイスからログアウト**:
   - 「Logout All Devices」で現在のセッション以外を全て無効化

### シナリオ 4: パスワードリセット

1. **ログイン画面で「Forgot Password?」**
2. **メールアドレス入力**
3. **（モック）メールでリセットリンクを受信**
4. **新しいパスワードを設定**
5. **新パスワードでログイン**

---

## 🧪 APIエンドポイント一覧

### 認証
- `POST /auth/register` - ユーザー登録
- `POST /auth/login` - ログイン
- `POST /auth/login/2fa` - 2FA検証
- `POST /auth/logout` - ログアウト
- `POST /auth/logout-all` - 全デバイスログアウト

### ユーザー
- `GET /auth/me` - 現在のユーザー情報

### 2FA
- `POST /auth/2fa/totp/setup` - TOTP設定開始
- `POST /auth/2fa/totp/verify-setup` - TOTP有効化
- `DELETE /auth/2fa/totp` - TOTP無効化
- `POST /auth/2fa/sms/setup` - SMS設定開始
- `POST /auth/2fa/sms/verify-setup` - SMS有効化
- `DELETE /auth/2fa/sms` - SMS無効化
- `GET /auth/2fa/status` - 2FA状態確認

### パスワード
- `POST /auth/password-reset/request` - リセット要求
- `POST /auth/password-reset/confirm` - リセット実行
- `POST /auth/password/change` - パスワード変更

### セッション
- `GET /auth/sessions` - アクティブセッション一覧
- `DELETE /auth/sessions/{session_id}` - セッション削除
- `GET /auth/sessions/statistics` - セッション統計

---

## 📊 確認ポイント

### ✓ ユーザー登録
- [ ] 正常に登録できる
- [ ] 重複メールはエラーになる
- [ ] user_idが返される

### ✓ ログイン
- [ ] 正しい認証情報でログイン成功
- [ ] 間違ったパスワードでエラー
- [ ] JWTトークンが返される
- [ ] session_idが返される

### ✓ トークン認証
- [ ] トークンでプロフィールにアクセスできる
- [ ] トークンなしでは401エラー
- [ ] 無効なトークンでエラー

### ✓ セッション
- [ ] ログイン時にセッションが作成される
- [ ] デバイス情報が記録される
- [ ] セッション一覧で確認できる
- [ ] ログアウトでセッションが無効化される

### ✓ 2FA (TOTP)
- [ ] QRコードが生成される
- [ ] Authenticatorアプリでスキャンできる
- [ ] コードで検証できる
- [ ] バックアップコードが生成される

### ✓ フロントエンド
- [ ] ログイン画面が表示される
- [ ] ログインが動作する
- [ ] ダッシュボードが表示される
- [ ] セッション一覧が表示される

---

## 🐛 トラブルシューティング

### サーバーが起動しない

```bash
# ポートを確認
lsof -i :8000
lsof -i :3000

# プロセスを停止
pkill -f 'uvicorn api.main:app'
pkill -f 'http.server 3000'

# 再起動
bash START_SERVERS.sh
```

### APIに接続できない

```bash
# サーバー状態確認
curl http://localhost:8000/health

# ログ確認
tail -f /tmp/api_server.log
```

### トークンエラー

```bash
# 新しくログインしてトークンを取得
curl -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"test@example.com","password":"Test123"}'
```

### フロントエンドが表示されない

```bash
# ブラウザのコンソールでCORSエラーを確認
# ブラウザのキャッシュをクリア
# APIサーバーが起動しているか確認
```

---

## 📝 次のステップ

テストが完了したら：

1. **PostgreSQLに接続してデータを永続化**
2. **本番環境設定の調整**
3. **セキュリティ設定の強化**
4. **モニタリング・ロギングの設定**

---

## 🔗 便利なリンク

- **API Documentation (Swagger)**: http://localhost:8000/docs
- **API Documentation (ReDoc)**: http://localhost:8000/redoc
- **OpenAPI Spec**: http://localhost:8000/openapi.json
- **Login Page**: http://localhost:3000/login.html
- **Dashboard**: http://localhost:3000/dashboard.html

---

質問やissueがあれば、GitHubでissueを作成してください。

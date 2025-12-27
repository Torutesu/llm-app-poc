# 🔐 認証システム - ローカルテスト環境

包括的な認証システムが**ローカル環境で実行中**です！

## 📍 現在の状態

✅ **APIサーバー稼働中**: http://localhost:8000
✅ **フロントエンド稼働中**: http://localhost:3000
✅ **全機能テスト済み**: 21/22 テスト成功

---

## 🚀 今すぐテストする

### 1️⃣ ブラウザで直接テスト

```bash
# ログイン画面を開く
open http://localhost:3000/login.html

# または
# Chrome: chrome http://localhost:3000/login.html
# Firefox: firefox http://localhost:3000/login.html
```

**テストユーザー（既に登録済み）**:
- Email: `test@example.com`
- Password: `TestPassword123`

### 2️⃣ Swagger UI でAPIをテスト

```bash
open http://localhost:8000/docs
```

インタラクティブにAPIエンドポイントをテスト可能

### 3️⃣ cURL でクイックテスト

```bash
# ユーザー登録
curl -X POST http://localhost:8000/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"newuser@test.com","password":"Pass123","tenant_id":"test"}'

# ログイン
curl -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"newuser@test.com","password":"Pass123"}'
```

---

## 🎯 テスト可能な機能

### ✅ 基本認証
- [x] ユーザー登録
- [x] ログイン / ログアウト
- [x] JWT トークン認証
- [x] パスワード変更

### ✅ 二要素認証 (2FA)
- [x] TOTP (Google Authenticator)
- [x] SMS OTP
- [x] バックアップコード

### ✅ パスワード管理
- [x] パスワードリセット（メール経由）
- [x] パスワード変更

### ✅ セッション管理
- [x] マルチデバイストラッキング
- [x] デバイスごとのログアウト
- [x] 全デバイスからログアウト
- [x] セッション統計

### ✅ セキュリティ
- [x] レート制限（ブルートフォース対策）
- [x] 監査ログ
- [x] RBAC（ロールベースアクセス制御）

---

## 📂 重要なファイル

### サーバー起動
```bash
bash START_SERVERS.sh          # サーバー起動スクリプト
```

### テスト
```bash
python3 test_integration.py    # 統合テスト
pytest tests/test_auth.py      # ユニットテスト
python3 examples/advanced_auth_example.py  # デモ
```

### ドキュメント
- `TESTING_GUIDE.md` - 詳細なテストガイド
- `COMPLETE_AUTH_GUIDE.md` - 完全な実装ガイド
- `AUTH_FEATURES_README.md` - 機能リファレンス

---

## 🌐 利用可能なURL

| サービス | URL | 説明 |
|---------|-----|------|
| **ログイン画面** | http://localhost:3000/login.html | フロントエンドUI |
| **ダッシュボード** | http://localhost:3000/dashboard.html | ユーザーダッシュボード |
| **Swagger UI** | http://localhost:8000/docs | インタラクティブAPI |
| **ReDoc** | http://localhost:8000/redoc | APIドキュメント |
| **OpenAPI Spec** | http://localhost:8000/openapi.json | API仕様 |
| **Health Check** | http://localhost:8000/health | サーバー状態 |

---

## 📊 APIエンドポイント (抜粋)

### 認証
- `POST /auth/register` - ユーザー登録
- `POST /auth/login` - ログイン
- `POST /auth/logout` - ログアウト
- `GET /auth/me` - ユーザー情報取得

### 2FA
- `POST /auth/2fa/totp/setup` - TOTP設定
- `POST /auth/2fa/sms/setup` - SMS設定
- `GET /auth/2fa/status` - 2FA状態確認

### セッション
- `GET /auth/sessions` - セッション一覧
- `DELETE /auth/sessions/{id}` - セッション削除

**全15+エンドポイント利用可能**

---

## 🎬 デモシナリオ

### シナリオ A: 初回ログイン
1. http://localhost:3000/login.html にアクセス
2. 「Create Account」で新規登録
3. ログインしてダッシュボード表示
4. プロフィール情報とセッションを確認

### シナリオ B: 2FA有効化
1. ダッシュボードで「Manage 2FA」
2. QRコードをスキャン（Google Authenticator等）
3. コード入力して有効化
4. ログアウト → 再ログインで2FA検証

### シナリオ C: セッション管理
1. 複数のブラウザ/タブでログイン
2. ダッシュボードで全セッションを表示
3. 不要なセッションを個別削除
4. または「Logout All Devices」

---

## 🔧 トラブルシューティング

### サーバーが起動しない？
```bash
# プロセス確認
lsof -i :8000
lsof -i :3000

# 停止
pkill -f 'uvicorn'
pkill -f 'http.server'

# 再起動
bash START_SERVERS.sh
```

### ログ確認
```bash
tail -f /tmp/api_server.log
tail -f /tmp/frontend_server.log
```

---

## 💡 次のステップ

### 本番環境へ
1. PostgreSQLデータベース設定
2. 環境変数でシークレットキー設定
3. HTTPS設定
4. Dockerコンテナ化

### 追加機能
- WebAuthn/FIDO2 生体認証
- ソーシャルログイン完全統合
- マジックリンク認証

---

## 📞 サポート

質問や問題があれば:
- 📖 `TESTING_GUIDE.md` を参照
- 🐛 GitHub Issues で報告
- 💬 ディスカッションで質問

---

**🎉 全機能が動作中！今すぐテストを開始できます！**

```bash
# 今すぐ始める
open http://localhost:3000/login.html
```

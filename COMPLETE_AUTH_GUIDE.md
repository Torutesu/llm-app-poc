# Complete Authentication System Guide

包括的な認証システムの実装ガイドです。本番環境対応の認証システムを構築するための完全なドキュメントです。

## 目次

1. [概要](#概要)
2. [アーキテクチャ](#アーキテクチャ)
3. [実装済み機能](#実装済み機能)
4. [セットアップガイド](#セットアップガイド)
5. [API リファレンス](#apiリファレンス)
6. [セキュリティ](#セキュリティ)
7. [デプロイメント](#デプロイメント)
8. [トラブルシューティング](#トラブルシューティング)

---

## 概要

### システム構成

```
llm-app-poc/
├── auth/                    # 認証コアモジュール
│   ├── user_manager.py      # ユーザー管理
│   ├── jwt_handler.py       # JWT トークン処理
│   ├── two_factor.py        # 2要素認証 (TOTP/SMS)
│   ├── password_reset.py    # パスワードリセット
│   ├── session_manager.py   # セッション管理
│   ├── oauth_providers.py   # OAuth統合
│   └── auth_middleware.py   # 認証ミドルウェア
│
├── api/                     # FastAPI エンドポイント
│   ├── main.py             # メインアプリケーション
│   └── auth_api.py         # 認証API
│
├── database/               # データベース層
│   ├── models.py          # SQLAlchemy モデル
│   ├── connection.py      # DB接続管理
│   ├── repositories.py    # データアクセス層
│   └── init_db.py         # DB初期化スクリプト
│
├── security/              # セキュリティ機能
│   ├── rate_limiter.py   # レート制限
│   └── audit_logger.py   # 監査ログ
│
├── frontend/              # フロントエンドUI
│   ├── login.html        # ログイン画面
│   ├── dashboard.html    # ダッシュボード
│   └── 2fa-setup.html    # 2FA設定画面
│
├── tests/                 # テストスイート
│   └── test_auth.py      # 認証テスト
│
└── examples/              # 実装例
    ├── auth_flow_example.py
    └── advanced_auth_example.py
```

### 主な技術スタック

- **Backend**: Python 3.9+, FastAPI, SQLAlchemy
- **Database**: PostgreSQL
- **Authentication**: JWT, TOTP (pyotp), OAuth 2.0
- **Frontend**: HTML/CSS/JavaScript (Vanilla JS)
- **Testing**: pytest

---

## アーキテクチャ

### レイヤー構造

```
┌─────────────────────────────────────────┐
│         Frontend (HTML/JS)              │
├─────────────────────────────────────────┤
│      FastAPI REST API Layer             │
│  (/auth/login, /auth/2fa, etc.)        │
├─────────────────────────────────────────┤
│     Business Logic Layer                │
│  (UserManager, TwoFactorManager, etc.)  │
├─────────────────────────────────────────┤
│      Data Access Layer                  │
│  (Repositories, SQLAlchemy ORM)        │
├─────────────────────────────────────────┤
│       PostgreSQL Database               │
└─────────────────────────────────────────┘
```

### 認証フロー

#### 1. 基本ログイン
```
User → POST /auth/login → Verify Password → Return JWT
```

#### 2. 2FA有効時のログイン
```
User → POST /auth/login → Verify Password → Return requires_2fa=true
     → POST /auth/login/2fa → Verify 2FA Code → Return JWT
```

#### 3. セッション管理
```
Login → Create Session (with device info) → Return Session ID
      → Validate Session on each request
      → Logout → Invalidate Session
```

---

## 実装済み機能

### ✅ 完了した機能

#### 1. ユーザー認証
- ✅ メール/パスワード認証
- ✅ JWT トークン発行・検証
- ✅ アクセストークン/リフレッシュトークン
- ✅ トークン更新
- ✅ OAuth 2.0 統合 (Google, Microsoft, GitHub対応)

#### 2. 二要素認証 (2FA)
- ✅ TOTP (Google Authenticator, Authy対応)
- ✅ SMS OTP
- ✅ バックアップコード (10個自動生成)
- ✅ 複数方式対応 (TOTP + SMS同時有効化可能)

#### 3. パスワード管理
- ✅ パスワードリセット (メール経由)
- ✅ パスワード変更 (現在のパスワード必須)
- ✅ セキュアなトークン生成 (24時間有効)
- ✅ 確認メール送信

#### 4. セッション管理
- ✅ マルチデバイスセッション追跡
- ✅ デバイス情報記録 (OS, ブラウザ, IP, 位置情報)
- ✅ デバイスごとのログアウト
- ✅ 全デバイスからのログアウト
- ✅ セッション有効期限管理
- ✅ セッション統計情報

#### 5. セキュリティ機能
- ✅ レート制限 (ログイン、2FA、APIコール等)
- ✅ 監査ログ (全認証イベント記録)
- ✅ PBKDF2-SHA256 パスワードハッシュ化
- ✅ トークンハッシュ化保存
- ✅ ブルートフォース攻撃対策

#### 6. API エンドポイント
- ✅ 完全なRESTful API (FastAPI)
- ✅ OpenAPI/Swagger ドキュメント自動生成
- ✅ CORS設定
- ✅ エラーハンドリング

#### 7. データベース統合
- ✅ PostgreSQL + SQLAlchemy ORM
- ✅ リポジトリパターン実装
- ✅ マイグレーション対応
- ✅ インデックス最適化

#### 8. フロントエンドUI
- ✅ ログイン画面
- ✅ ダッシュボード
- ✅ セッション管理UI
- ✅ レスポンシブデザイン

#### 9. テスト
- ✅ pytest テストスイート
- ✅ ユニットテスト (認証、2FA、セッション等)
- ✅ モックプロバイダー

### 📋 今後実装予定の機能

#### ソーシャルログイン拡張
- [ ] Google OAuth完全統合
- [ ] GitHub OAuth完全統合
- [ ] Microsoft OAuth完全統合
- [ ] プロバイダー自動リンク機能

#### 生体認証
- [ ] WebAuthn/FIDO2 サポート
- [ ] 指紋認証・顔認証対応
- [ ] セキュリティキー (YubiKey等) サポート

#### 追加機能
- [ ] パスワードレスログイン (Magic Link)
- [ ] ソーシャルリカバリー
- [ ] デバイス信頼管理

---

## セットアップガイド

### 前提条件

- Python 3.9以上
- PostgreSQL 12以上
- Node.js (フロントエンド開発用、オプション)

### 1. 環境構築

```bash
# リポジトリクローン
git clone <repository-url>
cd llm-app-poc

# Python仮想環境作成
python3 -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 依存パッケージインストール
pip install -r auth/requirements.txt
pip install -r api/requirements.txt
pip install -r database/requirements.txt
pip install -r tests/requirements.txt
```

### 2. データベースセットアップ

```bash
# PostgreSQLデータベース作成
createdb llm_app_auth

# 環境変数設定
export DATABASE_URL="postgresql://postgres:postgres@localhost:5432/llm_app_auth"

# テーブル作成
python database/init_db.py

# テストデータ投入 (オプション)
python database/init_db.py --seed
```

### 3. 設定

環境変数を設定するか、`.env`ファイルを作成:

```bash
# .env ファイル
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/llm_app_auth
JWT_SECRET_KEY=your-super-secret-key-change-in-production
API_BASE_URL=http://localhost:8000
FRONTEND_URL=http://localhost:3000

# SMS設定 (Twilio)
TWILIO_ACCOUNT_SID=your_account_sid
TWILIO_AUTH_TOKEN=your_auth_token
TWILIO_PHONE_NUMBER=+1234567890

# メール設定 (SendGrid)
SENDGRID_API_KEY=your_api_key
SENDGRID_FROM_EMAIL=noreply@yourdomain.com
```

### 4. APIサーバー起動

```bash
# 開発モード
cd api
uvicorn main:app --reload --port 8000

# 本番モード
uvicorn main:app --host 0.0.0.0 --port 8000 --workers 4
```

APIドキュメント: http://localhost:8000/docs

### 5. フロントエンド起動

```bash
# 簡易HTTPサーバー
cd frontend
python3 -m http.server 3000

# または
npx http-server -p 3000
```

アプリケーション: http://localhost:3000/login.html

### 6. テスト実行

```bash
# 全テスト実行
pytest tests/ -v

# カバレッジ付き
pytest tests/ --cov=auth --cov=api --cov-report=html

# 特定のテストのみ
pytest tests/test_auth.py::TestUserManager -v
```

---

## APIリファレンス

### 認証エンドポイント

#### `POST /auth/register`
ユーザー登録

**Request:**
```json
{
  "email": "user@example.com",
  "password": "SecurePassword123!",
  "name": "John Doe",
  "tenant_id": "tenant_001"
}
```

**Response:**
```json
{
  "user_id": "user_abc123",
  "email": "user@example.com",
  "message": "User registered successfully"
}
```

#### `POST /auth/login`
ログイン

**Request:**
```json
{
  "email": "user@example.com",
  "password": "SecurePassword123!"
}
```

**Response (2FA無効時):**
```json
{
  "access_token": "eyJ0eXAiOiJKV1QiLCJhbGc...",
  "refresh_token": "eyJ0eXAiOiJKV1QiLCJhbGc...",
  "token_type": "Bearer",
  "expires_in": 1800,
  "requires_2fa": false,
  "session_id": "sess_xyz789"
}
```

**Response (2FA有効時):**
```json
{
  "requires_2fa": true,
  "access_token": "",
  "refresh_token": "",
  "token_type": "Bearer",
  "expires_in": 0
}
```

#### `POST /auth/login/2fa`
2FA検証

**Request:**
```json
{
  "user_id": "user_abc123",
  "code": "123456"
}
```

#### `POST /auth/logout`
ログアウト

**Headers:**
```
Authorization: Bearer <access_token>
X-Session-ID: <session_id>
```

#### `POST /auth/logout-all`
全デバイスからログアウト

### 2FA エンドポイント

#### `POST /auth/2fa/totp/setup`
TOTP設定開始

**Response:**
```json
{
  "secret": "JBSWY3DPEHPK3PXP",
  "provisioning_uri": "otpauth://totp/...",
  "qr_code_url": "https://api.qrserver.com/..."
}
```

#### `POST /auth/2fa/totp/verify-setup`
TOTP設定完了

**Request:**
```json
{
  "code": "123456"
}
```

#### `GET /auth/2fa/status`
2FA状態確認

**Response:**
```json
{
  "enabled": true,
  "methods": ["totp", "sms"],
  "preferred_method": "totp"
}
```

### セッション管理エンドポイント

#### `GET /auth/sessions`
アクティブセッション一覧

**Response:**
```json
[
  {
    "session_id": "sess_abc123",
    "device_name": "MacBook Pro",
    "device_type": "desktop",
    "os": "macOS",
    "browser": "Chrome",
    "ip_address": "192.168.1.100",
    "location": "Tokyo, Japan",
    "created_at": "2025-01-01T00:00:00",
    "last_activity_at": "2025-01-01T12:00:00",
    "is_current": true
  }
]
```

#### `DELETE /auth/sessions/{session_id}`
特定セッション削除

### ユーザー情報エンドポイント

#### `GET /auth/me`
現在のユーザー情報取得

**Response:**
```json
{
  "user_id": "user_abc123",
  "email": "user@example.com",
  "name": "John Doe",
  "roles": ["editor"],
  "permissions": ["read:documents", "write:documents"],
  "is_verified": true,
  "created_at": "2025-01-01T00:00:00",
  "last_login_at": "2025-01-01T12:00:00"
}
```

---

## セキュリティ

### 実装済みセキュリティ機能

#### 1. パスワードセキュリティ
- PBKDF2-SHA256 ハッシュ化 (100,000イテレーション)
- ソルト付きハッシュ
- 最小8文字要求

#### 2. トークンセキュリティ
- JWT with HS256署名
- アクセストークン: 30分有効
- リフレッシュトークン: 7日有効
- トークン失効機能

#### 3. レート制限
```python
limits = {
    "login": {
        "max_attempts": 5,
        "window_seconds": 900,  # 15分
        "block_seconds": 3600   # 1時間ブロック
    },
    "2fa": {
        "max_attempts": 3,
        "window_seconds": 300,
        "block_seconds": 1800
    }
}
```

#### 4. 監査ログ
すべての認証イベントを記録:
- ログイン試行 (成功/失敗)
- 2FA検証
- パスワード変更
- セッション操作
- 不審な活動

#### 5. セッションセキュリティ
- デバイスフィンガープリント
- IP アドレス追跡
- 異常なロケーション検出
- セッションハイジャック対策

### セキュリティベストプラクティス

#### 本番環境での必須設定

1. **強力なシークレットキー**
```python
# 256ビット以上のランダムキー
JWT_SECRET_KEY = secrets.token_urlsafe(32)
```

2. **HTTPS必須**
```python
# すべてのトラフィックをHTTPSにリダイレクト
app.add_middleware(HTTPSRedirectMiddleware)
```

3. **CORS設定**
```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://yourdomain.com"],  # 特定のオリジンのみ
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["*"],
)
```

4. **環境変数で機密情報管理**
```bash
# 絶対にコードにハードコードしない
export JWT_SECRET_KEY=<random-secret>
export DATABASE_URL=postgresql://...
export SENDGRID_API_KEY=<key>
```

5. **データベース暗号化**
```python
# 機密データ (TOTP secret等) は暗号化して保存
from cryptography.fernet import Fernet

cipher = Fernet(encryption_key)
encrypted_secret = cipher.encrypt(totp_secret.encode())
```

---

## デプロイメント

### Docker デプロイメント

```dockerfile
# Dockerfile
FROM python:3.9-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

```yaml
# docker-compose.yml
version: '3.8'

services:
  db:
    image: postgres:14
    environment:
      POSTGRES_DB: llm_app_auth
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: postgres
    volumes:
      - postgres_data:/var/lib/postgresql/data

  api:
    build: .
    ports:
      - "8000:8000"
    environment:
      DATABASE_URL: postgresql://postgres:postgres@db:5432/llm_app_auth
      JWT_SECRET_KEY: ${JWT_SECRET_KEY}
    depends_on:
      - db

volumes:
  postgres_data:
```

### Kubernetes デプロイメント

```yaml
# k8s/deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: auth-api
spec:
  replicas: 3
  selector:
    matchLabels:
      app: auth-api
  template:
    metadata:
      labels:
        app: auth-api
    spec:
      containers:
      - name: auth-api
        image: your-registry/auth-api:latest
        ports:
        - containerPort: 8000
        env:
        - name: DATABASE_URL
          valueFrom:
            secretKeyRef:
              name: auth-secrets
              key: database-url
        - name: JWT_SECRET_KEY
          valueFrom:
            secretKeyRef:
              name: auth-secrets
              key: jwt-secret
```

---

## トラブルシューティング

### よくある問題

#### 1. データベース接続エラー
```
sqlalchemy.exc.OperationalError: could not connect to server
```

**解決策:**
- PostgreSQLが起動しているか確認: `pg_isready`
- 接続文字列を確認: `echo $DATABASE_URL`
- ファイアウォール設定を確認

#### 2. JWT検証エラー
```
jwt.InvalidTokenError: Signature verification failed
```

**解決策:**
- シークレットキーが一致しているか確認
- トークンの有効期限を確認
- トークン形式が正しいか確認 (`Bearer <token>`)

#### 3. 2FAコードが一致しない
```
Invalid TOTP code
```

**解決策:**
- デバイスの時刻同期を確認
- TOTPシークレットが正しく保存されているか確認
- `valid_window`パラメータを調整 (時刻のずれを許容)

#### 4. レート制限に引っかかる
```
Rate limit exceeded
```

**解決策:**
- 一定時間待つ
- 開発環境では制限を緩和する
- 本番環境では正常な挙動

### ログ確認

```bash
# API ログ
tail -f logs/api.log

# 監査ログ
tail -f logs/audit.log

# データベースログ
tail -f /var/log/postgresql/postgresql-14-main.log
```

---

## パフォーマンス最適化

### データベース最適化

1. **インデックス**
```sql
CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_sessions_user_active ON sessions(user_id, is_active);
CREATE INDEX idx_audit_created ON audit_logs(created_at);
```

2. **接続プール**
```python
engine = create_engine(
    DATABASE_URL,
    pool_size=20,
    max_overflow=40,
    pool_pre_ping=True
)
```

### キャッシング

```python
# Redis でセッションキャッシュ
import redis

redis_client = redis.Redis(host='localhost', port=6379)

# セッション情報をキャッシュ
redis_client.setex(
    f"session:{session_id}",
    3600,  # 1時間
    json.dumps(session_data)
)
```

---

## まとめ

このシステムは本番環境対応の包括的な認証システムです。

### 主な特徴
✅ エンタープライズグレードのセキュリティ
✅ スケーラブルなアーキテクチャ
✅ 完全なAPI＋フロントエンド
✅ テスト済み
✅ ドキュメント完備

### 次のステップ
1. 本番環境へのデプロイ
2. モニタリング・アラート設定
3. 定期的なセキュリティ監査
4. ユーザーフィードバックの収集

ご質問やサポートが必要な場合は、Issueを作成してください。

# 認証システム実装ガイド

このガイドでは、JWT/OAuth2.0ベースの認証・認可システムの使い方を説明します。

## 📋 目次

1. [概要](#概要)
2. [アーキテクチャ](#アーキテクチャ)
3. [実装されたコンポーネント](#実装されたコンポーネント)
4. [セットアップ](#セットアップ)
5. [使い方](#使い方)
6. [API エンドポイント](#api-エンドポイント)
7. [セキュリティベストプラクティス](#セキュリティベストプラクティス)

---

## 概要

実装された認証システムの特徴：

✅ **JWT (JSON Web Token)** - ステートレス認証
✅ **OAuth 2.0** - Google, Microsoft, Okta, Auth0対応
✅ **RBAC (Role-Based Access Control)** - ロールベースの権限管理
✅ **マルチテナント対応** - テナント分離
✅ **トークンリフレッシュ** - アクセストークンの更新
✅ **パスワードハッシング** - PBKDF2-SHA256

---

## アーキテクチャ

```
┌─────────────────────────────────────────────────────┐
│                   Client (UI)                       │
└───────────────────┬─────────────────────────────────┘
                    │
         ┌──────────┴──────────┐
         │                     │
    ┌────▼────┐          ┌────▼────────┐
    │ Login   │          │ OAuth       │
    │ (Email/ │          │ (Google/    │
    │ Pass)   │          │ Microsoft)  │
    └────┬────┘          └────┬────────┘
         │                    │
         └──────────┬─────────┘
                    │
         ┌──────────▼──────────┐
         │  Auth Middleware    │
         │  - JWT Validation   │
         │  - Tenant Check     │
         │  - Permission Check │
         └──────────┬──────────┘
                    │
         ┌──────────▼──────────┐
         │  Pathway RAG API    │
         │  - Search           │
         │  - Summarize        │
         │  - Answer           │
         └─────────────────────┘
```

---

## 実装されたコンポーネント

### 📂 ファイル構成

```
llm-app-poc/
├── auth/
│   ├── jwt_handler.py          # JWT生成・検証
│   ├── oauth_providers.py      # OAuth統合 (Google, Microsoft, etc.)
│   ├── auth_middleware.py      # 認証ミドルウェア・RBAC
│   └── user_manager.py         # ユーザー管理
├── templates/
│   └── authenticated_rag/
│       └── app.py              # 認証付きRAGアプリ
├── examples/
│   └── auth_flow_example.py    # 使用例
└── AUTHENTICATION_GUIDE.md     # このドキュメント
```

---

## セットアップ

### 1. 依存パッケージのインストール

```bash
pip install pyjwt httpx pydantic python-dotenv
```

### 2. 環境変数の設定

`.env`ファイルを作成：

```bash
# JWT Settings
JWT_SECRET_KEY=your-super-secret-key-change-in-production-use-long-random-string
JWT_EXPIRE_MINUTES=30
JWT_REFRESH_DAYS=7

# Deployment
DEPLOYMENT_MODE=multi_tenant  # or single_tenant
TENANT_ID=your_tenant_id      # (single-tenant mode only)

# OAuth (Optional)
GOOGLE_CLIENT_ID=your-google-client-id
GOOGLE_CLIENT_SECRET=your-google-client-secret
GOOGLE_REDIRECT_URI=https://yourapp.com/auth/callback

MICROSOFT_CLIENT_ID=your-microsoft-client-id
MICROSOFT_CLIENT_SECRET=your-microsoft-client-secret
MICROSOFT_TENANT_ID=common

OKTA_DOMAIN=dev-123456.okta.com
OKTA_CLIENT_ID=your-okta-client-id
OKTA_CLIENT_SECRET=your-okta-client-secret
```

### 3. サンプル実行

```bash
cd llm-app-poc
python examples/auth_flow_example.py
```

---

## 使い方

### 1️⃣ **ユーザー作成**

```python
from auth.jwt_handler import JWTConfig, JWTHandler
from auth.user_manager import UserManager
from auth.auth_middleware import Roles

# JWT設定
jwt_config = JWTConfig(
    secret_key="your-secret-key",
    access_token_expire_minutes=30
)

jwt_handler = JWTHandler(jwt_config)
user_manager = UserManager(jwt_handler)

# ユーザー作成
user = user_manager.create_user(
    email="alice@company.com",
    tenant_id="company_xyz",
    password="secure_password_123",
    name="Alice Smith",
    roles=[Roles.ADMIN]
)

print(f"Created user: {user.user_id}")
```

### 2️⃣ **ログイン（パスワード認証）**

```python
# 認証
authenticated_user = user_manager.authenticate_password(
    "alice@company.com",
    "secure_password_123"
)

if authenticated_user:
    # JWTトークン生成
    tokens = user_manager.create_tokens_for_user(authenticated_user)

    print(f"Access Token: {tokens['access_token']}")
    print(f"Refresh Token: {tokens['refresh_token']}")
    print(f"Expires in: {tokens['expires_in']} seconds")
```

### 3️⃣ **OAuth認証（Google）**

```python
from auth.oauth_providers import GoogleOAuthProvider, OAuthConfig

# Google OAuth設定
config = OAuthConfig(
    provider_name="google",
    client_id="your-google-client-id",
    client_secret="your-google-client-secret",
    redirect_uri="https://yourapp.com/auth/callback",
    scopes=["openid", "email", "profile"]
)

provider = GoogleOAuthProvider(config)

# ステップ1: 認証URLを生成してユーザーをリダイレクト
auth_url = provider.get_authorization_url(state="random_csrf_token")
print(f"Redirect user to: {auth_url}")

# ステップ2: コールバックでcodeを受け取る
# (ユーザーが承認後、https://yourapp.com/auth/callback?code=AUTH_CODE にリダイレクト)

# ステップ3: codeをトークンに交換
token_data = await provider.exchange_code_for_token(code="AUTH_CODE")

# ステップ4: ユーザー情報を取得
user_info = await provider.get_user_info(token_data['access_token'])

# ステップ5: システムにユーザーを作成
oauth_user = user_manager.create_oauth_user(
    oauth_info=user_info,
    tenant_id="company_xyz",
    roles=[Roles.VIEWER]
)

# JWTトークン生成
tokens = user_manager.create_tokens_for_user(oauth_user)
```

### 4️⃣ **トークン検証とAPI呼び出し**

```python
from auth.auth_middleware import AuthMiddleware, Permissions

auth_middleware = AuthMiddleware(jwt_handler)

# APIリクエストのシミュレーション
request_data = {
    "headers": {
        "Authorization": f"Bearer {tokens['access_token']}"
    },
    "body": {
        "query": "Show engineering documents"
    }
}

# 認証
try:
    authenticated_request = auth_middleware.authenticate_request(request_data)

    # 権限チェック
    auth_middleware.require_permission(
        authenticated_request,
        Permissions.SEARCH
    )

    print("✓ User authenticated and authorized")
    print(f"User ID: {authenticated_request['user_id']}")
    print(f"Tenant ID: {authenticated_request['tenant_id']}")
    print(f"Roles: {authenticated_request['user_roles']}")

except Exception as e:
    print(f"✗ Authentication failed: {e}")
```

### 5️⃣ **トークンリフレッシュ**

```python
# アクセストークンが期限切れの場合
try:
    new_access_token = jwt_handler.refresh_access_token(
        refresh_token=tokens['refresh_token']
    )

    print(f"New access token: {new_access_token}")

except Exception as e:
    print(f"Refresh failed: {e}")
    # ユーザーに再ログインを促す
```

---

## API エンドポイント

### 認証エンドポイント

#### `POST /v1/auth/login`

メール/パスワードでログイン

**リクエスト:**
```bash
curl -X POST https://api.yourapp.com/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "email": "alice@company.com",
    "password": "secure_password_123"
  }'
```

**レスポンス:**
```json
{
  "user_id": "user_a1b2c3d4_e5f6g7h8",
  "email": "alice@company.com",
  "tenant_id": "company_xyz",
  "roles": ["admin"],
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "Bearer",
  "expires_in": 1800
}
```

#### `POST /v1/auth/refresh`

アクセストークンを更新

**リクエスト:**
```bash
curl -X POST https://api.yourapp.com/v1/auth/refresh \
  -H "Content-Type: application/json" \
  -d '{
    "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
  }'
```

**レスポンス:**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "Bearer",
  "expires_in": 1800
}
```

#### `GET /v1/auth/me`

現在のユーザー情報を取得

**リクエスト:**
```bash
curl -X GET https://api.yourapp.com/v1/auth/me \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
```

**レスポンス:**
```json
{
  "user_id": "user_a1b2c3d4_e5f6g7h8",
  "email": "alice@company.com",
  "name": "Alice Smith",
  "tenant_id": "company_xyz",
  "roles": ["admin"],
  "permissions": [
    "read:documents",
    "write:documents",
    "delete:documents",
    "search",
    "..."
  ],
  "is_active": true
}
```

### 保護されたエンドポイント

#### `POST /v2/answer`

認証が必要な検索・質問応答

**リクエスト:**
```bash
curl -X POST https://api.yourapp.com/v2/answer \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..." \
  -H "Content-Type: application/json" \
  -d '{
    "query": "What is our Q4 revenue?"
  }'
```

**レスポンス:**
```json
{
  "query": "What is our Q4 revenue?",
  "result": "Based on the financial documents...",
  "user_id": "user_a1b2c3d4_e5f6g7h8",
  "tenant_id": "company_xyz"
}
```

---

## ロールと権限

### 標準ロール

| ロール | 説明 | 権限 |
|--------|------|------|
| `admin` | 管理者 | すべての操作 |
| `editor` | 編集者 | 読み取り、書き込み、検索 |
| `viewer` | 閲覧者 | 読み取り、検索のみ |
| `guest` | ゲスト | 読み取りのみ |

### 標準権限

```python
from auth.auth_middleware import Permissions

# ドキュメント権限
Permissions.READ_DOCUMENTS
Permissions.WRITE_DOCUMENTS
Permissions.DELETE_DOCUMENTS

# 検索権限
Permissions.SEARCH
Permissions.ADVANCED_SEARCH

# ユーザー管理
Permissions.READ_USERS
Permissions.WRITE_USERS
Permissions.DELETE_USERS

# 設定
Permissions.READ_SETTINGS
Permissions.WRITE_SETTINGS

# アナリティクス
Permissions.READ_ANALYTICS
```

### カスタム権限の追加

```python
# ユーザーにカスタム権限を付与
user_manager.add_permission(
    user_id="user_123",
    permission="custom:export_data"
)

# エンドポイントで権限チェック
auth_middleware.require_permission(
    request_data,
    "custom:export_data"
)
```

---

## セキュリティベストプラクティス

### 🔒 **JWT Secret Key**

```bash
# 強力なランダム文字列を生成
python -c "import secrets; print(secrets.token_urlsafe(64))"

# 環境変数に設定（絶対にコードにハードコードしない）
export JWT_SECRET_KEY="生成された文字列"
```

### 🕒 **トークン有効期限**

```python
# 推奨設定
jwt_config = JWTConfig(
    access_token_expire_minutes=30,    # 短め（15-30分）
    refresh_token_expire_days=7        # 長め（7-30日）
)
```

### 🔐 **HTTPS必須**

```python
# 本番環境では必ずHTTPSを使用
if not request.is_secure and not IS_DEVELOPMENT:
    raise SecurityError("HTTPS required")
```

### 🚫 **レート制限**

```python
# APIエンドポイントにレート制限を実装
# 例: Redis + sliding window algorithm
```

### 📝 **監査ログ**

```python
# すべての認証イベントをログ記録
logger.info(
    f"Login attempt: email={email}, "
    f"ip={request.remote_addr}, "
    f"success={authenticated}"
)
```

### 🔑 **パスワードポリシー**

```python
def validate_password(password: str) -> bool:
    """
    パスワード強度チェック:
    - 最低8文字
    - 大文字・小文字・数字を含む
    - 特殊文字を含む
    """
    import re

    if len(password) < 8:
        return False

    if not re.search(r"[a-z]", password):
        return False

    if not re.search(r"[A-Z]", password):
        return False

    if not re.search(r"\d", password):
        return False

    if not re.search(r"[!@#$%^&*(),.?\":{}|<>]", password):
        return False

    return True
```

---

## 次のステップ

✅ **完了した機能:**
- JWT認証基盤
- OAuth 2.0統合 (Google, Microsoft, Okta, Auth0)
- 認証ミドルウェア
- RBAC (Role-Based Access Control)
- ユーザー管理システム
- トークンリフレッシュ

🚧 **次に実装すべき機能:**
1. **PostgreSQLへの移行** - インメモリから永続化DBへ
2. **ドキュメントレベル権限** - ファイル/フォルダごとのアクセス制御
3. **監査ログ** - アクセス履歴の記録
4. **2要素認証 (2FA)** - TOTPベースの追加認証
5. **パスワードリセット** - メール経由のパスワード変更

---

## トラブルシューティング

### エラー: "Invalid token"

**原因:** トークンの署名検証失敗

**解決策:**
- `JWT_SECRET_KEY`が正しいか確認
- トークンが改ざんされていないか確認
- トークン形式が正しいか確認 (`Bearer <token>`)

### エラー: "Token has expired"

**原因:** アクセストークンの有効期限切れ

**解決策:**
- リフレッシュトークンを使用して新しいアクセストークンを取得
- `/v1/auth/refresh` エンドポイントを呼び出す

### エラー: "Tenant mismatch"

**原因:** ユーザーのテナントとリソースのテナントが一致しない

**解決策:**
- ユーザーのテナントIDを確認
- リクエストが正しいテナントのリソースを要求しているか確認

---

## まとめ

このガイドで実装された認証システムにより、以下が実現できます：

✅ エンタープライズグレードの認証・認可
✅ マルチテナント対応のセキュアなデータアクセス
✅ OAuth統合によるシームレスなSSO
✅ きめ細かいRBACによる権限管理
✅ スケーラブルなJWTベースの認証

Glean.comのようなエンタープライズSaaSに必要な認証基盤が整いました！

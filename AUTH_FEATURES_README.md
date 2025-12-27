# Advanced Authentication Features

このドキュメントでは、実装された高度な認証機能について説明します。

## 実装済み機能

### 1. 二要素認証 (2FA)

#### TOTP (Time-based One-Time Password)
- Google Authenticator、Authy などの認証アプリに対応
- QRコードベースのセットアップ
- 6桁のワンタイムコード検証
- バックアップコード生成（アカウント復旧用）

**実装ファイル**: [auth/two_factor.py](auth/two_factor.py)

**主な機能**:
- `setup_totp()`: TOTP設定の開始（QRコード生成）
- `verify_totp_setup()`: TOTP設定の検証と有効化
- `verify_totp()`: ログイン時のTOTP検証
- `disable_totp()`: TOTP無効化

**使用例**:
```python
from auth.two_factor import TwoFactorManager

tfa_manager = TwoFactorManager()

# TOTP設定
setup_data = tfa_manager.setup_totp(
    user_id="user_123",
    user_email="user@example.com"
)
# setup_data には secret、provisioning_uri、qr_code_url が含まれる

# ユーザーがQRコードをスキャンしてコードを入力
verified = tfa_manager.verify_totp_setup(user_id="user_123", code="123456")

# ログイン時の検証
is_valid = tfa_manager.verify_totp(user_id="user_123", code="654321")
```

#### SMS OTP
- 電話番号へのワンタイムパスワード送信
- 5分間有効なOTPコード
- SMS プロバイダー統合（Twilio、AWS SNS など）

**主な機能**:
- `setup_sms()`: SMS 2FA設定の開始
- `send_sms_otp()`: OTPコードの送信
- `verify_sms_otp()`: OTPコードの検証
- `disable_sms()`: SMS 2FA無効化

**使用例**:
```python
# SMS設定（検証コード送信）
tfa_manager.setup_sms(
    user_id="user_123",
    phone_number="+1234567890"
)

# ユーザーがSMSで受信したコードを入力
verified = tfa_manager.verify_sms_setup(user_id="user_123", code="123456")

# ログイン時にOTP送信
tfa_manager.send_sms_otp(user_id="user_123", phone_number="+1234567890")
is_valid = tfa_manager.verify_sms_otp(user_id="user_123", code="654321")
```

#### バックアップコード
- アカウント復旧用の10個のバックアップコード
- 使い切り（一度使用したら無効化）
- 再生成機能

**主な機能**:
- `verify_backup_code()`: バックアップコードの検証
- `regenerate_backup_codes()`: バックアップコードの再生成

### 2. パスワードリセット

メール経由の安全なパスワード変更機能。

**実装ファイル**: [auth/password_reset.py](auth/password_reset.py)

**主な機能**:
- `request_password_reset()`: リセットメールの送信
- `validate_reset_token()`: リセットトークンの検証
- `reset_password()`: パスワードのリセット実行

**フロー**:
1. ユーザーがメールアドレスを入力してリセットを要求
2. セキュアなトークンを生成してメール送信
3. ユーザーがメール内のリンクをクリック
4. トークンを検証して新しいパスワードを設定
5. 確認メールを送信

**セキュリティ機能**:
- トークンは24時間で有効期限切れ
- トークンはハッシュ化して保存
- 一度使用したトークンは無効化
- パスワード変更後に確認メール送信

**使用例**:
```python
from auth.password_reset import PasswordResetManager
from auth.user_manager import UserManager

# UserManagerに統合されています
user_manager = UserManager(jwt_handler, password_reset_manager)

# リセット要求
user_manager.request_password_reset(email="user@example.com")

# ユーザーがメールのリンクからトークンを取得
# トークンを使ってパスワードリセット
success = user_manager.reset_password_with_token(
    token="token_from_email_link",
    new_password="NewSecurePassword123!"
)

# 現在のパスワードを知っている場合の変更
user_manager.change_password(
    user_id="user_123",
    old_password="CurrentPassword",
    new_password="NewPassword123!"
)
```

**統合**: `UserManager` に `request_password_reset()` と `reset_password_with_token()` メソッドとして統合済み

### 3. セッション管理

アクティブセッションの追跡と管理機能。

**実装ファイル**: [auth/session_manager.py](auth/session_manager.py)

**主な機能**:
- `create_session()`: 新しいセッションの作成
- `validate_session()`: セッションの検証と更新
- `invalidate_session()`: 特定セッションの無効化
- `invalidate_all_user_sessions()`: 全デバイスからログアウト
- `list_user_sessions()`: ユーザーのセッション一覧
- `get_session_statistics()`: セッション統計情報

**トラッキング情報**:
- デバイスタイプ（モバイル、デスクトップ、タブレット）
- デバイス名
- OS（Windows、macOS、Linux、iOS、Android）
- ブラウザ（Chrome、Firefox、Safari、Edge）
- IPアドレス
- 地理的位置
- 最終アクティビティ時刻

**セッション管理機能**:
- セッション有効期限管理（デフォルト7日間）
- デバイスごとのログアウト
- 全デバイスからログアウト（現在のセッション除外可能）
- セッション数制限（デフォルト10セッション）
- 自動クリーンアップ

**使用例**:
```python
from auth.session_manager import SessionManager, DeviceInfo, parse_user_agent

session_manager = SessionManager(session_expire_hours=168)  # 7日間

# ログイン時にセッション作成
user_agent = request.headers.get("User-Agent")
device_info_parsed = parse_user_agent(user_agent)

session = session_manager.create_session(
    user_id="user_123",
    tenant_id="tenant_456",
    device_info=DeviceInfo(
        user_agent=user_agent,
        ip_address="192.168.1.100",
        device_type=device_info_parsed["device_type"],
        os=device_info_parsed["os"],
        browser=device_info_parsed["browser"],
        device_name="My MacBook Pro",
        location="Tokyo, Japan"
    ),
    is_current=True
)

# リクエストごとにセッション検証
session = session_manager.validate_session(session_id)

# アクティブセッション一覧
sessions = session_manager.list_user_sessions(user_id="user_123")

# 特定デバイスからログアウト
session_manager.invalidate_session(
    session_id="sess_abc123",
    reason="user_logout"
)

# 全デバイスからログアウト
session_manager.invalidate_all_user_sessions(
    user_id="user_123",
    except_session_id="current_session",  # 現在のセッションは維持
    reason="logout_all_devices"
)

# セッション統計
stats = session_manager.get_session_statistics(user_id="user_123")
# {
#   "total_sessions": 5,
#   "active_sessions": 3,
#   "expired_sessions": 1,
#   "invalidated_sessions": 1,
#   "average_duration_hours": 12.5,
#   "devices": ["desktop", "mobile"],
#   "locations": ["Tokyo, Japan", "Osaka, Japan"]
# }
```

## インストール

必要なパッケージをインストール:

```bash
cd auth
pip install -r requirements.txt
```

主な依存関係:
- `PyJWT`: JWT トークン処理
- `pyotp`: TOTP実装
- `pydantic`: データ検証
- `email-validator`: メールアドレス検証

## 実行例

完全な実装例を確認:

```bash
python examples/advanced_auth_example.py
```

このスクリプトは以下のデモを実行します:
1. TOTP 2FA のセットアップとログイン
2. SMS 2FA のセットアップとログイン
3. パスワードリセットフロー
4. マルチデバイスセッション管理

## 本番環境への展開

### データベース統合

現在の実装はインメモリストレージを使用していますが、本番環境では以下の統合が必要です:

#### PostgreSQL
```python
# ユーザー、セッション、リセットトークンの永続化
import psycopg2

# テーブル設計例:
# - users (user_id, email, password_hash, ...)
# - user_2fa_config (user_id, totp_secret, phone_number, ...)
# - sessions (session_id, user_id, device_info, ...)
# - password_reset_tokens (token_hash, user_id, expires_at, ...)
```

#### Redis
```python
# セッションとOTPの高速ストレージ
import redis

redis_client = redis.Redis(host='localhost', port=6379, db=0)

# セッション管理
redis_client.setex(f"session:{session_id}", 3600, session_data)

# SMS OTP（5分間）
redis_client.setex(f"sms_otp:{user_id}", 300, otp_code)
```

### 外部サービス統合

#### Twilio (SMS)
```python
from twilio.rest import Client

client = Client(account_sid, auth_token)

message = client.messages.create(
    body="Your code is: 123456",
    from_="+1234567890",
    to=phone_number
)
```

#### SendGrid (Email)
```python
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail

message = Mail(
    from_email='noreply@example.com',
    to_emails=user_email,
    subject='Password Reset',
    html_content=reset_email_html
)

sg = SendGridAPIClient(api_key)
response = sg.send(message)
```

#### AWS SNS (SMS)
```python
import boto3

sns_client = boto3.client('sns', region_name='us-east-1')

response = sns_client.publish(
    PhoneNumber=phone_number,
    Message=f"Your code is: {otp}"
)
```

#### AWS SES (Email)
```python
import boto3

ses_client = boto3.client('ses', region_name='us-east-1')

response = ses_client.send_email(
    Source='noreply@example.com',
    Destination={'ToAddresses': [user_email]},
    Message={
        'Subject': {'Data': 'Password Reset'},
        'Body': {'Html': {'Data': reset_email_html}}
    }
)
```

## セキュリティ考慮事項

### 2FA
- ✅ TOTPシークレットは安全に保存（暗号化推奨）
- ✅ バックアップコードはハッシュ化
- ✅ SMS OTPは5分で期限切れ
- ✅ レート制限の実装を推奨（ブルートフォース対策）

### パスワードリセット
- ✅ トークンはハッシュ化して保存
- ✅ トークンは24時間で期限切れ
- ✅ 使い切りトークン（再利用不可）
- ✅ ユーザー存在の確認を隠蔽（セキュリティのため常に成功を返す）

### セッション管理
- ✅ セッションIDはランダム生成
- ✅ セッション有効期限管理
- ✅ デバイス情報の追跡
- ✅ 疑わしいログインの検出（IPアドレス、位置情報の変化）
- ✅ セッション数の制限

### 追加推奨事項
- レート制限（ログイン試行、OTP送信）
- CAPTCHA統合
- IPアドレスベースのブロック
- 異常なログインパターンの検出と通知
- 監査ログ

## API統合例

FastAPIとの統合例:

```python
from fastapi import FastAPI, Depends, HTTPException, Header
from auth.user_manager import UserManager
from auth.two_factor import TwoFactorManager
from auth.session_manager import SessionManager

app = FastAPI()

@app.post("/auth/2fa/totp/setup")
async def setup_totp(user_id: str = Depends(get_current_user)):
    """TOTP設定開始"""
    user = user_manager.get_user(user_id)
    setup_data = tfa_manager.setup_totp(user_id, user.email)
    return setup_data

@app.post("/auth/2fa/totp/verify-setup")
async def verify_totp_setup(
    code: str,
    user_id: str = Depends(get_current_user)
):
    """TOTP設定完了"""
    success = tfa_manager.verify_totp_setup(user_id, code)
    if not success:
        raise HTTPException(status_code=400, detail="Invalid code")
    return {"status": "enabled"}

@app.post("/auth/password-reset/request")
async def request_reset(email: str):
    """パスワードリセット要求"""
    user_manager.request_password_reset(email)
    return {"message": "If email exists, reset link sent"}

@app.post("/auth/password-reset/confirm")
async def reset_password(token: str, new_password: str):
    """パスワードリセット実行"""
    success = user_manager.reset_password_with_token(token, new_password)
    if not success:
        raise HTTPException(status_code=400, detail="Invalid or expired token")
    return {"status": "success"}

@app.get("/auth/sessions")
async def list_sessions(user_id: str = Depends(get_current_user)):
    """アクティブセッション一覧"""
    sessions = session_manager.list_user_sessions(user_id)
    return {"sessions": sessions}

@app.delete("/auth/sessions/{session_id}")
async def logout_session(
    session_id: str,
    user_id: str = Depends(get_current_user)
):
    """特定セッションからログアウト"""
    session = session_manager.get_session(session_id)
    if not session or session.user_id != user_id:
        raise HTTPException(status_code=404, detail="Session not found")

    session_manager.invalidate_session(session_id, reason="user_logout")
    return {"status": "logged_out"}

@app.post("/auth/sessions/logout-all")
async def logout_all(
    user_id: str = Depends(get_current_user),
    current_session_id: str = Header(None, alias="X-Session-ID")
):
    """全デバイスからログアウト"""
    count = session_manager.invalidate_all_user_sessions(
        user_id,
        except_session_id=current_session_id,
        reason="logout_all_devices"
    )
    return {"logged_out_count": count}
```

## トラブルシューティング

### TOTP コードが一致しない
- デバイスの時刻が正確か確認
- `valid_window` パラメータで許容範囲を調整

### SMS が届かない
- 電話番号がE.164形式か確認（+国番号 + 番号）
- SMSプロバイダーのクレジット残高確認
- レート制限に引っかかっていないか確認

### パスワードリセットトークンが無効
- トークン有効期限（24時間）を確認
- トークンが既に使用済みでないか確認
- URLのトークンが完全にコピーされているか確認

### セッションが期限切れ
- `session_expire_hours` を適切に設定
- アクティビティベースの更新が機能しているか確認
- クライアント側でセッション更新を実装

## まとめ

これらの認証機能により、以下が実現できます:

✅ **強力なセキュリティ**: 2FAとパスワードリセットで不正アクセス防止
✅ **ユーザー体験**: 複数デバイス対応、柔軟なセッション管理
✅ **監視と制御**: アクティブセッション追跡、不審なログイン検出
✅ **スケーラビリティ**: Redis/PostgreSQLで本番環境対応
✅ **柔軟性**: TOTP/SMS の選択、バックアップコード

本番環境への展開時は、適切なデータベース統合とサードパーティサービス（SMS、メール）の設定を行ってください。

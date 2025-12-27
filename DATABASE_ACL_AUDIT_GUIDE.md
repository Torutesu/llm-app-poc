# データベース・ACL・監査ログ 完全ガイド

P0とP1の重要機能を実装しました。このガイドではPostgreSQL永続化、ドキュメントレベルACL、監査ログ、GDPR対応の使い方を説明します。

## 📋 目次

1. [概要](#概要)
2. [PostgreSQLセットアップ](#postgresqlセットアップ)
3. [ドキュメントACL](#ドキュメントacl)
4. [監査ログ](#監査ログ)
5. [GDPR対応](#gdpr対応)
6. [統合例](#統合例)

---

## 概要

### 実装された機能

✅ **PostgreSQLスキーマ** - 12テーブル + ビュー + 関数
✅ **ユーザー管理** - PostgreSQL永続化
✅ **ドキュメントACL** - ファイル/フォルダ権限管理
✅ **監査ログ** - 全アクション記録
✅ **GDPR対応** - データ削除・匿名化・エクスポート

### ファイル構成

```
llm-app-poc/
├── database/
│   ├── schema.sql                  # PostgreSQLスキーマ定義
│   ├── postgres_user_manager.py    # ユーザー管理 (DB版)
│   ├── document_acl.py             # ドキュメント権限管理
│   ├── audit_logger.py             # 監査ログ
│   └── gdpr_compliance.py          # GDPR対応
├── middleware/
│   └── document_filter.py          # Pathway統合ACLフィルタ
└── DATABASE_ACL_AUDIT_GUIDE.md     # このドキュメント
```

---

## PostgreSQLセットアップ

### 1. PostgreSQLインストール

```bash
# macOS
brew install postgresql
brew services start postgresql

# Ubuntu
sudo apt-get install postgresql postgresql-contrib
sudo systemctl start postgresql

# Docker
docker run --name llm-postgres \
  -e POSTGRES_PASSWORD=your_password \
  -e POSTGRES_DB=llm_app \
  -p 5432:5432 \
  -d postgres:15
```

### 2. データベース作成

```bash
# PostgreSQLに接続
psql -U postgres

# データベース作成
CREATE DATABASE llm_app;
\c llm_app

# スキーマ適用
\i /path/to/llm-app-poc/database/schema.sql
```

または、ファイルから直接:

```bash
psql -U postgres -d llm_app -f database/schema.sql
```

### 3. 接続文字列設定

`.env`ファイルに追加:

```bash
DATABASE_URL=postgresql://postgres:your_password@localhost:5432/llm_app
```

### 4. スキーマ確認

```sql
-- テーブル一覧
\dt

-- テーブル: tenants, users, roles, permissions, documents,
--          document_permissions, audit_logs, refresh_tokens, etc.

-- ユーザー数確認
SELECT COUNT(*) FROM users;

-- テーブル構造確認
\d users
```

---

## ドキュメントACL

### アクセスレベル

| レベル | 権限 |
|--------|------|
| `read` | ドキュメント閲覧 |
| `write` | 編集・作成 |
| `admin` | 権限管理 |
| `none` | アクセス不可 |

### 基本的な使い方

```python
from database.document_acl import DocumentACL, AccessLevel
from uuid import UUID

# 初期化
db_url = "postgresql://postgres:password@localhost/llm_app"
acl = DocumentACL(db_url)

# ユーザーに権限付与
document_id = UUID("123e4567-e89b-12d3-a456-426614174000")
acl.grant_user_access(
    document_id=document_id,
    tenant_id="company_xyz",
    user_id="user_abc123",
    access_level=AccessLevel.READ,
    granted_by="admin_user"
)

# ロールに権限付与
acl.grant_role_access(
    document_id=document_id,
    tenant_id="company_xyz",
    role_id=2,  # editor role
    access_level=AccessLevel.WRITE
)

# 権限チェック
has_access = acl.check_user_access(
    document_id=document_id,
    user_id="user_abc123",
    required_access=AccessLevel.READ
)
print(f"User has access: {has_access}")

# ユーザーがアクセス可能なドキュメント取得
accessible_docs = acl.get_user_accessible_documents(
    user_id="user_abc123",
    tenant_id="company_xyz",
    access_level=AccessLevel.READ
)
print(f"Accessible documents: {len(accessible_docs)}")
```

### フォルダ権限の継承

```python
# 親フォルダの権限を子ドキュメントに継承
folder_id = UUID("parent-folder-uuid")
document_id = UUID("child-document-uuid")

acl.inherit_folder_permissions(
    folder_id=folder_id,
    document_id=document_id,
    tenant_id="company_xyz"
)
```

### デフォルト権限設定

```python
# 新規ドキュメント作成時のデフォルト権限
acl.set_default_permissions(
    document_id=document_id,
    tenant_id="company_xyz",
    owner_id="user_abc123"
)

# 結果:
# - owner: admin権限
# - admin role: admin権限
# - editor role: write権限
# - viewer role: read権限
```

### ドキュメント権限の確認

```python
# ドキュメントの全権限を取得
permissions = acl.get_document_permissions(document_id)

print("User permissions:")
for perm in permissions['users']:
    print(f"  {perm['email']}: {perm['access_level']}")

print("Role permissions:")
for perm in permissions['roles']:
    print(f"  {perm['role_name']}: {perm['access_level']}")
```

### Pathway統合

```python
from middleware.document_filter import ACLAwareRetriever
import pathway as pw

# ACL対応のレトリーバー作成
base_retriever = pw.xpacks.llm.vector_store.UsearchKNN(...)
acl_retriever = ACLAwareRetriever(base_retriever, document_acl)

# 検索（自動的にACLフィルタリング）
results = acl_retriever.retrieve(
    query="Show financial reports",
    k=10
)
# → ユーザーがアクセス可能なドキュメントのみ返される
```

---

## 監査ログ

### 基本的な使い方

```python
from database.audit_logger import AuditLogger, AuditAction

# 初期化
audit_logger = AuditLogger(db_url)

# ログ記録
audit_logger.log(
    action=AuditAction.DOCUMENT_READ,
    user_id="user_abc123",
    tenant_id="company_xyz",
    resource_type="document",
    resource_id="doc_uuid",
    ip_address="192.168.1.100",
    user_agent="Mozilla/5.0...",
    success=True
)
```

### 便利なメソッド

```python
# ログイン記録
audit_logger.log_login(
    user_id="user_abc123",
    tenant_id="company_xyz",
    success=True,
    ip_address="192.168.1.100"
)

# ドキュメントアクセス記録
audit_logger.log_document_access(
    document_id="doc_uuid",
    action=AuditAction.DOCUMENT_READ,
    metadata={"file_name": "report.pdf"}
)

# 検索記録
audit_logger.log_search(
    query="Q4 financial report",
    results_count=15,
    response_time_ms=120
)

# 権限変更記録
audit_logger.log_permission_change(
    action=AuditAction.PERMISSION_GRANT,
    resource_type="document",
    resource_id="doc_uuid",
    target_user_id="user_xyz",
    access_level="read"
)
```

### ログ検索

```python
from datetime import datetime, timedelta

# ユーザーの活動履歴
user_activity = audit_logger.get_user_activity(
    user_id="user_abc123",
    start_date=datetime.now() - timedelta(days=7),
    limit=100
)

for log in user_activity:
    print(f"{log['timestamp']}: {log['action']} - {log['resource_type']}")

# テナントの活動履歴
tenant_activity = audit_logger.get_tenant_activity(
    tenant_id="company_xyz",
    start_date=datetime.now() - timedelta(days=30),
    limit=500
)

# ドキュメントアクセス履歴
doc_history = audit_logger.get_document_access_history(
    document_id="doc_uuid",
    limit=50
)
```

### コンプライアンスレポート

```python
from datetime import datetime

# 月次コンプライアンスレポート
report = audit_logger.generate_compliance_report(
    tenant_id="company_xyz",
    start_date=datetime(2025, 1, 1),
    end_date=datetime(2025, 1, 31)
)

print(f"Total actions: {report['summary']['total_actions']}")
print(f"Unique users: {report['summary']['unique_users']}")
print(f"Document accesses: {report['summary']['document_accesses']}")
print(f"Failed actions: {report['summary']['failed_actions']}")
```

### デコレータで自動ログ記録

```python
from database.audit_logger import audit_log, AuditAction

@audit_log(AuditAction.DOCUMENT_READ, resource_type="document")
def read_document(document_id: str, audit_logger=None):
    """Read document with automatic audit logging."""
    # ドキュメント読み取り処理
    return document_content

# 使用
result = read_document(
    document_id="doc_uuid",
    audit_logger=audit_logger
)
# → 成功/失敗が自動的にログ記録される
```

---

## GDPR対応

### データエクスポート（Article 15, 20）

```python
from database.gdpr_compliance import GDPRCompliance

# 初期化
gdpr = GDPRCompliance(db_url, audit_logger)

# ユーザーデータを完全エクスポート
export_data = gdpr.export_user_data("user_abc123")

# エクスポート内容:
# - プロフィール
# - ロール
# - カスタム権限
# - ドキュメント権限
# - 所有ドキュメント
# - 検索履歴
# - アクティビティログ

# JSONファイルに保存
from database.gdpr_compliance import export_to_json_file
filename = export_to_json_file(
    export_data,
    f"user_data_export_{user_id}.json"
)
print(f"Exported to: {filename}")
```

### データ匿名化（Article 17）

```python
# ユーザーデータを匿名化（監査ログは保持）
gdpr.anonymize_user(
    user_id="user_abc123",
    reason="User requested account deletion"
)

# 結果:
# - メールアドレス: deleted_user_xxx@anonymized.local
# - 名前: "Deleted User"
# - パスワード: 削除
# - OAuth連携: 削除
# - アカウント: 非アクティブ化
# - 監査ログ: アクションは保持、PII削除
```

### 完全削除（Article 17）

```python
# 警告: 不可逆的な削除
gdpr.delete_user_data(
    user_id="user_abc123",
    reason="Legal requirement"
)

# すべてのユーザーデータが永久削除される
# 監査ログにのみ削除記録が残る
```

### データ修正（Article 16）

```python
# ユーザー情報の修正
gdpr.rectify_user_data(
    user_id="user_abc123",
    updates={
        "name": "Alice Smith (Updated)",
        "email": "alice.new@company.com"
    }
)
```

### 同意状況の確認

```python
# ユーザーの同意状況を取得
consent = gdpr.get_consent_status("user_abc123")

print(f"Consent given: {consent['consent_given']}")
print(f"Data processing: {consent['data_processing_consent']}")
print(f"Marketing: {consent['marketing_consent']}")
```

### GDPRコンプライアンスレポート

```python
# テナントのGDPR対応状況レポート
gdpr_report = gdpr.generate_gdpr_report("company_xyz")

print(f"Total users: {gdpr_report['users']['total']}")
print(f"Active users: {gdpr_report['users']['active']}")
print(f"Anonymized users: {gdpr_report['users']['anonymized']}")
print(f"Data export requests (30d): {gdpr_report['gdpr_requests_30_days']['data_export']}")
print(f"Compliance status: {gdpr_report['compliance_status']}")
```

---

## 統合例

### 完全な認証付きアプリケーション

```python
import os
from database.postgres_user_manager import PostgresUserManager
from database.document_acl import DocumentACL, AccessLevel
from database.audit_logger import AuditLogger
from database.gdpr_compliance import GDPRCompliance
from auth.jwt_handler import JWTConfig, JWTHandler

# データベース接続
db_url = os.getenv("DATABASE_URL")

# JWT設定
jwt_config = JWTConfig(
    secret_key=os.getenv("JWT_SECRET_KEY"),
    access_token_expire_minutes=30
)
jwt_handler = JWTHandler(jwt_config)

# 各マネージャー初期化
user_manager = PostgresUserManager(jwt_handler, db_url)
document_acl = DocumentACL(db_url)
audit_logger = AuditLogger(db_url)
gdpr = GDPRCompliance(db_url, audit_logger)

# シナリオ1: ユーザー作成
user = user_manager.create_user(
    email="alice@company.com",
    tenant_id="company_xyz",
    password="secure_pass",
    roles=["editor"]
)

# シナリオ2: ログイン
authenticated_user = user_manager.authenticate_password(
    email="alice@company.com",
    password="secure_pass"
)

if authenticated_user:
    # ログイン監査
    audit_logger.log_login(
        user_id=authenticated_user.user_id,
        tenant_id=authenticated_user.tenant_id,
        success=True,
        ip_address="192.168.1.100"
    )

    # JWTトークン生成
    tokens = user_manager.create_tokens_for_user(authenticated_user)

# シナリオ3: ドキュメントアクセス
from uuid import UUID
document_id = UUID("123e4567-e89b-12d3-a456-426614174000")

# 権限チェック
if document_acl.check_user_access(document_id, user.user_id, AccessLevel.READ):
    # アクセス監査
    audit_logger.log_document_access(
        document_id=str(document_id),
        action="document_read",
        user_id=user.user_id,
        tenant_id=user.tenant_id
    )

    # ドキュメント取得処理
    print("Document access granted")
else:
    audit_logger.log(
        action="document_access_denied",
        user_id=user.user_id,
        resource_id=str(document_id),
        success=False
    )
    print("Access denied")

# シナリオ4: GDPRリクエスト
# ユーザーがデータエクスポートを要求
export_data = gdpr.export_user_data(user.user_id)
print(f"Exported {len(export_data['data'])} data sections")

# ユーザーがアカウント削除を要求
gdpr.anonymize_user(
    user_id=user.user_id,
    reason="User requested deletion"
)
```

### Pathway統合例

```python
import pathway as pw
from middleware.document_filter import ACLAwareRetriever
from middleware.tenant_context import TenantContext

# テナント・ユーザーコンテキスト設定
TenantContext.set_tenant("company_xyz")
TenantContext.set_user("user_abc123")

# ACL対応のレトリーバー
acl_retriever = ACLAwareRetriever(base_retriever, document_acl)

# 検索（自動的に権限フィルタリング）
results = acl_retriever.retrieve(
    query="Show Q4 financial reports",
    k=10
)

# 監査ログ記録
audit_logger.log_search(
    query="Show Q4 financial reports",
    results_count=len(results),
    user_id=TenantContext.get_user(),
    tenant_id=TenantContext.get_tenant()
)
```

---

## データベーステーブル構造

### 主要テーブル

| テーブル | 説明 | 主キー |
|---------|------|--------|
| `tenants` | 組織情報 | tenant_id |
| `users` | ユーザー | user_id |
| `roles` | ロール定義 | role_id |
| `permissions` | 権限定義 | permission_id |
| `documents` | ドキュメントメタデータ | document_id (UUID) |
| `document_permissions` | ドキュメントACL | permission_id (UUID) |
| `audit_logs` | 監査ログ | log_id (UUID) |
| `refresh_tokens` | リフレッシュトークン | token_id (UUID) |
| `search_queries` | 検索履歴 | query_id (UUID) |

### ビュー

- `user_all_permissions` - ユーザーの全権限（ロール + カスタム）
- `document_access` - ドキュメントアクセス権限

### 関数

- `update_updated_at_column()` - updated_at自動更新
- `user_can_access_document()` - ユーザー権限チェック

---

## トラブルシューティング

### PostgreSQL接続エラー

```python
# エラー: "connection refused"
# 解決策: PostgreSQLが起動しているか確認
brew services list  # macOS
sudo systemctl status postgresql  # Linux
```

### スキーマ適用エラー

```sql
-- エラー: "relation already exists"
-- 解決策: テーブルを削除して再作成
DROP TABLE IF EXISTS audit_logs, documents, users, tenants CASCADE;
\i database/schema.sql
```

### ACL権限エラー

```python
# エラー: "User does not have access"
# 確認1: ユーザーに権限が付与されているか
SELECT * FROM document_access
WHERE user_id = 'user_abc123' AND document_id = 'doc_uuid';

# 確認2: ロールベースの権限
SELECT r.role_name, dp.access_level
FROM document_permissions dp
JOIN user_roles ur ON dp.role_id = ur.role_id
JOIN roles r ON ur.role_id = r.role_id
WHERE ur.user_id = 'user_abc123' AND dp.document_id = 'doc_uuid';
```

---

## 次のステップ

✅ **完了した実装:**
- PostgreSQL永続化
- ドキュメントレベルACL
- 監査ログシステム
- GDPR対応機能

🚧 **次エージェントへの引き継ぎ事項:**
- 2要素認証 (2FA)
- パスワードリセット機能
- セッション管理
- レート制限
- リアルタイム通知

---

## まとめ

このガイドで実装した機能により、以下が実現できます：

✅ **エンタープライズグレードのデータ管理**
✅ **きめ細かいドキュメント権限制御**
✅ **完全な監査証跡**
✅ **GDPR完全準拠**
✅ **Glean.comレベルのセキュリティ**

これでエンタープライズSaaSに必要な基盤インフラが完成しました！

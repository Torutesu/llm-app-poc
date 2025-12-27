# Hybrid Multi-Tenant / Single-Tenant Deployment Guide

このガイドでは、**Glean.com**のようなエンタープライズSaaSを実現するためのハイブリッドアーキテクチャの実装方法を説明します。

## 📋 目次

1. [アーキテクチャ概要](#アーキテクチャ概要)
2. [デプロイメントモード](#デプロイメントモード)
3. [実装されたコンポーネント](#実装されたコンポーネント)
4. [使い方](#使い方)
5. [ユースケース別設定](#ユースケース別設定)
6. [移行シナリオ](#移行シナリオ)

---

## アーキテクチャ概要

```
┌─────────────────────────────────────────────────────┐
│         コントロールプレーン                          │
│  - テナント管理 (TenantManager)                     │
│  - ルーティングテーブル                              │
│  - 課金・プロビジョニング                            │
└──────────────┬──────────────────────────────────────┘
               │
       ┌───────┴────────┐
       │                │
┌──────▼─────────┐  ┌──▼─────────────────────┐
│ マルチテナント  │  │ シングルテナント         │
│ (共有環境)      │  │ (専用環境)              │
├────────────────┤  ├────────────────────────┤
│ テナントA      │  │ 大企業X専用インスタンス │
│ テナントB      │  │ - 専用VPC              │
│ テナントC      │  │ - データ完全分離        │
│ ...            │  │ - カスタム機能          │
└────────────────┘  └────────────────────────┘
```

### 特徴

- **マルチテナント**: 複数組織を1つのインスタンスで運用（コスト効率◎）
- **シングルテナント**: 大企業向け専用インスタンス（セキュリティ◎）
- **柔軟なアップグレード**: StandardからDedicatedへの移行が可能

---

## デプロイメントモード

### 1. マルチテナント（共有環境）

**適用対象:**
- Free / Standard / Enterpriseティア
- 中小規模の顧客
- コスト重視の顧客

**特徴:**
- 論理的データ分離（`tenant_id`によるフィルタリング）
- 共有インフラで運用コスト削減
- 標準機能のみ

**設定ファイル:** [`config/deployment-multi-tenant.yaml`](config/deployment-multi-tenant.yaml)

### 2. シングルテナント（専用環境）

**適用対象:**
- Dedicatedティア
- 大企業顧客
- 高セキュリティ要件

**特徴:**
- 物理的データ分離（専用インスタンス）
- カスタム機能・モデル対応
- SSO統合、VPC Peering対応

**設定ファイル:** [`config/deployment-single-tenant.yaml`](config/deployment-single-tenant.yaml)

---

## 実装されたコンポーネント

### 📂 ファイル構成

```
llm-app-poc/
├── config/
│   ├── deployment.py                    # デプロイメント設定クラス
│   ├── deployment-multi-tenant.yaml     # マルチテナント設定
│   └── deployment-single-tenant.yaml    # シングルテナント設定
├── middleware/
│   ├── tenant_context.py               # テナントコンテキスト管理
│   └── tenant_data_filter.py           # テナント別データフィルタ
├── control_plane/
│   └── tenant_manager.py               # テナント管理サービス
└── examples/
    └── hybrid_deployment_example.py    # 使用例
```

### 🔧 主要クラス

#### 1. **DeploymentConfig** ([`config/deployment.py`](config/deployment.py))

デプロイメントモードと分離レベルを定義。

```python
from config.deployment import DeploymentConfig, DeploymentMode

# マルチテナント設定
config = DeploymentConfig(
    mode=DeploymentMode.MULTI_TENANT,
    require_tenant_in_request=True,
    enforce_tenant_isolation=True
)

# シングルテナント設定
config = DeploymentConfig(
    mode=DeploymentMode.SINGLE_TENANT,
    tenant_id="acme_corp",
    tenant_name="Acme Corporation"
)
```

#### 2. **TenantMiddleware** ([`middleware/tenant_context.py`](middleware/tenant_context.py))

リクエストからテナントを識別し、コンテキストに設定。

```python
from middleware.tenant_context import TenantMiddleware, TenantContext

middleware = TenantMiddleware(config)

# リクエスト処理
request_data = {
    "headers": {"X-Tenant-ID": "startup_alpha"},
    "body": {"query": "Find documents"}
}
enriched_request = middleware.process_request(request_data)

# テナントコンテキストを取得
tenant_id = TenantContext.get_tenant()  # "startup_alpha"
```

#### 3. **TenantDataFilter** ([`middleware/tenant_data_filter.py`](middleware/tenant_data_filter.py))

Pathwayパイプラインでテナント別にデータをフィルタ。

```python
from middleware.tenant_data_filter import TenantDataFilter
import pathway as pw

# テナント専用データソースを作成
source = TenantDataFilter.create_tenant_aware_source(
    pw.io.fs.read,
    tenant_id="acme_corp",
    path="./data/tenants/{tenant_id}",  # {tenant_id}が自動置換
    format="binary"
)

# テナントメタデータを追加
table_with_tenant = TenantDataFilter.add_tenant_metadata(table, tenant_id)

# テナントでフィルタ
filtered_table = TenantDataFilter.filter_by_tenant(table, tenant_id)
```

#### 4. **TenantManager** ([`control_plane/tenant_manager.py`](control_plane/tenant_manager.py))

テナントの登録・管理・アップグレードを担当。

```python
from control_plane.tenant_manager import get_tenant_manager, TenantTier

manager = get_tenant_manager()

# テナント登録
tenant = manager.register_tenant(
    "Startup Inc.",
    tier=TenantTier.STANDARD
)

# ルーティング情報取得
routing = manager.get_routing_info(tenant.tenant_id)
print(f"Instance URL: {routing.instance_url}")

# アップグレード（自動的にシングルテナントに移行）
manager.upgrade_tenant_tier(tenant.tenant_id, TenantTier.DEDICATED)
```

---

## 使い方

### ステップ1: デプロイメント設定を選択

環境変数または設定ファイルでモードを指定。

**マルチテナント:**
```bash
export DEPLOYMENT_MODE=multi_tenant
```

**シングルテナント:**
```bash
export DEPLOYMENT_MODE=single_tenant
export TENANT_ID=acme_corp
export TENANT_NAME="Acme Corporation"
```

### ステップ2: アプリケーション起動

既存の`app.py`を拡張してテナント対応にします。

```python
import os
import pathway as pw
from config.deployment import DeploymentConfig, DeploymentMode
from middleware.tenant_context import TenantMiddleware, create_tenant_aware_handler
from middleware.tenant_data_filter import TenantDataFilter

# デプロイメント設定を読み込み
deployment_mode = os.getenv("DEPLOYMENT_MODE", "multi_tenant")

if deployment_mode == "single_tenant":
    config = DeploymentConfig(
        mode=DeploymentMode.SINGLE_TENANT,
        tenant_id=os.getenv("TENANT_ID"),
        tenant_name=os.getenv("TENANT_NAME")
    )
else:
    config = DeploymentConfig(
        mode=DeploymentMode.MULTI_TENANT,
        require_tenant_in_request=True,
        enforce_tenant_isolation=True
    )

# テナント対応データソース
if config.is_multi_tenant():
    # マルチテナント: テナントごとのフォルダから読み込み
    sources = TenantDataFilter.create_tenant_aware_source(
        pw.io.fs.read,
        path="./data/tenants/{tenant_id}",
        format="binary"
    )
else:
    # シングルテナント: 全データが対象
    sources = pw.io.fs.read("./data", format="binary")

# 残りのパイプライン処理...
# (既存のapp.pyのロジックを使用)

# REST APIハンドラにミドルウェアを適用
middleware = TenantMiddleware(config)
handler_decorator = create_tenant_aware_handler(config)

# アプリケーション実行
pw.run()
```

### ステップ3: APIリクエスト

**マルチテナント環境:**
```bash
curl -X POST https://api.yoursaas.com/v2/answer \
  -H "X-Tenant-ID: startup_alpha" \
  -H "Authorization: Bearer <JWT>" \
  -d '{"query": "What is our Q4 revenue?"}'
```

**シングルテナント環境:**
```bash
# テナントIDは不要（設定で固定されている）
curl -X POST https://acme.dedicated.yoursaas.com/v2/answer \
  -H "Authorization: Bearer <JWT>" \
  -d '{"query": "What is our Q4 revenue?"}'
```

---

## ユースケース別設定

### 🌱 スタートアップ向け（Standard Tier）

- **デプロイ:** マルチテナント
- **データ:** 論理分離
- **コスト:** 低（共有インフラ）
- **機能:** 標準機能のみ

```yaml
mode: multi_tenant
tier: standard
api_rate_limit: 100
max_documents: 10000
```

### 🏢 中規模企業向け（Enterprise Tier）

- **デプロイ:** マルチテナント
- **データ:** 論理分離 + 高度なセキュリティ
- **コスト:** 中
- **機能:** SSO、高優先度サポート

```yaml
mode: multi_tenant
tier: enterprise
sso_enabled: true
api_rate_limit: 500
advanced_security: true
```

### 🏛️ 大企業向け（Dedicated Tier）

- **デプロイ:** シングルテナント
- **データ:** 物理分離
- **コスト:** 高
- **機能:** カスタムモデル、VPC、専任サポート

```yaml
mode: single_tenant
tier: dedicated
tenant_id: megacorp
custom_model_allowed: true
vpc_peering: true
api_rate_limit: 1000
```

---

## 移行シナリオ

### シナリオ1: Standard → Dedicated

**ステップ:**
1. 顧客がDedicatedティアにアップグレード申し込み
2. システムが専用インスタンスをプロビジョニング
3. マルチテナント環境からデータを移行
4. DNSを専用インスタンスにルーティング
5. マルチテナント環境のデータを削除

**コード:**
```python
from control_plane.tenant_manager import get_tenant_manager, TenantTier

manager = get_tenant_manager()
manager.upgrade_tenant_tier("startup_alpha_12345", TenantTier.DEDICATED)
```

**結果:**
- 新URL: `https://startup_alpha.dedicated.yoursaas.com`
- カスタム機能が有効化
- 専用リソース割り当て

### シナリオ2: 新規Dedicated顧客

大企業が最初からDedicatedで契約する場合。

```python
tenant = manager.register_tenant(
    "MegaCorp Inc.",
    tier=TenantTier.DEDICATED  # 最初からシングルテナント
)
# 自動的に専用インスタンスがプロビジョニングされる
```

---

## 次のステップ

実装済みの基盤に加えて、以下を追加すると本格的なGlean型システムになります：

### 🔐 認証・認可（P0）
- JWT/OAuth2.0実装
- RBAC（Role-Based Access Control）
- ドキュメントレベル権限管理

### 📊 監査ログ（P1）
- すべてのアクセスを記録
- コンプライアンス対応（GDPR, CCPA）

### 🎯 パーソナライズ（P2）
- ユーザー検索履歴
- ドキュメント推薦
- 行動分析

### 📈 アナリティクス（P2）
- テナントごとの使用状況
- 検索トレンド分析
- コスト最適化インサイト

---

## サンプル実行

デモを実行して動作確認：

```bash
cd llm-app-poc
python examples/hybrid_deployment_example.py
```

**出力例:**
```
=== Multi-Tenant Setup ===
Registered tenants:
  - startup_alpha_a1b2c3d4: Startup Alpha (standard)
  - company_beta_e5f6g7h8: Company Beta (enterprise)

=== Single-Tenant (Dedicated) Setup ===
Dedicated instance for tenant: megacorp_12345678
Organization: MegaCorp Inc.

=== Hybrid: Tenant Upgrade Demo ===
Initial setup:
  Tier: standard
  Deployment: multi_tenant
  Instance: https://api.yoursaas.com

After upgrade:
  Tier: dedicated
  Deployment: single_tenant
  Dedicated URL: https://growing_company_xyz.dedicated.yoursaas.com
```

---

## まとめ

このハイブリッドアーキテクチャにより、以下が実現できます：

✅ **柔軟なビジネスモデル**: Standard（共有）→ Dedicated（専用）の段階的提供
✅ **コスト最適化**: 小規模顧客は共有、大企業は専用で効率化
✅ **セキュリティ**: テナント分離を論理/物理両方でサポート
✅ **スケーラビリティ**: 1インスタンスで数百〜数千テナントに対応可能
✅ **Glean型エンタープライズ**: 権限管理・パーソナライズの基盤完成

次は認証・認可システムの実装に進むことをお勧めします！

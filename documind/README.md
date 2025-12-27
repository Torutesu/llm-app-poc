# DocuMind - Enterprise AI Document Intelligence Platform

<div align="center">

![DocuMind Logo](https://via.placeholder.com/200x60?text=DocuMind)

**次世代の企業向けドキュメント検索・ナレッジマネジメントプラットフォーム**

[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Pathway](https://img.shields.io/badge/Powered%20by-Pathway-blue)](https://pathway.com)
[![Next.js](https://img.shields.io/badge/Frontend-Next.js-black)](https://nextjs.org)

</div>

## 📋 目次

- [概要](#概要)
- [主な機能](#主な機能)
- [技術スタック](#技術スタック)
- [クイックスタート](#クイックスタート)
- [アーキテクチャ](#アーキテクチャ)
- [設定](#設定)
- [デプロイ](#デプロイ)
- [ロードマップ](#ロードマップ)

## 🎯 概要

**DocuMind**は、企業のドキュメント管理を革新するAI駆動型のプラットフォームです。

Pathwayフレームワークをベースに、リアルタイムでドキュメントを同期・解析し、自然言語で質問できる次世代のナレッジマネジメントシステムを提供します。

### なぜDocuMindなのか？

✅ **リアルタイム同期** - Google Drive、SharePoint等から自動同期、ETLパイプライン不要
✅ **マルチモーダルAI** - テキスト、画像、テーブル、スライドを統合処理
✅ **エンタープライズ対応** - 権限管理、監査ログ、SOC2準拠のセキュリティ
✅ **カスタマイズ可能** - LLMモデル、embedder、プロンプトをUI上で変更可能
✅ **本番環境対応** - 数百万ページのドキュメントをスケール処理

## ✨ 主な機能

### 🔍 高度なドキュメント検索

- **自然言語検索** - 質問を入力するだけで関連ドキュメントから回答を生成
- **ベクトル検索** - 意味的類似性に基づく高精度な検索
- **ハイブリッド検索** - ベクトル検索とキーワード検索を組み合わせ
- **フィルタリング** - メタデータによる柔軟な検索条件

### 📄 マルチモーダル処理

- **PDF・Office文書** - PDF、DOCX、PPTX、Excelに対応
- **画像解析** - 図表、グラフ、チャートの内容を理解
- **テーブル抽出** - 財務データ、統計情報などを正確に抽出
- **スライド検索** - プレゼン資料から特定のスライドを即座に検索

### 🔄 リアルタイム同期

- **Google Drive** - Googleドライブの変更を自動検知・同期
- **Microsoft SharePoint** - SharePoint Onlineと連携
- **ローカルフォルダ** - ファイルシステムの変更を監視
- **S3/Azure Blob** - クラウドストレージとの統合

### 🎛️ 管理機能

- **ユーザー管理** - 組織、チーム、個人のアクセス制御
- **ダッシュボード** - ドキュメント統計、使用状況の可視化
- **設定管理** - LLMモデル、embedder、パラメータの動的変更
- **監査ログ** - すべての操作を記録・追跡

## 🛠️ 技術スタック

### フロントエンド

- **Framework**: Next.js 14 (App Router)
- **Language**: TypeScript
- **Styling**: Tailwind CSS
- **UI Components**: Radix UI + shadcn/ui
- **State Management**: Zustand
- **HTTP Client**: Axios

### バックエンド

- **RAG Engine**: Pathway (v0.12.0+)
- **API Framework**: FastAPI
- **Language**: Python 3.10+
- **LLM**: OpenAI GPT-4, Mistral, Ollama
- **Embeddings**: OpenAI text-embedding-3-small
- **Vector Store**: USearch (in-memory)
- **Full-Text Search**: Tantivy

### インフラ

- **Container**: Docker + Docker Compose
- **Database**: PostgreSQL 16
- **Cache**: Redis 7
- **Reverse Proxy**: Nginx (optional)
- **Deployment**: AWS, GCP, Azure, Render

## 🚀 クイックスタート

### 前提条件

- Docker & Docker Compose
- OpenAI API キー
- 8GB以上のRAM

### インストール

1. **リポジトリをクローン**

```bash
git clone https://github.com/your-org/documind.git
cd documind
```

2. **環境変数を設定**

```bash
cp .env.example .env
# .envファイルを編集してOpenAI APIキーを設定
nano .env
```

必須の環境変数:
```env
OPENAI_API_KEY=your_openai_api_key_here
JWT_SECRET=your_super_secret_jwt_key
```

3. **データフォルダを作成**

```bash
mkdir -p data
# テスト用のPDFやドキュメントをdataフォルダに配置
```

4. **Docker Composeで起動**

```bash
docker-compose up -d
```

5. **アクセス**

- **フロントエンド**: http://localhost:3000
- **バックエンドAPI**: http://localhost:8000
- **API Docs**: http://localhost:8000/docs
- **pgAdmin**: http://localhost:5050 (optional)

### 初回ログイン

デモ用の認証情報:
- Email: `admin@example.com`
- Password: `demo`

## 📐 アーキテクチャ

```
┌─────────────────────────────────────────────────────────┐
│                     フロントエンド                        │
│              Next.js + TypeScript + Tailwind            │
│                    (Port: 3000)                         │
└─────────────────────┬───────────────────────────────────┘
                      │ HTTP/REST API
┌─────────────────────┴───────────────────────────────────┐
│                  バックエンド API                         │
│              FastAPI + Pathway Integration              │
│                    (Port: 8000)                         │
└─────────┬──────────────────────┬────────────────────────┘
          │                      │
┌─────────┴──────────┐  ┌────────┴──────────┐
│  Pathway RAG Core  │  │   PostgreSQL DB   │
│  (Port: 8080)      │  │   (Port: 5432)    │
│                    │  │                   │
│  - Document Store  │  │  - Users          │
│  - Embeddings      │  │  - Organizations  │
│  - Vector Search   │  │  - Audit Logs     │
│  - LLM Integration │  │                   │
└────────────────────┘  └───────────────────┘
          │
┌─────────┴──────────┐
│   Data Sources     │
│                    │
│  - Local Files     │
│  - Google Drive    │
│  - SharePoint      │
│  - S3 / Azure      │
└────────────────────┘
```

### データフロー

1. **ドキュメントの取り込み**
   - データソースから自動同期
   - ファイルのアップロード
   - メタデータの抽出

2. **解析・インデックス**
   - Doclingでドキュメントをパース
   - チャンク分割 (TokenCountSplitter)
   - エンベッディング生成 (OpenAI)
   - ベクトルストアに保存 (USearch)

3. **検索・回答生成**
   - ユーザーの質問をエンベッディング
   - ベクトル検索で関連ドキュメントを取得
   - LLMで回答を生成
   - コンテキストとともに返却

## ⚙️ 設定

### バックエンド設定 (`backend/app.yaml`)

```yaml
# LLMモデルの変更
$llm: !pw.xpacks.llm.llms.OpenAIChat
  model: "gpt-4o-mini"  # gpt-4o, gpt-4-turbo など
  temperature: 0
  max_tokens: 2000

# Embeddingモデルの変更
$embedder: !pw.xpacks.llm.embedders.OpenAIEmbedder
  model: "text-embedding-3-small"  # text-embedding-3-large など

# 検索結果の数
question_answerer:
  search_topk: 6  # 増やすとより多くのコンテキストを参照
```

### データソースの追加

Google Driveを追加する場合:

```yaml
$sources:
  - !pw.io.gdrive.read
    object_id: $DRIVE_ID
    service_user_credentials_file: gdrive_credentials.json
    with_metadata: true
    refresh_interval: 30
```

SharePointを追加する場合:

```yaml
$sources:
  - !pw.xpacks.connectors.sharepoint.read
    url: $SHAREPOINT_URL
    tenant: $SHAREPOINT_TENANT
    client_id: $SHAREPOINT_CLIENT_ID
    cert_path: sharepoint_cert.pem
    thumbprint: $SHAREPOINT_THUMBPRINT
```

## 🌐 デプロイ

### AWS ECS / Fargate

```bash
# ECRにイメージをプッシュ
aws ecr get-login-password --region ap-northeast-1 | docker login --username AWS --password-stdin <account-id>.dkr.ecr.ap-northeast-1.amazonaws.com
docker build -t documind-backend ./backend
docker tag documind-backend:latest <account-id>.dkr.ecr.ap-northeast-1.amazonaws.com/documind-backend:latest
docker push <account-id>.dkr.ecr.ap-northeast-1.amazonaws.com/documind-backend:latest

# ECS タスク定義とサービスを作成
```

### Google Cloud Run

```bash
# Cloud Buildでビルド
gcloud builds submit --tag gcr.io/PROJECT_ID/documind-backend ./backend

# Cloud Runにデプロイ
gcloud run deploy documind-backend \
  --image gcr.io/PROJECT_ID/documind-backend \
  --platform managed \
  --region asia-northeast1 \
  --allow-unauthenticated
```

### Kubernetes (Helm)

```bash
# Helm chartを使用
helm install documind ./helm/documind \
  --set image.tag=latest \
  --set env.OPENAI_API_KEY=$OPENAI_API_KEY
```

## 🗺️ ロードマップ

### v0.2.0 (次のリリース)
- [ ] 本格的な認証・認可システム (Auth0/Clerk統合)
- [ ] ユーザー・組織管理画面
- [ ] ドキュメントアップロードUI
- [ ] リアルタイムドキュメント同期ステータス

### v0.3.0
- [ ] マルチテナント対応
- [ ] 詳細な権限管理 (RBAC)
- [ ] 監査ログUI
- [ ] 使用量制限・課金機能

### v0.4.0
- [ ] Slack/Teams統合
- [ ] Webhooks & イベント通知
- [ ] カスタムプロンプトテンプレート
- [ ] A/Bテスト機能

### v1.0.0
- [ ] エンタープライズSLA
- [ ] SOC2準拠
- [ ] オンプレミス版
- [ ] カスタムモデルサポート

## 📝 ライセンス

MIT License - 詳細は [LICENSE](LICENSE) を参照

## 🤝 コントリビューション

プルリクエストを歓迎します！大きな変更の場合は、まずissueを開いて変更内容を議論してください。

## 📧 サポート

- **ドキュメント**: [docs.documind.ai](https://docs.documind.ai)
- **Discord**: [Join our community](https://discord.gg/documind)
- **Email**: support@documind.ai

---

<div align="center">

**Built with ❤️ using [Pathway](https://pathway.com)**

[Website](https://documind.ai) • [Docs](https://docs.documind.ai) • [Twitter](https://twitter.com/documind)

</div>

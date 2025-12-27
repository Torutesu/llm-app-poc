# DocuMind プロジェクト構造

## 📁 ディレクトリ構成

```
documind/
├── frontend/                    # Next.js フロントエンドアプリケーション
│   ├── app/                    # Next.js App Router
│   │   ├── page.tsx           # ランディングページ
│   │   ├── layout.tsx         # ルートレイアウト
│   │   ├── globals.css        # グローバルスタイル
│   │   ├── dashboard/         # ダッシュボードページ群
│   │   │   ├── page.tsx      # ダッシュボードホーム
│   │   │   ├── layout.tsx    # ダッシュボードレイアウト
│   │   │   ├── chat/         # AIチャットページ
│   │   │   ├── documents/    # ドキュメント管理 (予定)
│   │   │   └── settings/     # 設定ページ (予定)
│   │   └── auth/             # 認証ページ (予定)
│   ├── components/            # 再利用可能なReactコンポーネント
│   ├── lib/                   # ユーティリティ・API クライアント
│   │   └── api.ts            # バックエンドAPIクライアント
│   ├── types/                 # TypeScript型定義
│   │   └── index.ts          # 共通型定義
│   ├── package.json           # Node.js依存関係
│   ├── tsconfig.json          # TypeScript設定
│   ├── tailwind.config.ts     # Tailwind CSS設定
│   ├── next.config.js         # Next.js設定
│   └── Dockerfile             # Dockerイメージビルド定義
│
├── backend/                    # FastAPI + Pathway バックエンド
│   ├── app.py                 # メインアプリケーション
│   ├── app.yaml               # Pathway RAG設定
│   ├── requirements.txt       # Python依存関係
│   ├── .env.example           # 環境変数テンプレート
│   └── Dockerfile             # Dockerイメージビルド定義
│
├── data/                       # ドキュメント保存ディレクトリ (runtime)
│   └── (PDFs, DOCX, etc.)     # ユーザーがアップロードしたファイル
│
├── docker-compose.yml          # Docker Compose設定
├── .env.example                # 環境変数テンプレート
├── .gitignore                  # Git無視ファイル
├── README.md                   # プロジェクトREADME
├── GETTING_STARTED.md          # クイックスタートガイド
└── PROJECT_STRUCTURE.md        # このファイル
```

## 🎯 主要コンポーネント

### フロントエンド

#### ページコンポーネント

| ファイル | 説明 |
|---------|------|
| `app/page.tsx` | ランディングページ (公開) |
| `app/dashboard/page.tsx` | ダッシュボードホーム |
| `app/dashboard/chat/page.tsx` | AIチャット UI |

#### 共通コンポーネント

| ディレクトリ/ファイル | 説明 |
|-------------------|------|
| `lib/api.ts` | バックエンドAPI通信ロジック |
| `types/index.ts` | TypeScript型定義 |

### バックエンド

| ファイル | 説明 |
|---------|------|
| `app.py` | FastAPIサーバー + Pathway統合 |
| `app.yaml` | Pathway RAG設定 (LLM、embedder、データソース) |

## 🔌 API エンドポイント

### 認証 (Mock)

- `POST /v1/auth/login` - ログイン
- `POST /v1/auth/register` - ユーザー登録

### ドキュメント管理

- `GET /v2/list_documents` - ドキュメント一覧取得
- `POST /v1/documents/upload` - ドキュメントアップロード
- `DELETE /v1/documents/:id` - ドキュメント削除
- `POST /v1/retrieve` - ドキュメント検索

### RAG & チャット

- `POST /v2/answer` - 質問に対する回答生成
- `POST /v2/summarize` - テキスト要約

### 設定管理

- `GET /v1/config/rag` - RAG設定取得
- `PUT /v1/config/rag` - RAG設定更新

### データソース

- `GET /v1/datasources` - データソース一覧
- `POST /v1/datasources` - データソース追加
- `POST /v1/datasources/:id/sync` - 同期トリガー

### システム

- `GET /health` - ヘルスチェック
- `GET /v1/stats` - 統計情報

## 🗄️ データフロー

```
┌─────────────┐
│   Browser   │
│  (Next.js)  │
└──────┬──────┘
       │ HTTP
       ↓
┌──────────────┐
│  FastAPI     │ ← ユーザー認証、ビジネスロジック
│  (Port 8000) │
└──────┬───────┘
       │
       ↓
┌──────────────┐
│   Pathway    │ ← RAGエンジン、ドキュメント処理
│  (Port 8080) │
└──────┬───────┘
       │
       ↓
┌──────────────┐
│  Data Store  │ ← ベクトルDB、ドキュメントストレージ
│  (In-memory) │
└──────────────┘
```

## 🛠️ 技術スタック詳細

### フロントエンド
- **Framework**: Next.js 14 (App Router)
- **Language**: TypeScript 5
- **Styling**: Tailwind CSS 3
- **UI Library**: Radix UI (Headless components)
- **Icons**: Lucide React
- **HTTP Client**: Axios
- **State**: Zustand (予定)

### バックエンド
- **RAG Engine**: Pathway 0.12.0+
- **API**: FastAPI
- **Language**: Python 3.10+
- **Parser**: Docling
- **Embeddings**: OpenAI API
- **Vector Search**: USearch
- **Full-Text**: Tantivy

### インフラ
- **Container**: Docker
- **Orchestration**: Docker Compose
- **Database**: PostgreSQL 16
- **Cache**: Redis 7

## 📦 依存関係

### フロントエンド (package.json)

```json
{
  "dependencies": {
    "next": "14.2.3",
    "react": "18.3.1",
    "@radix-ui/react-*": "^1.0+",
    "tailwindcss": "^3.4.3",
    "axios": "^1.7.2",
    "zustand": "^4.5.2"
  }
}
```

### バックエンド (requirements.txt)

```
pathway>=0.12.0
fastapi>=0.104.0
uvicorn[standard]>=0.24.0
pydantic>=2.0.0
sqlalchemy>=2.0.0
```

## 🚀 起動フロー

1. **docker-compose up**
   - PostgreSQL起動
   - Redis起動
   - Backend起動 (Pathway + FastAPI)
   - Frontend起動 (Next.js)

2. **Backend初期化**
   - `app.yaml`を読み込み
   - Pathwayパイプライン構築
   - データソース接続
   - ドキュメントインデックス開始

3. **Frontend起動**
   - Next.jsサーバー起動
   - バックエンドAPIに接続
   - ユーザーアクセス待機

## 🔧 カスタマイズポイント

### LLMモデル変更

`backend/app.yaml`:
```yaml
$llm: !pw.xpacks.llm.llms.OpenAIChat
  model: "gpt-4o-mini"  # ← ここを変更
```

### データソース追加

`backend/app.yaml`:
```yaml
$sources:
  - !pw.io.gdrive.read  # Google Drive
  - !pw.io.fs.read      # ローカル
```

### UIテーマ変更

`frontend/app/globals.css`:
```css
:root {
  --primary: 221.2 83.2% 53.3%;  # プライマリカラー
}
```

## 📚 今後の拡張予定

1. **認証システム**
   - JWT実装
   - Auth0/Clerk統合
   - RBAC (ロールベースアクセス制御)

2. **ドキュメント管理**
   - ドラッグ&ドロップアップロード
   - フォルダ管理
   - タグ付け

3. **高度な検索**
   - フィルタリング
   - ファセット検索
   - 検索履歴

4. **組織管理**
   - マルチテナント
   - 使用量制限
   - 課金機能

---

**最終更新**: 2025-12-27

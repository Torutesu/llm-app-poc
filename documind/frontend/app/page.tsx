import Link from 'next/link'
import { ArrowRight, FileSearch, Zap, Shield, Users } from 'lucide-react'

export default function Home() {
  return (
    <div className="min-h-screen bg-gradient-to-b from-blue-50 to-white dark:from-gray-900 dark:to-gray-800">
      {/* Navigation */}
      <nav className="border-b bg-white/50 backdrop-blur-lg dark:bg-gray-900/50">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between items-center h-16">
            <div className="flex items-center space-x-2">
              <FileSearch className="h-8 w-8 text-blue-600" />
              <span className="text-2xl font-bold text-gray-900 dark:text-white">DocuMind</span>
            </div>
            <div className="flex items-center space-x-4">
              <Link
                href="/auth/login"
                className="text-gray-600 hover:text-gray-900 dark:text-gray-300 dark:hover:text-white"
              >
                ログイン
              </Link>
              <Link
                href="/auth/register"
                className="bg-blue-600 text-white px-4 py-2 rounded-lg hover:bg-blue-700 transition"
              >
                無料で始める
              </Link>
            </div>
          </div>
        </div>
      </nav>

      {/* Hero Section */}
      <section className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-20">
        <div className="text-center">
          <h1 className="text-5xl md:text-6xl font-bold text-gray-900 dark:text-white mb-6">
            企業のドキュメントを
            <span className="text-blue-600"> AI が理解する</span>
          </h1>
          <p className="text-xl text-gray-600 dark:text-gray-300 mb-8 max-w-3xl mx-auto">
            DocuMindは、社内文書をリアルタイムで同期・解析し、
            自然言語で質問できる次世代のナレッジマネジメントプラットフォームです
          </p>
          <div className="flex justify-center space-x-4">
            <Link
              href="/auth/register"
              className="bg-blue-600 text-white px-8 py-3 rounded-lg hover:bg-blue-700 transition flex items-center space-x-2 text-lg"
            >
              <span>今すぐ無料で試す</span>
              <ArrowRight className="h-5 w-5" />
            </Link>
            <Link
              href="/demo"
              className="bg-white text-blue-600 px-8 py-3 rounded-lg border-2 border-blue-600 hover:bg-blue-50 transition text-lg"
            >
              デモを見る
            </Link>
          </div>
        </div>
      </section>

      {/* Features Section */}
      <section className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-20">
        <h2 className="text-3xl font-bold text-center text-gray-900 dark:text-white mb-12">
          主な機能
        </h2>
        <div className="grid md:grid-cols-2 lg:grid-cols-4 gap-8">
          <FeatureCard
            icon={<Zap className="h-10 w-10 text-blue-600" />}
            title="リアルタイム同期"
            description="Google Drive、SharePoint等から自動同期。ドキュメント更新を即座に反映"
          />
          <FeatureCard
            icon={<FileSearch className="h-10 w-10 text-blue-600" />}
            title="高度なAI検索"
            description="画像、テーブル、テキストを統合解析。自然言語で質問して回答を取得"
          />
          <FeatureCard
            icon={<Shield className="h-10 w-10 text-blue-600" />}
            title="エンタープライズ対応"
            description="権限管理、監査ログ、SOC2準拠のセキュリティ"
          />
          <FeatureCard
            icon={<Users className="h-10 w-10 text-blue-600" />}
            title="チームコラボレーション"
            description="組織全体でナレッジを共有。誰でも簡単にアクセス"
          />
        </div>
      </section>

      {/* CTA Section */}
      <section className="bg-blue-600 text-white py-20">
        <div className="max-w-4xl mx-auto text-center px-4">
          <h2 className="text-4xl font-bold mb-6">
            今すぐドキュメント管理を革新しましょう
          </h2>
          <p className="text-xl mb-8 text-blue-100">
            14日間の無料トライアル。クレジットカード不要。
          </p>
          <Link
            href="/auth/register"
            className="bg-white text-blue-600 px-8 py-3 rounded-lg hover:bg-gray-100 transition text-lg font-semibold inline-block"
          >
            無料で始める
          </Link>
        </div>
      </section>

      {/* Footer */}
      <footer className="bg-gray-900 text-gray-400 py-12">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="text-center">
            <div className="flex items-center justify-center space-x-2 mb-4">
              <FileSearch className="h-6 w-6 text-blue-500" />
              <span className="text-xl font-bold text-white">DocuMind</span>
            </div>
            <p className="text-sm">© 2025 DocuMind. All rights reserved.</p>
          </div>
        </div>
      </footer>
    </div>
  )
}

function FeatureCard({ icon, title, description }: { icon: React.ReactNode; title: string; description: string }) {
  return (
    <div className="bg-white dark:bg-gray-800 p-6 rounded-xl shadow-lg hover:shadow-xl transition">
      <div className="mb-4">{icon}</div>
      <h3 className="text-xl font-semibold text-gray-900 dark:text-white mb-2">{title}</h3>
      <p className="text-gray-600 dark:text-gray-300">{description}</p>
    </div>
  )
}

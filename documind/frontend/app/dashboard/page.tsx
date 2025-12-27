'use client'

import { FileText, MessageSquare, Database, TrendingUp } from 'lucide-react'

export default function DashboardHome() {
  return (
    <div className="p-8">
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-gray-900 dark:text-white mb-2">
          ダッシュボード
        </h1>
        <p className="text-gray-600 dark:text-gray-400">
          組織全体のドキュメントとアクティビティを確認できます
        </p>
      </div>

      {/* Stats Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
        <StatCard
          icon={<FileText className="h-8 w-8 text-blue-600" />}
          title="総ドキュメント数"
          value="1,234"
          change="+12%"
          changeType="positive"
        />
        <StatCard
          icon={<Database className="h-8 w-8 text-green-600" />}
          title="インデックス済み"
          value="1,180"
          change="+8%"
          changeType="positive"
        />
        <StatCard
          icon={<MessageSquare className="h-8 w-8 text-purple-600" />}
          title="今月の質問数"
          value="567"
          change="+23%"
          changeType="positive"
        />
        <StatCard
          icon={<TrendingUp className="h-8 w-8 text-orange-600" />}
          title="ストレージ使用量"
          value="45.2 GB"
          change="2.1 GB"
          changeType="neutral"
        />
      </div>

      {/* Recent Activity */}
      <div className="bg-white dark:bg-gray-800 rounded-lg shadow p-6">
        <h2 className="text-xl font-semibold text-gray-900 dark:text-white mb-4">
          最近のアクティビティ
        </h2>
        <div className="space-y-4">
          <ActivityItem
            type="document"
            title="新しいドキュメントがアップロードされました"
            description="financial_report_Q4_2024.pdf"
            time="5分前"
          />
          <ActivityItem
            type="chat"
            title="AIアシスタントへの質問"
            description="Q4の売上推移について教えてください"
            time="15分前"
          />
          <ActivityItem
            type="sync"
            title="Google Driveとの同期完了"
            description="23個の新しいファイルが追加されました"
            time="1時間前"
          />
          <ActivityItem
            type="document"
            title="ドキュメントのインデックス完了"
            description="product_roadmap_2025.pptx"
            time="2時間前"
          />
        </div>
      </div>
    </div>
  )
}

function StatCard({
  icon,
  title,
  value,
  change,
  changeType,
}: {
  icon: React.ReactNode
  title: string
  value: string
  change: string
  changeType: 'positive' | 'negative' | 'neutral'
}) {
  const changeColor =
    changeType === 'positive'
      ? 'text-green-600'
      : changeType === 'negative'
      ? 'text-red-600'
      : 'text-gray-600'

  return (
    <div className="bg-white dark:bg-gray-800 rounded-lg shadow p-6">
      <div className="flex items-center justify-between mb-4">
        {icon}
        <span className={`text-sm font-medium ${changeColor}`}>{change}</span>
      </div>
      <h3 className="text-sm font-medium text-gray-600 dark:text-gray-400 mb-1">{title}</h3>
      <p className="text-2xl font-bold text-gray-900 dark:text-white">{value}</p>
    </div>
  )
}

function ActivityItem({
  type,
  title,
  description,
  time,
}: {
  type: string
  title: string
  description: string
  time: string
}) {
  const iconMap: Record<string, React.ReactNode> = {
    document: <FileText className="h-5 w-5 text-blue-600" />,
    chat: <MessageSquare className="h-5 w-5 text-purple-600" />,
    sync: <Database className="h-5 w-5 text-green-600" />,
  }

  return (
    <div className="flex items-start space-x-3 p-3 hover:bg-gray-50 dark:hover:bg-gray-700 rounded-lg transition">
      <div className="flex-shrink-0 mt-1">{iconMap[type]}</div>
      <div className="flex-1 min-w-0">
        <p className="text-sm font-medium text-gray-900 dark:text-white">{title}</p>
        <p className="text-sm text-gray-600 dark:text-gray-400 truncate">{description}</p>
      </div>
      <span className="text-xs text-gray-500 dark:text-gray-400 whitespace-nowrap">{time}</span>
    </div>
  )
}

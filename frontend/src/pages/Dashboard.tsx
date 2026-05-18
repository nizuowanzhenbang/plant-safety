import { useEffect, useState, useCallback } from 'react'
import { Row, Col, Card, Statistic, Progress } from 'antd'
import {
  AlertOutlined,
  ClockCircleOutlined,
  ExclamationCircleOutlined,
  CheckCircleOutlined,
} from '@ant-design/icons'
import ReactECharts from 'echarts-for-react'
import type { EChartsOption } from 'echarts'
import { dashboardApi } from '../api'
import type { OverviewData, AreaStatItem, CategoryStatItem, TrendItem } from '../types'

const AREA_LABEL: Record<string, string> = {
  MAIN_PLANT: '主厂房', BOILER: '锅炉区', TURBINE: '汽轮机区',
  ELECTRICAL: '电气区', FUEL: '燃料区', CHEMICAL: '化学水',
  ASH_HANDLING: '除灰除渣', DESULFURIZATION: '脱硫脱硝',
  COOLING_TOWER: '冷却塔', SWITCHYARD: '开关站', OFFICE: '办公区', OTHER: '其他',
}

const CATEGORY_LABEL: Record<string, string> = {
  ELECTRICAL_SAFETY: '电气安全', PRESSURE_VESSEL: '压力容器',
  CHEMICAL_HAZARD: '危险化学品', WORK_AT_HEIGHT: '高处作业',
  CONFINED_SPACE: '有限空间', HOT_WORK: '动火作业', LIFTING: '起重作业',
  RADIATION: '辐射防护', FIRE_PROTECTION: '消防安全',
  MECHANICAL: '机械伤害', ENVIRONMENTAL: '环境排放',
  HOUSEKEEPING: '现场环境', OTHER: '其他',
}

export default function Dashboard() {
  const [overview, setOverview] = useState<OverviewData | null>(null)
  const [areaStats, setAreaStats] = useState<AreaStatItem[]>([])
  const [categoryStats, setCategoryStats] = useState<CategoryStatItem[]>([])
  const [trend, setTrend] = useState<TrendItem[]>([])
  const [loading, setLoading] = useState(true)

  const load = useCallback(async () => {
    try {
      const [ov, area, cat, tr] = await Promise.all([
        dashboardApi.overview(),
        dashboardApi.byArea(),
        dashboardApi.byCategory(),
        dashboardApi.trend(30),
      ])
      setOverview(ov.data)
      setAreaStats(area.data)
      setCategoryStats(cat.data)
      setTrend(tr.data)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    load()
    const t = setInterval(load, 60000)
    return () => clearInterval(t)
  }, [load])

  const areaOption: EChartsOption = {
    tooltip: { trigger: 'item' },
    series: [{
      type: 'pie', radius: ['40%', '70%'],
      data: areaStats.map((s) => ({ name: AREA_LABEL[s.area] || s.area, value: s.count })),
    }],
  }

  const categoryOption: EChartsOption = {
    tooltip: { trigger: 'axis' },
    grid: { left: 100, right: 20, top: 10, bottom: 30 },
    xAxis: { type: 'value' },
    yAxis: {
      type: 'category',
      data: categoryStats.map((s) => CATEGORY_LABEL[s.category] || s.category),
    },
    series: [{
      type: 'bar',
      data: categoryStats.map((s) => s.count),
      itemStyle: { color: '#1677ff' },
    }],
  }

  const trendOption: EChartsOption = {
    tooltip: { trigger: 'axis' },
    legend: { data: ['一般隐患', '重大隐患'], bottom: 0 },
    grid: { left: 40, right: 20, top: 20, bottom: 40 },
    xAxis: { type: 'category', data: trend.map((t) => t.date.slice(5)) },
    yAxis: { type: 'value' },
    series: [
      { name: '一般隐患', type: 'bar', stack: 'a', data: trend.map((t) => t.general), itemStyle: { color: '#faad14' } },
      { name: '重大隐患', type: 'bar', stack: 'a', data: trend.map((t) => t.major), itemStyle: { color: '#ff4d4f' } },
    ],
  }

  return (
    <div>
      <Row gutter={[16, 16]} style={{ marginBottom: 20 }}>
        <Col xs={24} sm={12} lg={6}>
          <Card loading={loading}>
            <Statistic
              title="总隐患数"
              value={overview?.total_hazards ?? 0}
              prefix={<AlertOutlined style={{ color: '#1677ff' }} />}
            />
          </Card>
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <Card loading={loading}>
            <Statistic
              title="待整改"
              value={overview?.pending_count ?? 0}
              valueStyle={{ color: (overview?.pending_count ?? 0) > 0 ? '#faad14' : 'inherit' }}
              prefix={<ClockCircleOutlined style={{ color: '#faad14' }} />}
            />
          </Card>
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <Card loading={loading}>
            <Statistic
              title="超期未整改"
              value={overview?.overdue_count ?? 0}
              valueStyle={{ color: (overview?.overdue_count ?? 0) > 0 ? '#ff4d4f' : 'inherit' }}
              prefix={<ExclamationCircleOutlined style={{ color: '#ff4d4f' }} />}
            />
          </Card>
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <Card loading={loading}>
            <Statistic
              title="重大隐患"
              value={overview?.major_count ?? 0}
              valueStyle={{ color: (overview?.major_count ?? 0) > 0 ? '#ff4d4f' : '#52c41a' }}
              prefix={<ExclamationCircleOutlined />}
            />
          </Card>
        </Col>
      </Row>

      <Row gutter={[16, 16]} style={{ marginBottom: 20 }}>
        <Col xs={24} lg={12}>
          <Card title="本月整改率" loading={loading}>
            <div style={{ padding: '8px 0' }}>
              <Progress
                percent={overview?.rectification_rate ?? 0}
                strokeColor={(overview?.rectification_rate ?? 0) >= 80 ? '#52c41a' : '#faad14'}
              />
              <div style={{ marginTop: 12, fontSize: 13, color: '#666' }}>
                本月新增 <b>{overview?.new_this_month ?? 0}</b> 条，已关闭{' '}
                <b style={{ color: '#52c41a' }}>{overview?.closed_this_month ?? 0}</b> 条
                <CheckCircleOutlined style={{ color: '#52c41a', marginLeft: 6 }} />
              </div>
            </div>
          </Card>
        </Col>
        <Col xs={24} lg={12}>
          <Card title="按发生区域分布" loading={loading}>
            <ReactECharts option={areaOption} style={{ height: 220 }} notMerge />
          </Card>
        </Col>
      </Row>

      <Row gutter={[16, 16]}>
        <Col xs={24} lg={12}>
          <Card title="按隐患类别分布" loading={loading}>
            <ReactECharts option={categoryOption} style={{ height: 320 }} notMerge />
          </Card>
        </Col>
        <Col xs={24} lg={12}>
          <Card title="近30天隐患新增趋势" loading={loading}>
            <ReactECharts option={trendOption} style={{ height: 320 }} notMerge />
          </Card>
        </Col>
      </Row>
    </div>
  )
}

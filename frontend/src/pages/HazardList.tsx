import { useState, useEffect, useCallback } from 'react'
import {
  Card, Table, Tag, Button, Space, Modal, Form, Input, Select,
  DatePicker, message, Descriptions, Row, Col,
} from 'antd'
import type { ColumnsType } from 'antd/es/table'
import { PlusOutlined, ReloadOutlined, EyeOutlined } from '@ant-design/icons'
import dayjs from 'dayjs'
import { hazardApi } from '../api'
import type { Hazard, HazardArea, HazardCategory, HazardLevel, HazardStatus } from '../types'

const AREA_OPTIONS = [
  ['MAIN_PLANT', '主厂房'], ['BOILER', '锅炉区'], ['TURBINE', '汽轮机区'],
  ['ELECTRICAL', '电气区'], ['FUEL', '燃料区'], ['CHEMICAL', '化学水'],
  ['ASH_HANDLING', '除灰除渣'], ['DESULFURIZATION', '脱硫脱硝'],
  ['COOLING_TOWER', '冷却塔'], ['SWITCHYARD', '开关站'],
  ['OFFICE', '办公区'], ['OTHER', '其他'],
] as const

const CATEGORY_OPTIONS = [
  ['ELECTRICAL_SAFETY', '电气安全'], ['PRESSURE_VESSEL', '压力容器'],
  ['CHEMICAL_HAZARD', '危险化学品'], ['WORK_AT_HEIGHT', '高处作业'],
  ['CONFINED_SPACE', '有限空间'], ['HOT_WORK', '动火作业'],
  ['LIFTING', '起重作业'], ['RADIATION', '辐射防护'],
  ['FIRE_PROTECTION', '消防安全'], ['MECHANICAL', '机械伤害'],
  ['ENVIRONMENTAL', '环境排放'], ['HOUSEKEEPING', '现场环境'],
  ['OTHER', '其他'],
] as const

const STATUS_LABEL: Record<HazardStatus, { label: string; color: string }> = {
  PENDING: { label: '待整改', color: 'default' },
  IN_PROGRESS: { label: '整改中', color: 'processing' },
  RECTIFIED: { label: '待复查', color: 'warning' },
  VERIFIED: { label: '已关闭', color: 'success' },
  OVERDUE: { label: '超期', color: 'error' },
}

const LEVEL_LABEL: Record<HazardLevel, { label: string; color: string }> = {
  GENERAL: { label: '一般', color: 'orange' },
  MAJOR: { label: '重大', color: 'red' },
}

const labelOf = (list: readonly (readonly [string, string])[], key: string) =>
  list.find(([k]) => k === key)?.[1] || key

export default function HazardList() {
  const [data, setData] = useState<Hazard[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(20)
  const [loading, setLoading] = useState(false)
  const [filters, setFilters] = useState<{ status?: HazardStatus; level?: HazardLevel; area?: HazardArea; keyword?: string }>({})
  const [createOpen, setCreateOpen] = useState(false)
  const [detail, setDetail] = useState<Hazard | null>(null)
  const [rectifyOpen, setRectifyOpen] = useState(false)
  const [verifyOpen, setVerifyOpen] = useState(false)
  const [form] = Form.useForm()
  const [rectifyForm] = Form.useForm()
  const [verifyForm] = Form.useForm()

  const load = useCallback(async (p = page, ps = pageSize, f = filters) => {
    setLoading(true)
    try {
      const res = await hazardApi.list({ page: p, page_size: ps, ...f })
      setData(res.data.items)
      setTotal(res.data.total)
    } catch {
      message.error('加载失败')
    } finally {
      setLoading(false)
    }
  }, [page, pageSize, filters])

  useEffect(() => { load(1, 20, {}) }, [])

  const handleCreate = async (values: { deadline?: dayjs.Dayjs } & Partial<Hazard>) => {
    try {
      const payload = {
        ...values,
        deadline: values.deadline ? values.deadline.toISOString() : null,
      }
      await hazardApi.create(payload as Partial<Hazard>)
      message.success('隐患已登记')
      setCreateOpen(false)
      form.resetFields()
      load()
    } catch (e: unknown) {
      message.error((e as { detail?: string })?.detail || '创建失败')
    }
  }

  const handleRectify = async (values: { rectification_measure: string }) => {
    if (!detail) return
    try {
      await hazardApi.rectify(detail.id, values.rectification_measure)
      message.success('整改已提交')
      setRectifyOpen(false)
      rectifyForm.resetFields()
      setDetail(null)
      load()
    } catch (e: unknown) {
      message.error((e as { detail?: string })?.detail || '提交失败')
    }
  }

  const handleVerify = async (values: { verifier: string; verification_notes: string; passed: boolean }) => {
    if (!detail) return
    try {
      await hazardApi.verify(detail.id, values.verifier, values.verification_notes, values.passed)
      message.success(values.passed ? '复查通过' : '已退回整改')
      setVerifyOpen(false)
      verifyForm.resetFields()
      setDetail(null)
      load()
    } catch (e: unknown) {
      message.error((e as { detail?: string })?.detail || '操作失败')
    }
  }

  const columns: ColumnsType<Hazard> = [
    { title: '编号', dataIndex: 'hazard_code', width: 140 },
    { title: '标题', dataIndex: 'title', ellipsis: true },
    { title: '区域', dataIndex: 'area', width: 100, render: (v) => labelOf(AREA_OPTIONS, v) },
    { title: '类别', dataIndex: 'category', width: 110, render: (v) => labelOf(CATEGORY_OPTIONS, v) },
    {
      title: '等级', dataIndex: 'level', width: 80,
      render: (v: HazardLevel) => <Tag color={LEVEL_LABEL[v].color}>{LEVEL_LABEL[v].label}</Tag>,
    },
    {
      title: '状态', dataIndex: 'status', width: 100,
      render: (v: HazardStatus) => <Tag color={STATUS_LABEL[v].color}>{STATUS_LABEL[v].label}</Tag>,
    },
    {
      title: '整改期限', dataIndex: 'deadline', width: 110,
      render: (v: string | null) => v ? dayjs(v).format('MM-DD') : '-',
    },
    { title: '发现人', dataIndex: 'reporter', width: 90 },
    {
      title: '操作', width: 70,
      render: (_, r) => <Button type="link" icon={<EyeOutlined />} onClick={() => setDetail(r)} />,
    },
  ]

  return (
    <div>
      <Card>
        <Row gutter={12} style={{ marginBottom: 16 }}>
          <Col>
            <Button type="primary" icon={<PlusOutlined />} onClick={() => setCreateOpen(true)}>
              登记隐患
            </Button>
          </Col>
          <Col flex="auto">
            <Space wrap>
              <Input
                placeholder="标题/描述关键字"
                style={{ width: 200 }}
                allowClear
                onChange={(e) => setFilters((f) => ({ ...f, keyword: e.target.value || undefined }))}
                onPressEnter={() => { setPage(1); load(1, pageSize) }}
              />
              <Select
                placeholder="区域" allowClear style={{ width: 130 }}
                options={AREA_OPTIONS.map(([v, l]) => ({ value: v, label: l }))}
                onChange={(v) => { setFilters((f) => ({ ...f, area: v })); setPage(1); load(1, pageSize, { ...filters, area: v }) }}
              />
              <Select
                placeholder="状态" allowClear style={{ width: 110 }}
                options={Object.entries(STATUS_LABEL).map(([v, { label }]) => ({ value: v, label }))}
                onChange={(v) => { setFilters((f) => ({ ...f, status: v })); setPage(1); load(1, pageSize, { ...filters, status: v }) }}
              />
              <Select
                placeholder="等级" allowClear style={{ width: 90 }}
                options={[{ value: 'GENERAL', label: '一般' }, { value: 'MAJOR', label: '重大' }]}
                onChange={(v) => { setFilters((f) => ({ ...f, level: v })); setPage(1); load(1, pageSize, { ...filters, level: v }) }}
              />
              <Button icon={<ReloadOutlined />} onClick={() => { setFilters({}); setPage(1); load(1, pageSize, {}) }}>
                重置
              </Button>
            </Space>
          </Col>
        </Row>

        <Table<Hazard>
          dataSource={data}
          columns={columns}
          rowKey="id"
          loading={loading}
          scroll={{ x: 1100 }}
          pagination={{
            current: page, pageSize, total,
            showSizeChanger: true,
            showTotal: (t) => `共 ${t} 条`,
            onChange: (p, ps) => { setPage(p); setPageSize(ps); load(p, ps) },
          }}
        />
      </Card>

      {/* 创建隐患 */}
      <Modal title="登记新隐患" open={createOpen} onCancel={() => setCreateOpen(false)} onOk={() => form.submit()} width={680} okText="登记">
        <Form form={form} layout="vertical" onFinish={handleCreate} initialValues={{ level: 'GENERAL' }}>
          <Form.Item name="title" label="隐患标题" rules={[{ required: true }]}>
            <Input placeholder="如：高压配电柜接地线松动" />
          </Form.Item>
          <Form.Item name="description" label="详细描述" rules={[{ required: true }]}>
            <Input.TextArea rows={3} placeholder="发生位置、现象、可能后果" />
          </Form.Item>
          <Row gutter={12}>
            <Col span={8}>
              <Form.Item name="area" label="发生区域" rules={[{ required: true }]}>
                <Select options={AREA_OPTIONS.map(([v, l]) => ({ value: v, label: l }))} />
              </Form.Item>
            </Col>
            <Col span={8}>
              <Form.Item name="category" label="隐患类别" rules={[{ required: true }]}>
                <Select options={CATEGORY_OPTIONS.map(([v, l]) => ({ value: v, label: l }))} />
              </Form.Item>
            </Col>
            <Col span={8}>
              <Form.Item name="level" label="等级" rules={[{ required: true }]}>
                <Select options={[{ value: 'GENERAL', label: '一般' }, { value: 'MAJOR', label: '重大' }]} />
              </Form.Item>
            </Col>
          </Row>
          <Row gutter={12}>
            <Col span={8}>
              <Form.Item name="reporter" label="发现人" rules={[{ required: true }]}>
                <Input />
              </Form.Item>
            </Col>
            <Col span={8}>
              <Form.Item name="department" label="发现部门">
                <Input />
              </Form.Item>
            </Col>
            <Col span={8}>
              <Form.Item name="deadline" label="整改期限">
                <DatePicker style={{ width: '100%' }} />
              </Form.Item>
            </Col>
          </Row>
          <Row gutter={12}>
            <Col span={12}>
              <Form.Item name="assignee" label="整改责任人">
                <Input />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item name="assignee_dept" label="整改部门">
                <Input />
              </Form.Item>
            </Col>
          </Row>
        </Form>
      </Modal>

      {/* 详情 */}
      <Modal
        title={detail ? `隐患详情 - ${detail.hazard_code}` : ''}
        open={!!detail}
        onCancel={() => setDetail(null)}
        width={760}
        footer={detail ? (
          <Space>
            {(detail.status === 'PENDING' || detail.status === 'IN_PROGRESS' || detail.status === 'OVERDUE') && (
              <Button type="primary" onClick={() => setRectifyOpen(true)}>提交整改</Button>
            )}
            {detail.status === 'RECTIFIED' && (
              <Button type="primary" onClick={() => setVerifyOpen(true)}>复查确认</Button>
            )}
            <Button onClick={() => setDetail(null)}>关闭</Button>
          </Space>
        ) : null}
      >
        {detail && (
          <Descriptions column={2} bordered size="small">
            <Descriptions.Item label="编号">{detail.hazard_code}</Descriptions.Item>
            <Descriptions.Item label="状态">
              <Tag color={STATUS_LABEL[detail.status].color}>{STATUS_LABEL[detail.status].label}</Tag>
            </Descriptions.Item>
            <Descriptions.Item label="标题" span={2}>{detail.title}</Descriptions.Item>
            <Descriptions.Item label="描述" span={2}>{detail.description}</Descriptions.Item>
            <Descriptions.Item label="区域">{labelOf(AREA_OPTIONS, detail.area)}</Descriptions.Item>
            <Descriptions.Item label="类别">{labelOf(CATEGORY_OPTIONS, detail.category)}</Descriptions.Item>
            <Descriptions.Item label="等级">
              <Tag color={LEVEL_LABEL[detail.level].color}>{LEVEL_LABEL[detail.level].label}</Tag>
            </Descriptions.Item>
            <Descriptions.Item label="整改期限">
              {detail.deadline ? dayjs(detail.deadline).format('YYYY-MM-DD') : '-'}
            </Descriptions.Item>
            <Descriptions.Item label="发现人">{detail.reporter} ({detail.department || '-'})</Descriptions.Item>
            <Descriptions.Item label="发现时间">{dayjs(detail.reported_at).format('YYYY-MM-DD HH:mm')}</Descriptions.Item>
            <Descriptions.Item label="责任人">{detail.assignee || '-'} ({detail.assignee_dept || '-'})</Descriptions.Item>
            <Descriptions.Item label="整改完成">
              {detail.rectified_at ? dayjs(detail.rectified_at).format('YYYY-MM-DD HH:mm') : '-'}
            </Descriptions.Item>
            {detail.rectification_measure && (
              <Descriptions.Item label="整改措施" span={2}>{detail.rectification_measure}</Descriptions.Item>
            )}
            {detail.verified_at && (
              <Descriptions.Item label="复查" span={2}>
                {detail.verifier} 于 {dayjs(detail.verified_at).format('YYYY-MM-DD HH:mm')}：{detail.verification_notes}
              </Descriptions.Item>
            )}
          </Descriptions>
        )}
      </Modal>

      {/* 提交整改 */}
      <Modal title="提交整改完成" open={rectifyOpen} onCancel={() => setRectifyOpen(false)} onOk={() => rectifyForm.submit()}>
        <Form form={rectifyForm} layout="vertical" onFinish={handleRectify}>
          <Form.Item name="rectification_measure" label="整改措施" rules={[{ required: true }]}>
            <Input.TextArea rows={4} placeholder="描述已采取的整改措施" />
          </Form.Item>
        </Form>
      </Modal>

      {/* 复查 */}
      <Modal title="复查确认" open={verifyOpen} onCancel={() => setVerifyOpen(false)} onOk={() => verifyForm.submit()}>
        <Form form={verifyForm} layout="vertical" onFinish={handleVerify} initialValues={{ passed: true }}>
          <Form.Item name="verifier" label="复查人" rules={[{ required: true }]}>
            <Input />
          </Form.Item>
          <Form.Item name="verification_notes" label="复查意见" rules={[{ required: true }]}>
            <Input.TextArea rows={3} />
          </Form.Item>
          <Form.Item name="passed" label="复查结果" rules={[{ required: true }]}>
            <Select options={[
              { value: true, label: '通过 - 关闭隐患' },
              { value: false, label: '未通过 - 退回整改' },
            ]} />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  )
}

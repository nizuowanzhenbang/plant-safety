import { useState } from 'react'
import { Card, Form, Input, Button, Typography, message } from 'antd'
import { UserOutlined, LockOutlined, SafetyCertificateOutlined } from '@ant-design/icons'
import { useNavigate } from 'react-router-dom'
import { authApi } from '../api'
import { useAuthStore } from '../stores/auth'

const { Title, Text } = Typography

export default function LoginPage() {
  const navigate = useNavigate()
  const [loading, setLoading] = useState(false)
  const setAuth = useAuthStore((s) => s.setAuth)

  const onFinish = async (values: { username: string; password: string }) => {
    setLoading(true)
    try {
      const res = await authApi.login(values.username, values.password)
      const me = await fetch('/api/auth/me', {
        headers: { Authorization: `Bearer ${res.access_token}` },
      }).then((r) => r.json())
      setAuth(res.access_token, me.data.username, me.data.role)
      message.success('登录成功')
      navigate('/dashboard')
    } catch (e: unknown) {
      const detail = (e as { detail?: string })?.detail
      message.error(detail || '登录失败')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div
      style={{
        minHeight: '100vh',
        display: 'flex',
        justifyContent: 'center',
        alignItems: 'center',
        background: 'linear-gradient(135deg, #1677ff 0%, #003a8c 100%)',
      }}
    >
      <Card style={{ width: 400, padding: 8 }}>
        <div style={{ textAlign: 'center', marginBottom: 24 }}>
          <SafetyCertificateOutlined style={{ fontSize: 48, color: '#1677ff' }} />
          <Title level={3} style={{ marginTop: 12, marginBottom: 4 }}>
            发电厂安全管理系统
          </Title>
          <Text type="secondary">隐患排查与整改闭环</Text>
        </div>
        <Form onFinish={onFinish} layout="vertical" initialValues={{ username: 'admin' }}>
          <Form.Item name="username" rules={[{ required: true, message: '请输入用户名' }]}>
            <Input prefix={<UserOutlined />} placeholder="用户名" size="large" />
          </Form.Item>
          <Form.Item name="password" rules={[{ required: true, message: '请输入密码' }]}>
            <Input.Password prefix={<LockOutlined />} placeholder="密码" size="large" />
          </Form.Item>
          <Form.Item>
            <Button type="primary" htmlType="submit" loading={loading} block size="large">
              登录
            </Button>
          </Form.Item>
          <Text type="secondary" style={{ fontSize: 12 }}>
            默认账户：admin / admin123
          </Text>
        </Form>
      </Card>
    </div>
  )
}

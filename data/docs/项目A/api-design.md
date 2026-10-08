# Project A — API 接口文档

> 版本：v1.0.0 | 更新日期：2026-07-28 | Base URL: `http://localhost:8080/api/v1`

## 1. 通用约定

### 1.1 认证方式

采用 **Bearer Token (JWT)** 认证。除公开接口外，所有接口需在请求头中携带 Token：

```
Authorization: Bearer eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6ImFkbWluIiwiaWF0IjoxNzIxOTQwMDAwLCJleHAiOjE3MjE5NDcyMDB9.xxx
```

- Access Token 有效期：**2 小时**
- Refresh Token 有效期：**7 天**
- Token 过期后，前端通过 `/auth/refresh` 接口换取新的 Access Token

### 1.2 通用请求头

| Header | 值 | 是否必填 | 说明 |
|--------|---|---------|------|
| `Content-Type` | `application/json` | 是 | 请求体格式 |
| `Authorization` | `Bearer {token}` | 是（除公开接口） | JWT Token |
| `X-Request-Id` | UUID | 否 | 请求追踪 ID |

### 1.3 通用响应格式

成功响应：

```json
{
    "code": 200,
    "message": "success",
    "data": { ... }
}
```

分页响应：

```json
{
    "code": 200,
    "message": "success",
    "data": {
        "list": [...],
        "total": 150,
        "page": 1,
        "size": 20
    }
}
```

### 1.4 通用错误码

| 错误码 | HTTP 状态码 | 说明 |
|--------|-----------|------|
| 200 | 200 | 请求成功 |
| 400 | 400 | 参数校验失败 |
| 401 | 401 | 未认证或 Token 已过期 |
| 403 | 403 | 无权限访问该资源 |
| 404 | 404 | 资源不存在 |
| 409 | 409 | 资源冲突（如用户名已存在） |
| 500 | 500 | 服务器内部错误 |

错误响应示例：

```json
{
    "code": 400,
    "message": "参数校验失败：课程标题不能为空",
    "data": null
}
```

---

## 2. 课程接口

### 2.1 创建课程

**POST** `/courses`

权限要求：`TEACHER` 或 `ADMIN`

请求参数：

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `title` | String | 是 | 课程标题，2~200 字符 |
| `description` | String | 否 | 课程描述 |
| `categoryId` | Long | 否 | 分类 ID |
| `price` | BigDecimal | 是 | 售价，单位：元 |
| `originalPrice` | BigDecimal | 否 | 原价，用于展示划线价 |
| `coverUrl` | String | 否 | 封面图片 URL |

请求示例：

```json
POST /api/v1/courses
Content-Type: application/json
Authorization: Bearer eyJhbGciOiJIUzI1NiJ9.xxx

{
    "title": "Spring Boot 3 实战教程",
    "description": "从零到一搭建企业级 Spring Boot 项目",
    "categoryId": 10,
    "price": 199.00,
    "originalPrice": 399.00,
    "coverUrl": "https://edu-oss.oss-cn-beijing.aliyuncs.com/covers/springboot.jpg"
}
```

响应示例：

```json
{
    "code": 200,
    "message": "success",
    "data": {
        "id": 10001,
        "title": "Spring Boot 3 实战教程",
        "status": 0,
        "createdAt": "2026-07-28T10:00:00"
    }
}
```

### 2.2 获取课程详情

**GET** `/courses/{id}`

权限要求：无（公开接口）

路径参数：

| 参数 | 类型 | 说明 |
|------|------|------|
| `id` | Long | 课程 ID |

响应示例：

```json
{
    "code": 200,
    "message": "success",
    "data": {
        "id": 10001,
        "title": "Spring Boot 3 实战教程",
        "coverUrl": "https://edu-oss.oss-cn-beijing.aliyuncs.com/covers/springboot.jpg",
        "description": "从零到一搭建企业级 Spring Boot 项目",
        "teacherId": 2001,
        "teacherName": "张老师",
        "categoryId": 10,
        "categoryName": "后端开发",
        "price": 199.00,
        "originalPrice": 399.00,
        "status": 1,
        "studentCount": 3562,
        "rating": 4.8,
        "chapterCount": 12,
        "chapters": [
            {
                "id": 1,
                "title": "第一章 环境搭建",
                "sortOrder": 1,
                "lessons": [
                    {
                        "id": 101,
                        "title": "1.1 JDK 安装与配置",
                        "videoUrl": null,
                        "durationSeconds": 600,
                        "isFree": true,
                        "sortOrder": 1
                    }
                ]
            }
        ]
    }
}
```

### 2.3 获取课程列表（分页）

**GET** `/courses`

权限要求：无（公开接口）

查询参数：

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `page` | Integer | 否 | 页码，默认 1 |
| `size` | Integer | 否 | 每页条数，默认 20，最大 50 |
| `categoryId` | Long | 否 | 分类 ID 筛选 |
| `status` | Integer | 否 | 课程状态筛选 |
| `keyword` | String | 否 | 搜索关键字（标题模糊匹配） |
| `sortBy` | String | 否 | 排序字段：`latest` / `popular` / `rating`，默认 `latest` |

请求示例：

```
GET /api/v1/courses?page=1&size=10&categoryId=10&sortBy=popular
```

响应示例：

```json
{
    "code": 200,
    "message": "success",
    "data": {
        "list": [
            {
                "id": 10001,
                "title": "Spring Boot 3 实战教程",
                "coverUrl": "https://edu-oss.../covers/springboot.jpg",
                "teacherName": "张老师",
                "price": 199.00,
                "originalPrice": 399.00,
                "studentCount": 3562,
                "rating": 4.8,
                "status": 1
            }
        ],
        "total": 156,
        "page": 1,
        "size": 10
    }
}
```

### 2.4 更新课程

**PUT** `/courses/{id}`

权限要求：课程创建者本人或 `ADMIN`

请求参数：与创建接口相同，所有字段均可选，仅传递需要修改的字段。

响应示例：

```json
{
    "code": 200,
    "message": "success",
    "data": {
        "id": 10001,
        "title": "Spring Boot 3 实战教程（第二版）",
        "updatedAt": "2026-07-28T14:30:00"
    }
}
```

### 2.5 删除课程

**DELETE** `/courses/{id}`

权限要求：课程创建者本人或 `ADMIN`

限制条件：课程状态必须为 `草稿(0)` 才可删除，已上架的课程需先下架。

响应示例：

```json
{
    "code": 200,
    "message": "success",
    "data": null
}
```

---

## 3. 视频接口

### 3.1 视频分片上传

**POST** `/videos/upload`

权限要求：`TEACHER` 或 `ADMIN`

请求参数（`multipart/form-data`）：

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `file` | File | 是 | 视频文件分片，每片 5MB |
| `uploadId` | String | 是 | 上传会话 ID（首次由后端生成） |
| `chunkIndex` | Integer | 是 | 当前分片序号，从 0 开始 |
| `totalChunks` | Integer | 是 | 总分片数 |
| `fileName` | String | 是 | 原始文件名 |
| `lessonId` | Long | 是 | 关联课时 ID |

响应示例：

```json
{
    "code": 200,
    "message": "success",
    "data": {
        "uploadId": "up_1722160800000_a3f8c1e2",
        "chunkIndex": 2,
        "completed": false,
        "ossPartETag": "\"a1b2c3d4\""
    }
}
```

当所有分片上传完毕后，后端自动调用 OSS `CompleteMultipartUpload` 合并文件，并返回视频信息：

```json
{
    "code": 200,
    "message": "success",
    "data": {
        "videoId": 5001,
        "ossUrl": "https://edu-oss.oss-cn-beijing.aliyuncs.com/videos/raw/5001.mp4",
        "fileName": "springboot-lesson01.mp4",
        "fileSize": 524288000,
        "transcodeStatus": "PENDING"
    }
}
```

### 3.2 查询转码状态

**GET** `/videos/{id}/transcode-status`

权限要求：`TEACHER` 或 `ADMIN`

响应示例：

```json
{
    "code": 200,
    "message": "success",
    "data": {
        "videoId": 5001,
        "status": "TRANSCODING",
        "progress": 65,
        "resolutions": [
            {
                "resolution": "1080p",
                "url": null,
                "status": "TRANSCODING"
            },
            {
                "resolution": "720p",
                "url": null,
                "status": "COMPLETED",
                "ossUrl": "https://edu-oss.../videos/720p/5001.mp4"
            },
            {
                "resolution": "480p",
                "url": null,
                "status": "PENDING"
            }
        ],
        "coverUrl": "https://edu-oss.../covers/5001.jpg",
        "createdAt": "2026-07-28T10:00:00",
        "updatedAt": "2026-07-28T10:15:00"
    }
}
```

转码状态枚举：`PENDING` | `TRANSCODING` | `COMPLETED` | `FAILED`

---

## 4. 订单接口

### 4.1 创建订单

**POST** `/orders`

权限要求：已登录学员

请求参数：

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `courseIds` | Long[] | 是 | 购买的课程 ID 列表 |
| `couponCode` | String | 否 | 优惠券兑换码 |

请求示例：

```json
{
    "courseIds": [10001, 10002],
    "couponCode": "SAVE50"
}
```

响应示例：

```json
{
    "code": 200,
    "message": "success",
    "data": {
        "orderId": 30001,
        "orderNo": "OD20260728143022123456",
        "totalAmount": 398.00,
        "discountAmount": 50.00,
        "payAmount": 348.00,
        "status": "CREATED",
        "expiredAt": "2026-07-28T14:45:22"
    }
}
```

> 订单创建后 **15 分钟** 未支付自动取消。

### 4.2 发起支付

**POST** `/orders/{id}/pay`

权限要求：订单所有者

请求参数：

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `payType` | String | 是 | 支付方式：`WECHAT` / `ALIPAY` |

响应示例（微信支付）：

```json
{
    "code": 200,
    "message": "success",
    "data": {
        "orderNo": "OD20260728143022123456",
        "payType": "WECHAT",
        "payParams": {
            "appId": "<YOUR_WECHAT_APP_ID>",
            "timeStamp": "1722160422",
            "nonceStr": "a1b2c3d4e5f6",
            "package": "prepay_id=wx26172160422xxx",
            "signType": "RSA",
            "paySign": "abc123def456..."
        }
    }
}
```

### 4.3 申请退款

**POST** `/orders/{id}/refund`

权限要求：订单所有者

限制条件：
- 已支付订单方可申请退款
- 支付后 **7 天内** 无理由退款
- 超过 7 天需提交退款说明，由管理员审核

请求参数：

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `reason` | String | 是 | 退款原因 |

响应示例：

```json
{
    "code": 200,
    "message": "退款申请已提交，预计 1~3 个工作日内处理",
    "data": {
        "orderId": 30001,
        "status": "REFUNDING"
    }
}
```

---

## 5. 用户认证接口

### 5.1 用户登录

**POST** `/auth/login`

请求参数：

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `username` | String | 是 | 用户名 |
| `password` | String | 是 | 密码（MD5 + 盐值加密传输） |

响应示例：

```json
{
    "code": 200,
    "message": "success",
    "data": {
        "accessToken": "eyJhbGciOiJIUzI1NiJ9.xxx",
        "refreshToken": "eyJhbGciOiJIUzI1NiJ9.yyy",
        "expiresIn": 7200,
        "user": {
            "id": 1001,
            "username": "student01",
            "nickname": "小明同学",
            "role": 0,
            "avatarUrl": "https://edu-oss.../avatars/1001.jpg"
        }
    }
}
```

### 5.2 刷新 Token

**POST** `/auth/refresh`

请求参数：

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `refreshToken` | String | 是 | 刷新令牌 |

---

## 6. 学习记录接口

### 6.1 上报学习进度

**POST** `/learning/progress`

权限要求：已登录学员，且已购买该课程

请求参数：

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `lessonId` | Long | 是 | 课时 ID |
| `watchDuration` | Integer | 是 | 本次观看时长（秒） |
| `lastPosition` | Integer | 是 | 最后播放位置（秒） |

---

## 7. 接口限流规则

| 接口 | 限流策略 | 限流值 |
|------|---------|--------|
| 登录接口 | IP 维度 | 10 次/分钟 |
| 发送验证码 | 手机号维度 | 1 次/分钟 |
| 视频上传 | 用户维度 | 3 个并发任务 |
| 课程列表 | IP 维度 | 60 次/分钟 |
| 订单创建 | 用户维度 | 10 次/分钟 |

限流通过 Redis + 自定义注解 `@RateLimiter` 实现，超限返回 HTTP 429。

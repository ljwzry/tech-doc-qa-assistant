# Project A — 数据库详细设计文档

> 版本：v1.0.0 | 更新日期：2026-07-28 | 数据库：MySQL 8.0

## 1. 数据库选型

| 项 | 说明 |
|----|------|
| 数据库 | MySQL 8.0.x |
| 存储引擎 | InnoDB（支持事务、行锁、外键） |
| 字符集 | utf8mb4（支持 emoji 和完整 Unicode） |
| 排序规则 | utf8mb4_general_ci（不区分大小写比较） |
| 连接池 | HikariCP（Spring Boot 3.2 默认） |

选择 MySQL 8.0 的理由：
- 在线教育业务以关系型数据为主，需要强事务保证（订单、支付）
- InnoDB 引擎支持行级锁，适合高并发读写场景
- JSON 字段支持灵活存储课程扩展属性
- 窗口函数（MySQL 8.0 新增）便于学习排行统计

## 2. ER 关系说明

```
+--------+       1:N       +-----------------+       1:N       +------------------+
|  user  |<----------------| course_chapter  |<---------------| course_lesson     |
| (教师) |  teacher_id    |   (章节)          |  chapter_id   |   (课时/视频)      |
+--------+                +-----------------+               +------------------+
     |                              ^
     | 1:N                          | N:1
     v                              |
+--------+       N:1      +-----------------+
|  user  |<----------------|     course       |
| (学员) |  teacher_id    |   (课程)          |
+--------+                +-----------------+
     |                              ^
     | 1:N                          | 1:N (通过 order_item)
     v                              |
+----------------+        +-----------------+
| learning_record |        |      order       |
| (学习记录)       |        |   (订单)          |
+----------------+        +-----------------+
```

核心关系说明：
- `user` (1) -> `course` (N)：一个教师可创建多门课程
- `course` (1) -> `course_chapter` (N)：一门课程包含多个章节
- `course_chapter` (1) -> `course_lesson` (N)：一个章节包含多个课时
- `user` (1) -> `order` (N)：一个用户可拥有多个订单
- `user` (1) -> `learning_record` (N)：一个学员可有多条学习记录

## 3. 完整 DDL

### 3.1 用户表 (user)

```sql
CREATE TABLE `user` (
    `id`          BIGINT       NOT NULL AUTO_INCREMENT COMMENT '用户主键',
    `username`    VARCHAR(50)  NOT NULL COMMENT '登录用户名',
    `nickname`    VARCHAR(50)  DEFAULT NULL COMMENT '昵称',
    `phone`       VARCHAR(20)  DEFAULT NULL COMMENT '手机号',
    `email`       VARCHAR(100) DEFAULT NULL COMMENT '邮箱',
    `avatar_url`  VARCHAR(500) DEFAULT NULL COMMENT '头像地址（OSS）',
    `password`    VARCHAR(255) NOT NULL COMMENT '密码（BCrypt加密）',
    `role`        TINYINT      NOT NULL DEFAULT 0 COMMENT '角色: 0-学员 1-教师 2-管理员',
    `status`      TINYINT      NOT NULL DEFAULT 1 COMMENT '状态: 0-禁用 1-正常',
    `created_at`  DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    `updated_at`  DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    PRIMARY KEY (`id`),
    UNIQUE KEY `uk_username` (`username`),
    UNIQUE KEY `uk_phone` (`phone`),
    KEY `idx_role` (`role`),
    KEY `idx_status` (`status`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='用户表';
```

### 3.2 课程表 (course)

```sql
CREATE TABLE `course` (
    `id`             BIGINT         NOT NULL AUTO_INCREMENT COMMENT '课程主键',
    `title`          VARCHAR(200)   NOT NULL COMMENT '课程标题',
    `cover_url`      VARCHAR(500)   DEFAULT NULL COMMENT '封面图片地址',
    `description`    TEXT           DEFAULT NULL COMMENT '课程描述',
    `teacher_id`     BIGINT         NOT NULL COMMENT '授课教师ID',
    `category_id`    BIGINT         DEFAULT NULL COMMENT '分类ID',
    `price`          DECIMAL(10,2)  NOT NULL DEFAULT 0.00 COMMENT '售价（元）',
    `original_price` DECIMAL(10,2)  DEFAULT NULL COMMENT '原价（元）',
    `status`         TINYINT        NOT NULL DEFAULT 0 COMMENT '状态: 0-草稿 1-已上架 2-已下架',
    `student_count`   INT            NOT NULL DEFAULT 0 COMMENT '学员数（冗余字段）',
    `rating`         DECIMAL(2,1)   NOT NULL DEFAULT 5.0 COMMENT '评分（1.0~5.0）',
    `chapter_count`  INT            NOT NULL DEFAULT 0 COMMENT '章节数（冗余字段）',
    `created_at`     DATETIME       NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    `updated_at`     DATETIME       NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    PRIMARY KEY (`id`),
    KEY `idx_teacher_id` (`teacher_id`),
    KEY `idx_category_id` (`category_id`),
    KEY `idx_status` (`status`),
    KEY `idx_created_at` (`created_at`),
    KEY `idx_title` (`title`(50))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='课程表';
```

### 3.3 课程章节表 (course_chapter)

```sql
CREATE TABLE `course_chapter` (
    `id`         BIGINT        NOT NULL AUTO_INCREMENT COMMENT '章节主键',
    `course_id`  BIGINT        NOT NULL COMMENT '所属课程ID',
    `title`      VARCHAR(200)  NOT NULL COMMENT '章节标题',
    `sort_order` INT           NOT NULL DEFAULT 0 COMMENT '排序序号',
    `created_at` DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    PRIMARY KEY (`id`),
    KEY `idx_course_id` (`course_id`),
    KEY `idx_sort_order` (`course_id`, `sort_order`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='课程章节表';
```

### 3.4 课程课时表 (course_lesson)

```sql
CREATE TABLE `course_lesson` (
    `id`              BIGINT        NOT NULL AUTO_INCREMENT COMMENT '课时主键',
    `chapter_id`      BIGINT        NOT NULL COMMENT '所属章节ID',
    `title`           VARCHAR(200)  NOT NULL COMMENT '课时标题',
    `video_url`       VARCHAR(500)   DEFAULT NULL COMMENT '视频地址（OSS，转码后）',
    `duration_seconds` INT           DEFAULT NULL COMMENT '视频时长（秒）',
    `is_free`         TINYINT       NOT NULL DEFAULT 0 COMMENT '是否免费试看: 0-否 1-是',
    `sort_order`      INT           NOT NULL DEFAULT 0 COMMENT '排序序号',
    `created_at`      DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    PRIMARY KEY (`id`),
    KEY `idx_chapter_id` (`chapter_id`),
    KEY `idx_sort_order` (`chapter_id`, `sort_order`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='课程课时表';
```

### 3.5 订单表 (order)

```sql
CREATE TABLE `order` (
    `id`           BIGINT         NOT NULL AUTO_INCREMENT COMMENT '订单主键',
    `order_no`     VARCHAR(30)    NOT NULL COMMENT '订单号（业务唯一）',
    `user_id`      BIGINT         NOT NULL COMMENT '下单用户ID',
    `total_amount` DECIMAL(10,2)  NOT NULL COMMENT '订单总金额（元）',
    `discount_amount` DECIMAL(10,2) NOT NULL DEFAULT 0.00 COMMENT '优惠金额（元）',
    `pay_amount`   DECIMAL(10,2)  NOT NULL COMMENT '实付金额（元）',
    `status`       TINYINT        NOT NULL DEFAULT 0 COMMENT '状态: 0-CREATED 1-PAID 2-COMPLETED 3-REFUNDING 4-REFUNDED 5-CANCELLED',
    `pay_type`     VARCHAR(20)    DEFAULT NULL COMMENT '支付方式: WECHAT / ALIPAY',
    `trade_no`     VARCHAR(64)    DEFAULT NULL COMMENT '第三方交易流水号',
    `paid_at`      DATETIME       DEFAULT NULL COMMENT '支付时间',
    `expired_at`   DATETIME       NOT NULL COMMENT '订单过期时间（15分钟后）',
    `created_at`   DATETIME       NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    `updated_at`   DATETIME       NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    PRIMARY KEY (`id`),
    UNIQUE KEY `uk_order_no` (`order_no`),
    KEY `idx_user_id` (`user_id`),
    KEY `idx_status` (`status`),
    KEY `idx_user_status` (`user_id`, `status`),
    KEY `idx_created_at` (`created_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='订单表';
```

### 3.6 学习记录表 (learning_record)

```sql
CREATE TABLE `learning_record` (
    `id`             BIGINT   NOT NULL AUTO_INCREMENT COMMENT '记录主键',
    `user_id`        BIGINT   NOT NULL COMMENT '学员ID',
    `course_id`      BIGINT   NOT NULL COMMENT '课程ID',
    `lesson_id`      BIGINT   NOT NULL COMMENT '课时ID',
    `watch_duration` INT      NOT NULL DEFAULT 0 COMMENT '累计观看时长（秒）',
    `completed`      TINYINT  NOT NULL DEFAULT 0 COMMENT '是否已完课: 0-否 1-是',
    `last_position`  INT      NOT NULL DEFAULT 0 COMMENT '最后播放位置（秒）',
    `created_at`     DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    `updated_at`     DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    PRIMARY KEY (`id`),
    UNIQUE KEY `uk_user_lesson` (`user_id`, `lesson_id`),
    KEY `idx_user_course` (`user_id`, `course_id`),
    KEY `idx_course_id` (`course_id`),
    KEY `idx_completed` (`user_id`, `course_id`, `completed`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='学习记录表';
```

## 4. 索引设计

### 4.1 索引汇总

| 表名 | 索引名 | 索引类型 | 字段 | 说明 |
|------|--------|---------|------|------|
| `user` | `uk_username` | UNIQUE | `username` | 用户名唯一，登录查询 |
| `user` | `uk_phone` | UNIQUE | `phone` | 手机号唯一，短信登录 |
| `user` | `idx_role` | NORMAL | `role` | 按角色筛选用户列表 |
| `user` | `idx_status` | NORMAL | `status` | 按状态筛选（禁用/正常） |
| `course` | `idx_teacher_id` | NORMAL | `teacher_id` | 查询教师名下所有课程 |
| `course` | `idx_category_id` | NORMAL | `category_id` | 按分类筛选课程 |
| `course` | `idx_status` | NORMAL | `status` | 区分上架/下架/草稿 |
| `course` | `idx_created_at` | NORMAL | `created_at` | 最新课程排序 |
| `course` | `idx_title` | NORMAL | `title(50)` 前缀 | 标题模糊搜索（LIKE） |
| `course_chapter` | `idx_course_id` | NORMAL | `course_id` | 查询课程的所有章节 |
| `course_chapter` | `idx_sort_order` | COMPOSITE | `(course_id, sort_order)` | 按序号排列章节 |
| `course_lesson` | `idx_chapter_id` | NORMAL | `chapter_id` | 查询章节的所有课时 |
| `course_lesson` | `idx_sort_order` | COMPOSITE | `(chapter_id, sort_order)` | 按序号排列课时 |
| `order` | `uk_order_no` | UNIQUE | `order_no` | 订单号全局唯一，支付回调 |
| `order` | `idx_user_id` | NORMAL | `user_id` | 查询用户的所有订单 |
| `order` | `idx_user_status` | COMPOSITE | `(user_id, status)` | 按状态筛选用户订单 |
| `order` | `idx_created_at` | NORMAL | `created_at` | 订单时间范围查询 |
| `learning_record` | `uk_user_lesson` | UNIQUE | `(user_id, lesson_id)` | 同一用户同一课时只有一条记录 |
| `learning_record` | `idx_user_course` | COMPOSITE | `(user_id, course_id)` | 查询用户某课程的所有学习记录 |
| `learning_record` | `idx_completed` | COMPOSITE | `(user_id, course_id, completed)` | 统计完课进度 |

### 4.2 索引设计原则

1. **唯一索引**：所有业务唯一标识（username、phone、order_no）必须建立唯一索引，在数据库层面保证数据一致性
2. **联合索引**：多条件查询场景建立联合索引，遵循最左前缀匹配原则
3. **前缀索引**：TEXT/VARCHAR 长文本字段使用前缀索引（如 `title(50)`），减少索引体积
4. **冗余字段**：course 表的 `student_count`、`chapter_count` 为冗余统计字段，通过定时任务或事件驱动更新，避免 COUNT 查询

## 5. 数据字典

### 5.1 user 表

| 字段 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `id` | BIGINT | 是 | 自增 | 主键，雪花算法备用 |
| `username` | VARCHAR(50) | 是 | - | 登录名，4~50 字符，字母数字下划线 |
| `nickname` | VARCHAR(50) | 否 | NULL | 用户昵称，可中文 |
| `phone` | VARCHAR(20) | 否 | NULL | 手机号，11 位中国大陆手机号 |
| `email` | VARCHAR(100) | 否 | NULL | 邮箱地址 |
| `avatar_url` | VARCHAR(500) | 否 | NULL | 头像 OSS 地址 |
| `password` | VARCHAR(255) | 是 | - | BCrypt 加密后的密码，不可逆 |
| `role` | TINYINT | 是 | 0 | 0=学员，1=教师，2=管理员 |
| `status` | TINYINT | 是 | 1 | 0=禁用，1=正常 |

### 5.2 course 表

| 字段 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `id` | BIGINT | 是 | 自增 | 课程主键 |
| `title` | VARCHAR(200) | 是 | - | 课程标题，2~200 字符 |
| `cover_url` | VARCHAR(500) | 否 | NULL | 封面图 OSS 地址 |
| `description` | TEXT | 否 | NULL | 课程详细介绍，支持富文本 |
| `teacher_id` | BIGINT | 是 | - | 关联 user 表 ID（教师） |
| `category_id` | BIGINT | 否 | NULL | 关联分类表 ID |
| `price` | DECIMAL(10,2) | 是 | 0.00 | 售价，精确到分 |
| `original_price` | DECIMAL(10,2) | 否 | NULL | 划线原价 |
| `status` | TINYINT | 是 | 0 | 0=草稿，1=已上架，2=已下架 |
| `student_count` | INT | 是 | 0 | 购买学员数（冗余，事件更新） |
| `rating` | DECIMAL(2,1) | 是 | 5.0 | 综合评分 1.0~5.0 |
| `chapter_count` | INT | 是 | 0 | 章节总数（冗余，事件更新） |

### 5.3 order 表

| 字段 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `id` | BIGINT | 是 | 自增 | 订单主键 |
| `order_no` | VARCHAR(30) | 是 | - | 订单号，格式 OD+时间戳+随机数 |
| `user_id` | BIGINT | 是 | - | 下单用户 ID |
| `total_amount` | DECIMAL(10,2) | 是 | - | 课程总价（优惠前） |
| `discount_amount` | DECIMAL(10,2) | 是 | 0.00 | 优惠券抵扣金额 |
| `pay_amount` | DECIMAL(10,2) | 是 | - | 实际支付金额 |
| `status` | TINYINT | 是 | 0 | 0=CREATED 1=PAID 2=COMPLETED 3=REFUNDING 4=REFUNDED 5=CANCELLED |
| `pay_type` | VARCHAR(20) | 否 | NULL | WECHAT 或 ALIPAY |
| `trade_no` | VARCHAR(64) | 否 | NULL | 第三方支付平台交易号 |
| `paid_at` | DATETIME | 否 | NULL | 实际支付时间 |
| `expired_at` | DATETIME | 是 | - | 订单过期时间（创建时间+15分钟） |

## 6. 命名规范

| 规则 | 示例 |
|------|------|
| 表名：小写下划线 | `course_chapter`, `learning_record` |
| 字段名：小写下划线 | `created_at`, `teacher_id` |
| 主键：统一使用 `id` | `BIGINT AUTO_INCREMENT` |
| 外键：`关联表_id` | `teacher_id`, `course_id` |
| 时间字段：`xxx_at` | `created_at`, `paid_at` |
| 布尔/状态：`is_xxx` / `status` | `is_free`, `status` |
| 索引名：`uk_` 唯一 / `idx_` 普通 | `uk_order_no`, `idx_teacher_id` |

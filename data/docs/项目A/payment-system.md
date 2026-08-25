# Project A — 支付系统设计文档

> 版本：v1.0.0 | 更新日期：2026-07-28 | 涉及组件：微信支付 + 支付宝支付 + RocketMQ 5.0

## 1. 系统概述

支付系统是在线教育平台的核心交易模块，负责课程订单的创建、支付调起、支付回调处理、退款流程以及优惠券核销等业务。系统支持 **微信支付** 和 **支付宝支付** 两种主流支付方式，通过 **RocketMQ 事务消息** 保证订单创建与消息发送的一致性，确保支付成功后正确发放课程权限。

### 1.1 设计目标

| 指标 | 目标 |
|------|------|
| 支付成功率 | > 99.9% |
| 回调处理延迟 | < 500ms |
| 幂等性保证 | 同一回调多次处理结果一致 |
| 订单超时取消 | 15 分钟未支付自动关闭 |
| 退款处理时效 | 1~3 个工作日 |

## 2. 支付流程

```
+--------+    1.创建订单     +--------+    2.计算金额     +----------+
|  学员   | ------------> |  后端   | ------------> | 优惠券服务 |
| (前端)  |              | Spring | <------------ | 满减/折扣 |
+--------+              |  Boot  |    返回优惠金额  +----------+
     |                    +--------+
     |                        |
     |    3.返回订单信息        |
     | <----------------------+
     |
     |    4.选择支付方式，发起支付
     | ----------------------->
     |                    +--------+
     |                    | 后端   |    5.调用支付平台API
     |                    +--------+ -------------------> +--------------+
     |                        |                        | 微信/支付宝   |
     |    6.返回支付凭证        | <---------------------- |              |
     | <----------------------+                        +--------------+
     |
     |    7.调起支付SDK（微信/支付宝）
     | -----------------------> 用户完成支付
     |
     |                    +--------+
     |                    | 微信/  |    8.异步回调通知
     |                    | 支付宝 | -------------------> +--------+
     |                    +--------+                     | 后端   |
     |                                                 | 回调接口|
     |                                                 +--------+
     |                                                     |
     |    9.验证签名，更新订单状态                              |
     |    10.发放课程权限                                     |
     |    11.RocketMQ发送通知消息                              |
```

### 2.1 流程详解

1. **创建订单**：前端提交课程 ID 列表和可选优惠券码
2. **计算金额**：查询课程价格，校验优惠券，计算最终支付金额
3. **返回订单**：返回订单号、支付金额、过期时间
4. **发起支付**：前端选择微信或支付宝，调用支付接口
5. **调起 SDK**：后端返回支付凭证（prepay_id / trade_no），前端调起支付
6. **异步回调**：支付平台向后端回调接口发送支付结果通知
7. **处理回调**：验证签名、更新订单状态、发放课程权限

## 3. 订单状态机

```
                     +-----------+
                     |  CREATED  |  订单创建（15分钟超时）
                     +-----------+
                      /    |     \
                     /     |      \
              用户支付  订单超时   用户取消
               /        |          \
              v         v           v
      +-----------+ +-----------+ +-----------+
      |   PAID    | | CANCELLED | | CANCELLED |
      +-----------+ +-----------+ +-----------+
            |
            v
      +-----------+
      | COMPLETED |  确认收货（自动，支付后即完成）
      +-----------+
            |
            | 用户申请退款
            v
      +-------------+
      | REFUNDING   |
      +-------------+
          /        \
     审核通过      审核拒绝
        /              \
       v                v
 +-----------+    +-----------+
 | REFUNDED  |    | COMPLETED |
 +-----------+    +-----------+
```

### 3.1 状态枚举

| 状态值 | 状态名 | 说明 |
|--------|--------|------|
| 0 | CREATED | 订单已创建，等待支付 |
| 1 | PAID | 已支付，待确认 |
| 2 | COMPLETED | 交易完成（教育场景：支付后自动完成） |
| 3 | REFUNDING | 退款中 |
| 4 | REFUNDED | 已退款 |
| 5 | CANCELLED | 已取消（超时或用户主动取消） |

### 3.2 合法状态流转

```java
// 状态流转校验
private static final Map<OrderStatus, Set<OrderStatus>> ALLOWED_TRANSITIONS = Map.of(
    CREATED,   Set.of(PAID, CANCELLED),
    PAID,      Set.of(COMPLETED, REFUNDING),
    COMPLETED, Set.of(REFUNDING),
    REFUNDING, Set.of(REFUNDED, COMPLETED)
);
```

## 4. 订单号生成规则

格式：`OD` + `yyyyMMddHHmmss` + 6 位随机数

示例：`OD20260715143022123456`

```java
public String generateOrderNo() {
    DateTimeFormatter formatter = DateTimeFormatter.ofPattern("yyyyMMddHHmmss");
    String timestamp = LocalDateTime.now().format(formatter);
    String random = String.format("%06d", new Random().nextInt(1000000));
    return "OD" + timestamp + random;
}
```

设计考量：
- 前缀 `OD` 便于日志和数据库中快速识别订单号类型
- 时间戳精确到秒，保证短时间内的唯一性
- 6 位随机数提供足够的随机空间，碰撞概率极低
- 总长度 22 字符，数据库 `VARCHAR(30)` 存储充足

## 5. 幂等性设计

支付回调接口使用 **order_no + pay_type** 作为幂等键，防止支付平台多次回调导致重复处理。

```java
@PostMapping("/pay/callback/wechat")
public String wechatPayCallback(@RequestBody String body,
                                  @RequestHeader("Wechatpay-Signature") String signature) {
    // 1. 验证签名
    if (!wechatPayService.verifySignature(body, signature)) {
        log.warn("微信支付回调签名验证失败");
        return "FAIL";
    }

    // 2. 解析回调数据
    PaymentCallback callback = wechatPayService.parseCallback(body);
    String idempotentKey = callback.getOrderNo() + ":" + callback.getPayType();

    // 3. 幂等性校验（Redis SETNX）
    Boolean firstTime = redisTemplate.opsForValue()
        .setIfAbsent("pay:callback:" + idempotentKey, "1", 24, TimeUnit.HOURS);
    if (Boolean.FALSE.equals(firstTime)) {
        log.info("重复回调，已处理: {}", idempotentKey);
        return "SUCCESS"; // 返回成功避免支付平台重试
    }

    // 4. 处理业务逻辑
    orderService.processPaymentSuccess(callback.getOrderNo(), callback.getTradeNo());

    return "SUCCESS";
}
```

幂等保障措施：
- Redis `SETNX` 作为分布式锁，24 小时有效期
- 数据库层面 `order_no` + `pay_type` 唯一约束兜底
- 订单状态流转校验，已完成的订单不允许重复更新

## 6. 退款流程

### 6.1 退款规则

| 规则 | 说明 |
|------|------|
| 无理由退款 | 支付后 7 天内可申请无理由退款 |
| 超时退款 | 超过 7 天需提交退款说明，由管理员人工审核 |
| 退款方式 | 原路退回（微信退回微信，支付宝退回支付宝） |
| 退款时效 | 1~3 个工作日（取决于支付平台） |
| 课程权限 | 退款成功后立即撤销课程访问权限 |

### 6.2 退款流程图

```
用户申请退款
    |
    v
+------------------+
| 校验退款资格      | --- 超过7天 ---+
| (7天/已完课比例)   |                 |
+------------------+                 v
    |                              +------------------+
    | 符合条件                     | 提交人工审核       |
    v                              +------------------+
+------------------+                      |
| 自动退款          | <----- 审核通过 -----+
| 调用支付平台退款API |              |
+------------------+              |
    |                              |
    v                              |
+------------------+              |
| 更新订单状态       |              |
| -> REFUNDING      |              |
| -> REFUNDED       |              |
+------------------+              |
    |                              |
    v                              |
+------------------+              |
| 撤销课程权限       |              |
+------------------+
```

## 7. 优惠券系统

### 7.1 优惠券类型

| 类型 | 说明 | 计算规则 |
|------|------|---------|
| 满减券 | 满足金额门槛后减固定金额 | 满 200 减 50，满 500 减 120 |
| 折扣券 | 按折扣比例减免 | 8 折券：实付 = 原价 x 0.8 |
| 兑换码 | 直接兑换免费课程 | 输入兑换码后价格为 0 |

### 7.2 金额计算逻辑

```java
public BigDecimal calculatePayAmount(List<Long> courseIds, String couponCode) {
    // 1. 查询课程总价
    BigDecimal totalAmount = courseMapper.sumPriceByIds(courseIds);

    // 2. 如果有优惠券，计算优惠金额
    BigDecimal discountAmount = BigDecimal.ZERO;
    if (StringUtils.hasText(couponCode)) {
        Coupon coupon = couponService.validateAndGet(couponCode, totalAmount);
        switch (coupon.getType()) {
            case FULL_REDUCTION:
                // 满减券：满 200 减 50
                discountAmount = coupon.getDiscountAmount();
                break;
            case DISCOUNT:
                // 折扣券：8 折
                discountAmount = totalAmount
                    .multiply(BigDecimal.ONE.subtract(coupon.getDiscountRate()));
                break;
            case REDEEM_CODE:
                // 兑换码：全额减免
                discountAmount = totalAmount;
                break;
        }
    }

    // 3. 实付金额 = 总价 - 优惠，最低为 0
    BigDecimal payAmount = totalAmount.subtract(discountAmount);
    payAmount = payAmount.max(BigDecimal.ZERO);
    return payAmount.setScale(2, RoundingMode.HALF_UP);
}
```

### 7.3 优惠券核销

优惠券在订单支付成功时核销，退款时回退：

```java
// 支付成功回调中核销优惠券
@Transactional
public void processPaymentSuccess(String orderNo, String tradeNo) {
    Order order = orderMapper.selectByOrderNo(orderNo);

    // 更新订单状态
    order.setStatus(OrderStatus.PAID);
    order.setTradeNo(tradeNo);
    order.setPaidAt(LocalDateTime.now());
    orderMapper.updateById(order);

    // 核销优惠券
    if (order.getCouponId() != null) {
        couponService.redeem(order.getCouponId(), order.getId());
    }

    // 发放课程权限
    courseService.grantAccess(order.getUserId(), order.getCourseIds());
}

// 退款成功时回退优惠券
@Transactional
public void processRefundSuccess(String orderNo) {
    Order order = orderMapper.selectByOrderNo(orderNo);

    order.setStatus(OrderStatus.REFUNDED);
    orderMapper.updateById(order);

    // 回退优惠券（如果未过期）
    if (order.getCouponId() != null) {
        couponService.unredeem(order.getCouponId());
    }

    // 撤销课程权限
    courseService.revokeAccess(order.getUserId(), order.getCourseIds());
}
```

## 8. RocketMQ 事务消息

### 8.1 事务消息保证一致性

订单创建过程中，需要保证「数据库写入订单」和「发送延迟取消消息」的原子性，使用 RocketMQ 事务消息解决。

```java
// 发送事务消息：创建订单 + 延迟取消消息
public OrderDTO createOrder(CreateOrderRequest request) {
    // 构建订单消息
    OrderTransactionalMessage msg = new OrderTransactionalMessage(
        request.getUserId(), request.getCourseIds(), request.getCouponCode()
    );

    // 发送事务消息（半消息）
    rocketMQTemplate.sendMessageInTransaction(
        "order-tx-topic",
        MessageBuilder.withPayload(msg).build(),
        null  // arg 传给本地事务监听器和回查方法
    );
}

// 本地事务监听器
@RocketMQTransactionListener
public class OrderTransactionListener implements RocketMQLocalTransactionListener {

    @Autowired private OrderService orderService;

    @Override
    public RocketMQLocalTransactionState executeLocalTransaction(Message msg, Object arg) {
        try {
            // 执行本地事务：写数据库
            OrderTransactionalMessage payload = JSON.parseObject(
                new String(msg.getBody()), OrderTransactionalMessage.class
            );
            orderService.doCreateOrder(payload);

            // 本地事务成功，提交消息
            return RocketMQLocalTransactionState.COMMIT;
        } catch (Exception e) {
            log.error("创建订单本地事务失败", e);
            return RocketMQLocalTransactionState.ROLLBACK;
        }
    }

    @Override
    public RocketMQLocalTransactionState checkLocalTransaction(Message msg) {
        // 事务回查：检查订单是否已入库
        OrderTransactionalMessage payload = JSON.parseObject(
            new String(msg.getBody()), OrderTransactionalMessage.class
        );
        Order order = orderService.getByOrderNo(payload.getOrderNo());
        if (order != null) {
            return RocketMQLocalTransactionState.COMMIT;
        }
        return RocketMQLocalTransactionState.UNKNOWN;
    }
}
```

### 8.2 延迟消息实现订单超时取消

订单创建后发送一条延迟 15 分钟的消息，消费者收到后检查订单是否已支付，未支付则自动取消。

```java
// 发送延迟消息（RocketMQ 延迟级别 16 = 15 分钟）
rocketMQTemplate.syncSend(
    "order-delay-topic",
    MessageBuilder.withPayload(orderNo).build(),
    3000, // 发送超时 3 秒
    16    // 延迟级别 16（RocketMQ 预定义：15 分钟）
);

// 延迟消息消费者
@RocketMQMessageListener(
    topic = "order-delay-topic",
    consumerGroup = "order-delay-consumer-group"
)
public class OrderDelayConsumer implements RocketMQListener<String> {

    @Override
    public void onMessage(String orderNo) {
        Order order = orderMapper.selectByOrderNo(orderNo);
        if (order != null && order.getStatus() == OrderStatus.CREATED) {
            order.setStatus(OrderStatus.CANCELLED);
            orderMapper.updateById(order);
            log.info("订单超时自动取消: {}", orderNo);
            // 回退优惠券
            if (order.getCouponId() != null) {
                couponService.unredeem(order.getCouponId());
            }
        }
    }
}
```

## 9. 支付方式配置

### 9.1 微信支付配置

```yaml
# application.yml
payment:
  wechat:
    app-id: wx1234567890abcdef
    mch-id: 1234567890
    api-v3-key: your-api-v3-key-32-characters-long
    private-key-path: classpath:cert/wechat/apiclient_key.pem
    serial-number: YOUR_CERT_SERIAL_NUMBER
    notify-url: https://api.edu-platform.com/api/v1/pay/callback/wechat
    description: 在线教育平台课程购买
```

### 9.2 支付宝配置

```yaml
payment:
  alipay:
    app-id: 2021000000000000
    private-key: your-rsa-private-key
    alipay-public-key: alipay-rsa-public-key
    notify-url: https://api.edu-platform.com/api/v1/pay/callback/alipay
    return-url: https://edu-platform.com/order/success
    sign-type: RSA2
```

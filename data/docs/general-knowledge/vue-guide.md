# Vue.js 技术文档

> **版本**：Vue 3.3+ / Composition API
> **适用场景**：前端单页应用开发、管理后台、跨平台移动端
> **最后更新**：2026-07-28

---

## 1. Vue 简介

Vue.js 是一款用于构建用户界面的渐进式 JavaScript 框架，由尤雨溪（Evan You）创建并于 2014 年首次发布。与其他框架不同，Vue 被设计为可以自底向上逐层应用——核心库只关注视图层，既能作为轻量库直接引入页面，也能配合生态库构建复杂的单页应用（SPA）。

### 1.1 核心特点

| 特性 | 说明 |
|------|------|
| **响应式数据绑定** | 数据变化自动更新视图，无需手动操作 DOM |
| **组件化开发** | 将 UI 拆分为可复用的独立组件，提升可维护性 |
| **虚拟 DOM** | 通过 Diff 算法最小化真实 DOM 操作，提升渲染性能 |
| **渐进式架构** | 核心库轻量（~34KB gzip），可按需引入路由、状态管理等插件 |
| **单文件组件（SFC）** | `.vue` 文件将模板、逻辑、样式封装在一起 |
| **Composition API** | Vue 3 引入，以函数方式组织逻辑，替代 Options API 的 `data/methods/computed` |
| **TypeScript 支持** | Vue 3 用 TypeScript 重写，原生支持类型推导与校验 |

### 1.2 Vue 2 vs Vue 3 对比

| 维度 | Vue 2 | Vue 3 |
|------|-------|-------|
| 响应式实现 | `Object.defineProperty` | `Proxy`（支持数组、新增/删除属性） |
| API 风格 | Options API（data/methods/computed） | Composition API + Options API |
| 生命周期 | `beforeCreate/created` 等 | `onMounted/onUpdated` 等函数式钩子 |
| 性能 | 虚拟 DOM 全量对比 | 静态提升、PatchFlag 优化 |
| 体积 | ~30KB gzip | ~34KB gzip（功能更多但 Tree-shaking 后更小） |
| TypeScript | 需 `vue-class-component` 装饰器 | 原生支持 |

### 1.3 Vue 生态系统

| 库 | 作用 | 版本 |
|----|------|------|
| Vue Router | 官方路由管理器 | 4.x |
| Pinia | 官方状态管理（替代 Vuex） | 2.x |
| Vue DevTools | 浏览器调试插件 | 6.x |
| Vite | 官方推荐构建工具（替代 Webpack） | 5.x |
| Vue CLI | 旧版脚手架工具（已不推荐） | 5.x |
| Element Plus | 桌面端 UI 组件库 | 2.4 |
| Vant | 移动端 UI 组件库 | 4.x |
| Nuxt 3 | 基于 Vue 的 SSR 框架 | 3.x |

---

## 2. 快速开始

### 2.1 创建项目（Vite）

```bash
# 创建 Vue3 + TypeScript 项目
npm create vite@latest my-app -- --template vue-ts

# 进入项目
cd my-app
npm install

# 启动开发服务器（默认 http://localhost:5173）
npm run dev

# 构建生产版本
npm run build
```

### 2.2 单文件组件（SFC）结构

```vue
<template>
  <!-- HTML 模板 -->
  <div class="counter">
    <h1>{{ title }}</h1>
    <p>当前计数：{{ count }}</p>
    <button @click="increment">+1</button>
  </div>
</template>

<script setup lang="ts">
// 逻辑代码（Composition API + TypeScript）
import { ref, computed } from 'vue'

const title = ref<string>('计数器')
const count = ref<number>(0)

const double = computed(() => count.value * 2)

function increment() {
  count.value++
}
</script>

<style scoped>
/* 仅作用于当前组件的样式 */
.counter {
  padding: 20px;
  text-align: center;
}
</style>
```

---

## 3. Composition API 核心概念

### 3.1 响应式数据

Vue 3 提供三种创建响应式数据的 API：

```typescript
import { ref, reactive, shallowRef } from 'vue'

// ref：适用于基本类型，通过 .value 访问
const count = ref<number>(0)
count.value++

// reactive：适用于对象/数组，直接访问属性（无需 .value）
const user = reactive({
  name: '张三',
  age: 25,
  courses: [] as string[]
})
user.name = '李四'
user.courses.push('Vue3 入门')

// shallowRef：浅响应（只对 .value 本身响应，内部属性变化不触发更新）
const list = shallowRef<number[]>([1, 2, 3])
list.value = [4, 5, 6]  // 触发更新
list.value.push(7)       // 不触发更新（需重新赋值）
```

**ref vs reactive 选择建议**：
- 基本类型（string/number/boolean）：用 `ref`
- 对象/数组：用 `reactive`
- 需要整体替换引用：用 `ref`（`reactive` 不支持整体替换）

### 3.2 计算属性（computed）

```typescript
import { ref, computed } from 'vue'

const price = ref(99)
const quantity = ref(2)

// 只读计算属性
const totalPrice = computed(() => price.value * quantity.value)

// 可写计算属性
const fullName = computed({
  get: () => `${firstName.value} ${lastName.value}`,
  set: (val: string) => {
    [firstName.value, lastName.value] = val.split(' ')
  }
})
```

### 3.3 侦听器（watch / watchEffect）

```typescript
import { ref, watch, watchEffect } from 'vue'

const keyword = ref('')

// watch：明确指定侦听源，可获取新旧值，默认懒执行
watch(keyword, (newVal, oldVal) => {
  console.log(`搜索词从 ${oldVal} 变为 ${newVal}`)
}, { immediate: true })  // immediate: 立即执行一次

// watchEffect：自动收集依赖，立即执行，无法获取旧值
watchEffect(() => {
  console.log(`当前搜索词: ${keyword.value}`)
})

// 侦听多个源
watch([firstName, lastName], ([newFirst, newLast]) => {
  console.log(`姓名变更为: ${newFirst} ${newLast}`)
})

// 深度侦听对象
watch(user, (newUser) => {
  console.log('用户信息变更', newUser)
}, { deep: true })
```

### 3.4 生命周期钩子

```typescript
import { onMounted, onUpdated, onUnmounted } from 'vue'

// 组件挂载后（DOM 已渲染）
onMounted(() => {
  console.log('组件已挂载')
  // 适合：发起 API 请求、初始化第三方库、操作 DOM
})

// 组件更新后
onUpdated(() => {
  console.log('组件已更新')
})

// 组件卸载前（清理副作用）
onUnmounted(() => {
  console.log('组件即将卸载')
  // 适合：清除定时器、移除事件监听、取消未完成的请求
})
```

**Vue 2 vs Vue 3 生命周期对照**：

| Vue 2 | Vue 3 (setup) | 说明 |
|-------|---------------|------|
| beforeCreate | （setup 本身） | 组件实例创建前 |
| created | （setup 本身） | 组件实例创建后 |
| beforeMount | onBeforeMount | 挂载到 DOM 前 |
| mounted | onMounted | 挂载到 DOM 后 |
| beforeUpdate | onBeforeUpdate | 数据变更前 |
| updated | onUpdated | 数据变更后 |
| beforeDestroy | onBeforeUnmount | 组件销毁前 |
| destroyed | onUnmounted | 组件销毁后 |

---

## 4. 组件通信

### 4.1 Props（父传子）

```vue
<!-- 父组件 -->
<template>
  <CourseCard :course="courseData" :show-price="true" />
</template>

<!-- 子组件 CourseCard.vue -->
<script setup lang="ts">
interface Course {
  id: number
  title: string
  price: number
}

// 定义 Props
const props = defineProps<{
  course: Course
  showPrice?: boolean  // 可选属性
}>()

// 带默认值
const props2 = withDefaults(defineProps<{
  showPrice?: boolean
}>(), {
  showPrice: true
})
</script>
```

### 4.2 Emits（子传父）

```vue
<!-- 子组件 -->
<script setup lang="ts">
// 定义事件
const emit = defineEmits<{
  (e: 'addToCart', courseId: number): void
  (e: 'close'): void
}>()

function handleAdd() {
  emit('addToCart', 123)
}
</script>

<!-- 父组件 -->
<template>
  <CourseCard @add-to-cart="handleAddToCart" @close="handleClose" />
</template>
```

### 4.3 v-model（双向绑定）

```vue
<!-- 父组件 -->
<template>
  <SearchBar v-model="keyword" />
  <!-- 等价于 -->
  <SearchBar :model-value="keyword" @update:model-value="keyword = $event" />
</template>

<!-- 子组件 SearchBar.vue -->
<script setup lang="ts">
const props = defineProps<{ modelValue: string }>()
const emit = defineEmits<{ (e: 'update:modelValue', val: string): void }>()

function onInput(e: Event) {
  emit('update:modelValue', (e.target as HTMLInputElement).value)
}
</script>
```

### 4.4 Provide / Inject（跨层级传递）

```typescript
// 祖先组件
import { provide, ref } from 'vue'

const theme = ref('dark')
provide('theme', theme)  // 提供数据

// 后代组件（任意层级）
import { inject } from 'vue'

const theme = inject('theme', 'light')  // 第二个参数为默认值
```

---

## 5. Vue Router 路由

### 5.1 路由配置

```typescript
// router/index.ts
import { createRouter, createWebHistory } from 'vue-router'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', redirect: '/dashboard' },
    { path: '/login', component: () => import('@/views/Login.vue') },
    {
      path: '/dashboard',
      component: () => import('@/views/Dashboard.vue'),
      meta: { requiresAuth: true, title: '首页' }
    },
    {
      path: '/courses/:id',
      component: () => import('@/views/CourseDetail.vue'),
      props: true  // 将路由参数作为 props 传给组件
    }
  ]
})

// 全局前置守卫
router.beforeEach((to, from, next) => {
  const token = localStorage.getItem('token')
  if (to.meta.requiresAuth && !token) {
    next('/login')
  } else {
    next()
  }
})

export default router
```

### 5.2 编程式导航

```typescript
import { useRouter, useRoute } from 'vue-router'

const router = useRouter()
const route = useRoute()

// 跳转
router.push('/courses/123')
router.push({ path: '/courses', query: { category: 'frontend' } })
router.push({ name: 'CourseDetail', params: { id: 123 } })

// 替换（不留历史记录）
router.replace('/login')

// 后退
router.back()

// 获取当前路由参数
console.log(route.params.id)
console.log(route.query.category)
```

---

## 6. Pinia 状态管理

### 6.1 定义 Store

```typescript
// stores/user.ts
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

export const useUserStore = defineStore('user', () => {
  // state
  const token = ref<string>('')
  const userInfo = ref<UserInfo | null>(null)

  // getters
  const isLoggedIn = computed(() => !!token.value)
  const username = computed(() => userInfo.value?.nickname || '未登录')

  // actions
  function setToken(newToken: string) {
    token.value = newToken
    localStorage.setItem('token', newToken)
  }

  function logout() {
    token.value = ''
    userInfo.value = null
    localStorage.removeItem('token')
  }

  return { token, userInfo, isLoggedIn, username, setToken, logout }
})
```

### 6.2 在组件中使用

```vue
<script setup lang="ts">
import { useUserStore } from '@/stores/user'
import { storeToRefs } from 'pinia'

const userStore = useUserStore()

// 解构需要响应式的数据（必须用 storeToRefs）
const { isLoggedIn, username } = storeToRefs(userStore)

// actions 可以直接解构
const { logout } = userStore
</script>
```

---

## 7. 常用指令

| 指令 | 说明 | 示例 |
|------|------|------|
| `v-if` / `v-else` | 条件渲染（不渲染到 DOM） | `<div v-if="show">显示</div>` |
| `v-show` | 条件显示（CSS display 控制） | `<div v-show="visible">显示</div>` |
| `v-for` | 列表渲染（必须加 key） | `<li v-for="item in list" :key="item.id">` |
| `v-bind` / `:` | 绑定属性 | `<img :src="imageUrl">` |
| `v-on` / `@` | 绑定事件 | `<button @click="handleClick">` |
| `v-model` | 双向数据绑定 | `<input v-model="text">` |
| `v-text` | 设置文本内容 | `<span v-text="message">` |
| `v-html` | 设置 HTML 内容（注意 XSS） | `<div v-html="htmlContent">` |
| `v-if` vs `v-show` | 频繁切换用 v-show，少变用 v-if | - |

---

## 8. 性能优化建议

### 8.1 按需加载

```typescript
// 路由懒加载（默认已支持）
{ path: '/courses', component: () => import('@/views/Courses.vue') }

// 异步组件
const AsyncComp = defineAsyncComponent(() => import('./HeavyComp.vue'))
```

### 8.2 v-for 优化

```vue
<!-- 正确：使用唯一 id 作为 key -->
<li v-for="item in list" :key="item.id">{{ item.name }}</li>

<!-- 错误：不要用 index 作为 key（数据变化时可能导致渲染异常） -->
<li v-for="(item, index) in list" :key="index">{{ item.name }}</li>
```

### 8.3 计算属性缓存

```typescript
// 推荐：使用 computed 缓存计算结果
const filteredList = computed(() =>
  list.value.filter(item => item.price > 100)
)

// 不推荐：在模板中写复杂逻辑（每次渲染都会重新计算）
// <div v-for="item in list.filter(i => i.price > 100)">
```

### 8.4 v-once / v-memo

```vue
<!-- v-once：只渲染一次，后续更新不重新渲染 -->
<h1 v-once>{{ websiteTitle }}</h1>

<!-- v-memo：依赖不变时跳过更新 -->
<div v-memo="[item.id, item.selected]">
  <!-- 大量内容 -->
</div>
```

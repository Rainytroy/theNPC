# 世界之书Store重构文档

## 📋 重构目标

将 `genesis.ts` 中的世界之书相关逻辑抽离到独立的 `world.ts` store，实现职责分离，提高代码可维护性。

## ✅ 已完成 (阶段1-3)

### 1. 创建独立的 WorldStore

**文件**: `theNPC/frontend/src/stores/genesis/world.ts`

**包含的状态**:
- `worldBible` - 草稿状态的世界之书
- `finalizedWorldBible` - 定稿后的世界之书
- `isLocked` - 世界锁定状态
- `worldConfirmed` - 世界设定确认标志
- `isReady` - Agent建议可确认标志

**包含的方法**:
- `updateWorldTitle()` - 更新世界标题
- `confirmWorld()` - 确认世界之书定稿（核心逻辑）
- `editWorld()` - 返回草稿模式
- `updateWorldBible()` - 更新草稿内容
- `setReady()` - 设置确认建议状态
- `refreshFromBackend()` - 从后端刷新数据
- `reset()` - 重置所有状态

### 2. 建立兼容转发层

**在 `genesis.ts` 中的修改**:

```typescript
// 1. Import worldStore
import { useWorldStore } from './genesis/world';

// 2. 转发 updateWorldTitle
async updateWorldTitle(title: string) {
    const worldStore = useWorldStore();
    await worldStore.updateWorldTitle(title);
    // 同步本地状态（兼容性）
    if (this.worldBible) this.worldBible.title = title;
    if (this.finalizedWorldBible) this.finalizedWorldBible.title = title;
}

// 3. 在 sendMessage 中同步状态
if (data.suggested_world_setting) {
    this.worldBible = data.suggested_world_setting;
    // ✨ 同步到 worldStore
    const worldStore = useWorldStore();
    worldStore.updateWorldBible(data.suggested_world_setting);
}

if (data.is_ready_to_generate && data.suggested_world_setting) {
    this.isReady = true;
    // ✨ 同步到 worldStore
    const worldStore = useWorldStore();
    worldStore.setReady(true);
}
```

### 3. 组件迁移 (已完成)

**`WorldBibleCard.vue`**:
- 已完全迁移至使用 `useWorldStore`。
- 直接调用 `worldStore.updateWorldTitle` 和 `worldStore.confirmWorld`。
- 保留 `useGenesisStore` 仅用于获取 `isLoading`, `sessionId`, `messages` 等上下文信息。

**`GenesisView.vue`**:
- 已迁移 `finalizedWorldBible` 的检查逻辑，使用 `worldStore.finalizedWorldBible`。
- 确保侧边栏刷新等副作用监听的是正确的数据源。

**`NPCList.vue`**:
- 已迁移 `finalizedWorldBible` 的引用，确保在生成 NPC 时使用的是 `worldStore` 中的最新定稿数据。

## 🎯 当前架构

### 职责分离

**WorldStore (world.ts)** - 业务逻辑层
- 负责世界之书的状态管理
- 负责调用后端API
- 负责数据验证和转换

**GenesisStore (genesis.ts)** - UI协调层  
- 负责UI加载状态管理
- 负责聊天消息流程
- 负责阶段切换逻辑
- 调用 WorldStore 的方法

### 数据流

```
用户操作 (WorldBibleCard)
    ↓
WorldStore.confirmWorld() → Backend API
    ↓
GenesisStore (手动同步 currentStep)
    ↓
UI 更新
```

## 🔄 待完成 (阶段4)

### 阶段4: 完整测试

**测试清单**:
- [ ] 创建新世界 - 对话生成世界设定
- [ ] 查看世界之书卡片 - 数据正确显示
- [ ] 编辑世界标题 - 标题更新成功
- [ ] 确认世界定稿（对话按钮） - 状态正确切换
- [ ] 确认世界定稿（卡片按钮） - 状态正确切换
- [ ] 刷新页面 - 状态正确恢复
- [ ] 进入NPC阶段 - 步骤正确前进

## ⚠️ 注意事项

### 1. 状态同步

当前采用**双向同步**策略：
- worldStore 是数据源头
- genesis store 保留副本用于兼容性
- 每次更新都同步两边

### 2. Loading状态

`isLoading` 状态仍在 genesis store 中，因为：
- UI加载状态是表现层逻辑
- 多个操作共享同一个loading状态
- 避免多个store的loading状态冲突

### 3. 消息流程

聊天消息（`messages`）仍在 genesis store 中，因为：
- 消息涉及多个阶段（world/npc/quest）
- 消息流程包含复杂的按钮选项
- 世界之书只是消息流程的一部分

## 📈 预期收益

### 短期收益
1. **代码更清晰** - 世界之书逻辑独立，易于理解
2. **易于测试** - 可以单独测试 worldStore
3. **降低耦合** - 世界之书逻辑与其他逻辑分离

### 长期收益
1. **可复用** - worldStore 可被其他组件直接使用
2. **易扩展** - 添加新功能时不影响其他模块
3. **好维护** - 修改世界之书逻辑时范围明确

## 🔍 技术债务

### 当前存在的问题
1. **状态冗余** - genesis store 和 world store 都有 worldBible 副本
2. **责任模糊** - confirmWorld 的逻辑分散在两个 store
3. **向后兼容** - 保留了转发层增加了代码复杂度

### 未来优化方向
1. 逐步移除 genesis store 中的 worldBible 副本
2. 明确 confirmWorld 的职责边界
3. 移除转发层，直接使用 worldStore

## 📝 开发日志

### 2025-12-15
- ✅ 创建独立的 world.ts store
- ✅ 实现核心状态和方法
- ✅ 在 genesis.ts 中建立转发层
- ✅ 同步 sendMessage 中的状态更新
- ✅ 迁移 WorldBibleCard.vue 使用 worldStore
- ✅ 迁移 GenesisView.vue 使用 worldStore
- ✅ 迁移 NPCList.vue 使用 worldStore

## 🚀 下一步行动

1. **立即**: 测试当前功能是否正常（World阶段完整流程）
2. **中期**: 考虑是否抽离 NPC 和 Quest 相关逻辑
3. **长期**: 评估是否需要进一步拆分 genesis store

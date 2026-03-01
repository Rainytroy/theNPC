<script setup lang="ts">
import { ref } from 'vue';
import { MessageSquare, X, Search, User, ChevronRight } from 'lucide-vue-next';

/**
 * QuestChips - 任务触发/对话流的交互选项组件
 * 
 * 用于显示：
 * 1. 任务触发时的 Accept/Reject 选项（LLM 动态生成文案）
 * 2. 对话流中的 Player Line（预设对话）
 * 3. 调查模式的 Investigate/Ignore 选项
 */

export interface QuestChip {
  type: 'accept' | 'reject' | 'investigate' | 'ignore' | 'player_line';
  label: string;
  quest_id?: string;
  node_id?: string;
  npc_id?: string;
  line_index?: number;
  action?: {
    type: 'show_item' | 'give_item';
    item_id: string;
    item_name?: string;
  };
}

const props = defineProps<{
  chips: QuestChip[];
  npcId?: string;
  npcName?: string;
  isLoading?: boolean;
}>();

const emit = defineEmits<{
  (e: 'chip-click', chip: QuestChip): void;
}>();

const isClicked = ref(false);

const getChipIcon = (type: string) => {
  switch (type) {
    case 'accept': return MessageSquare;
    case 'reject': return X;
    case 'investigate': return Search;
    case 'ignore': return X;
    case 'player_line': return User;
    default: return MessageSquare;
  }
};

const getActionHint = (action: QuestChip['action']) => {
  if (!action) return '';
  const actionType = action.type === 'show_item' ? '展示' : '交给对方';
  const itemName = action.item_name || action.item_id;
  return `${actionType} ${itemName}`;
};

const handleChipClick = (chip: QuestChip) => {
  if (isClicked.value || props.isLoading) return;
  
  isClicked.value = true;
  
  // 添加 npc_id 到 chip 数据
  const chipData = {
    ...chip,
    npc_id: chip.npc_id || props.npcId
  };
  
  emit('chip-click', chipData);
  
  // 防止重复点击，但不影响后续的 chips 显示
  setTimeout(() => {
    isClicked.value = false;
  }, 1000);
};
</script>

<template>
  <div 
    v-if="chips && chips.length > 0" 
    class="quest-chips-container"
  >
    <!-- 标题提示 -->
    <div class="chips-header">
      <ChevronRight class="w-3 h-3 text-[#d946ef]" />
      <span v-if="npcName">选择你的回应</span>
      <span v-else>选择你的行动</span>
    </div>
    
    <!-- Chips 列表 -->
    <div class="chips-list">
      <button
        v-for="(chip, index) in chips"
        :key="index"
        :class="[
          'quest-chip',
          `chip-${chip.type}`,
          { 'chip-disabled': isLoading || isClicked }
        ]"
        :disabled="isLoading || isClicked"
        @click="handleChipClick(chip)"
      >
        <!-- 图标 -->
        <component :is="getChipIcon(chip.type)" class="chip-icon" />
        
        <!-- 文案 -->
        <span class="chip-label">{{ chip.label }}</span>
        
        <!-- 物品操作提示 -->
        <span v-if="chip.action" class="chip-action-hint">
          [{{ getActionHint(chip.action) }}]
        </span>
      </button>
    </div>
  </div>
</template>

<style scoped>
.quest-chips-container {
  margin-top: 12px;
  padding: 12px;
  background: linear-gradient(135deg, rgba(217, 70, 239, 0.05), rgba(0, 0, 0, 0.3));
  border: 1px solid rgba(217, 70, 239, 0.2);
  border-radius: 12px;
  animation: slideIn 0.3s ease-out;
}

@keyframes slideIn {
  from {
    opacity: 0;
    transform: translateY(10px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.chips-header {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 10px;
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.1em;
  color: #a1a1aa;
}

.chips-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.quest-chip {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 12px 16px;
  border-radius: 10px;
  cursor: pointer;
  transition: all 0.2s ease;
  border: 1px solid transparent;
  text-align: left;
  font-size: 14px;
  line-height: 1.4;
}

.quest-chip:hover:not(.chip-disabled) {
  transform: translateX(4px);
}

.chip-icon {
  width: 18px;
  height: 18px;
  flex-shrink: 0;
}

.chip-label {
  flex: 1;
}

.chip-action-hint {
  font-size: 11px;
  opacity: 0.7;
  white-space: nowrap;
}

/* Accept Chip - 金色主题 */
.chip-accept {
  background: linear-gradient(135deg, rgba(255, 215, 0, 0.15), rgba(255, 165, 0, 0.1));
  border-color: rgba(255, 215, 0, 0.3);
  color: #ffd700;
}

.chip-accept:hover:not(.chip-disabled) {
  background: linear-gradient(135deg, rgba(255, 215, 0, 0.25), rgba(255, 165, 0, 0.15));
  border-color: rgba(255, 215, 0, 0.5);
  box-shadow: 0 4px 20px rgba(255, 215, 0, 0.2);
}

/* Player Line Chip - 紫色主题（对话流） */
.chip-player_line {
  background: linear-gradient(135deg, rgba(217, 70, 239, 0.15), rgba(168, 85, 247, 0.1));
  border-color: rgba(217, 70, 239, 0.3);
  color: #d946ef;
}

.chip-player_line:hover:not(.chip-disabled) {
  background: linear-gradient(135deg, rgba(217, 70, 239, 0.25), rgba(168, 85, 247, 0.15));
  border-color: rgba(217, 70, 239, 0.5);
  box-shadow: 0 4px 20px rgba(217, 70, 239, 0.2);
}

/* Investigate Chip - 蓝色主题 */
.chip-investigate {
  background: linear-gradient(135deg, rgba(74, 144, 217, 0.15), rgba(110, 181, 255, 0.1));
  border-color: rgba(74, 144, 217, 0.3);
  color: #6eb5ff;
}

.chip-investigate:hover:not(.chip-disabled) {
  background: linear-gradient(135deg, rgba(74, 144, 217, 0.25), rgba(110, 181, 255, 0.15));
  border-color: rgba(74, 144, 217, 0.5);
  box-shadow: 0 4px 20px rgba(74, 144, 217, 0.2);
}

/* Reject / Ignore Chip - 灰色主题 */
.chip-reject,
.chip-ignore {
  background: rgba(82, 82, 91, 0.3);
  border-color: rgba(82, 82, 91, 0.5);
  color: #a1a1aa;
}

.chip-reject:hover:not(.chip-disabled),
.chip-ignore:hover:not(.chip-disabled) {
  background: rgba(82, 82, 91, 0.5);
  border-color: rgba(113, 113, 122, 0.5);
}

/* Disabled State */
.chip-disabled {
  opacity: 0.5;
  cursor: not-allowed;
  transform: none !important;
}
</style>

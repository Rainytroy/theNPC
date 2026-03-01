<script setup lang="ts">
import { Users, BookOpen, Eye } from 'lucide-vue-next';

interface Tab {
  id: string;
  icon: any;
  label: string;
}

defineProps<{
  activeTab: string;
}>();

defineEmits<{
  'change-view': [tabId: string];
}>();

// 当前只有一个tab，预留扩展结构
const tabs: Tab[] = [
  { id: 'residents', icon: Users, label: '居民' },
  { id: 'manga', icon: BookOpen, label: '漫画书' },
  { id: 'godmode', icon: Eye, label: '观察' }
];
</script>

<template>
  <div class="flex flex-col gap-3 p-4 bg-zinc-900/50 rounded-xl border border-zinc-800 backdrop-blur-sm w-24 flex-shrink-0">
    <button 
      v-for="tab in tabs"
      :key="tab.id"
      @click="$emit('change-view', tab.id)"
      :class="{ 'active': activeTab === tab.id }"
      class="sidebar-button"
      :title="tab.label"
    >
      <component :is="tab.icon" class="w-6 h-6" />
      <span class="text-xs font-bold mt-1">{{ tab.label }}</span>
    </button>
    
    <!-- 预留：未来扩展按钮位置 -->
    <!-- 
    <button class="sidebar-button" disabled>
      <Target class="w-6 h-6" />
      <span class="text-xs font-bold mt-1">目标</span>
    </button>
    -->
  </div>
</template>

<style scoped>
.sidebar-button {
  @apply flex flex-col items-center justify-center;
  @apply w-16 h-16 rounded-xl;
  @apply border border-zinc-800;
  @apply bg-zinc-900;
  @apply text-zinc-500;
  @apply transition-all duration-200;
  @apply hover:border-zinc-600 hover:text-zinc-300;
  @apply cursor-pointer;
}

.sidebar-button.active {
  @apply border-[#d946ef] bg-[#d946ef]/10;
  @apply text-[#d946ef];
  @apply shadow-[0_0_10px_rgba(217,70,239,0.2)];
}

.sidebar-button:disabled {
  @apply opacity-40 cursor-not-allowed;
  @apply hover:border-zinc-800 hover:text-zinc-500;
}
</style>

<script setup lang="ts">
import { ref, onMounted, computed } from 'vue';
import worldApi, { WorldMeta } from '../api/world';
import { useGenesisStore } from '../stores/genesis';
import { useWorldStore } from '../stores/genesis/world';
import { useNpcStore } from '../stores/genesis/npc';
import { useQuestStore } from '../stores/genesis/quest';
import { useUIStore } from '../stores/ui';
import { Globe, RefreshCw, Plus, Trash2, Users } from 'lucide-vue-next';

const store = useGenesisStore();
const worldStore = useWorldStore();
const npcStore = useNpcStore();
const questStore = useQuestStore();
const uiStore = useUIStore();
const worlds = ref<WorldMeta[]>([]);
const isLoading = ref(false);

const currentWorldId = computed(() => store.finalizedWorldBible?.world_id);

const fetchWorlds = async () => {
  isLoading.value = true;
  try {
    const data = await worldApi.listWorlds();
    worlds.value = data.worlds;
  } catch (e) {
    console.error('Failed to load worlds', e);
  } finally {
    isLoading.value = false;
  }
};

const handleLoad = async (worldId: string) => {
  const confirmed = await uiStore.openModal(
    '加载存档',
    '确认加载此存档？当前未保存的对话将丢失。',
    'confirm'
  );
  
  if (confirmed) {
    // Force reset step to ensure change detection works even if we reload same phase
    store.currentStep = 'world';

    isLoading.value = true;
    try {
      const data = await worldApi.loadWorld(worldId);
      
      // Update Store
      await store.initSession(true); // Start session silently to fix chat bug
      npcStore.setNpcs(data.npcs);
      
      // Update Quest Store (Directly, as GenesisStore getters are read-only)
      questStore.setQuests(data.quests || []);
      questStore.setItems(data.items || []);
      questStore.setLocations(data.locations || []);
      questStore.setTimeConfig(data.time_config || null);
      questStore.setSchedules(data.schedules || {});
      
      // Update World Store (GenesisStore will proxy these values)
      worldStore.updateWorldBible(data.world_bible);
      worldStore.finalizedWorldBible = data.world_bible;
      worldStore.isLocked = data.is_locked || false;
      worldStore.worldConfirmed = data.config?.world_confirmed || false;
      worldStore.isReady = true;
      if (data.config) {
          worldStore.updateConfig(data.config);
      }

      if (data.chat_history && data.chat_history.length > 0) {
        store.messages = data.chat_history;
      } else {
        store.messages = [];
      }

      // Auto-determine Step (Match logic with genesis.ts refreshWorld)
      let nextStep: 'world' | 'npc' | 'quest' | 'launch' = 'world';
      
      // Robust Config Check: Check both explicit config and raw bible config
      const rawConfig = (data.world_bible as any)?.config || {};
      const apiConfig = data.config || {};
      
      const isRosterConfirmed = (apiConfig.roster_confirmed === true) || (rawConfig.roster_confirmed === true);
      const isQuestConfirmed = (apiConfig.quest_confirmed === true) || (rawConfig.quest_confirmed === true);
      
      if (store.finalizedWorldBible) {
          nextStep = 'npc';
          if (isRosterConfirmed) {
              nextStep = 'quest';
              if (isQuestConfirmed || store.isLocked) {
                  nextStep = 'launch';
              }
          }
      }
      store.currentStep = nextStep;
      
      console.log('[WorldSidebar] Load complete, determined step:', nextStep, {
          isRosterConfirmed,
          isQuestConfirmed,
          isLocked: store.isLocked
      });
      
    } finally {
      isLoading.value = false;
    }
  }
};

const handleDelete = async (worldId: string) => {
  const confirmed = await uiStore.openModal(
    '删除存档',
    '确定要删除这个世界吗？此操作不可恢复。',
    'alert'
  );

  if (confirmed) {
    await worldApi.deleteWorld(worldId);
    
    // Check if deleted world is currently selected
    if (currentWorldId.value === worldId) {
        store.$reset();
        worldStore.reset();
        store.initSession();
    }

    await fetchWorlds();
  }
};

const handleNewWorld = async () => {
  const confirmed = await uiStore.openModal(
    '新建世界',
    '确定要开始新的创世之旅吗？当前进度将被重置。',
    'confirm'
  );

  if (confirmed) {
    // Explicitly clear messages (to handle cases where store was manually set)
    store.messages = [];
    
    // Reset Store
    store.$reset();
    worldStore.reset();
    npcStore.reset();
    await store.initSession();
  }
};

onMounted(() => {
  fetchWorlds();
});

defineExpose({ refresh: fetchWorlds });
</script>

<template>
  <div class="h-full flex flex-col bg-zinc-950 text-zinc-300 border-r border-zinc-800 w-[300px] flex-shrink-0 transition-all">
    <!-- Header -->
    <div class="p-4 border-b border-zinc-800 flex justify-between items-center">
      <h2 class="font-bold text-[#ccff00] tracking-wide">
        我的世界 MY WORLDS
      </h2>
      <button 
        @click="fetchWorlds" 
        class="text-[#ccff00] hover:text-[#b3e600] transition-colors"
        title="刷新列表"
      >
        <RefreshCw class="w-4 h-4" :class="{ 'animate-spin': isLoading }" />
      </button>
    </div>

    <!-- New World Button -->
    <div class="p-4">
      <button 
        @click="handleNewWorld"
        class="w-full bg-[#ccff00] hover:bg-[#b3e600] text-black font-extrabold py-3 px-3 rounded-lg flex items-center justify-center gap-2 transition-all shadow-[0_0_10px_rgba(204,255,0,0.3)] hover:shadow-[0_0_15px_rgba(204,255,0,0.5)] group"
      >
        <Plus class="w-5 h-5 text-black stroke-[3px]" />
        <span class="tracking-wide">新建世界</span>
      </button>
    </div>

    <!-- List -->
    <div class="flex-1 overflow-y-auto px-4 py-4 space-y-4 custom-scrollbar">
      <div v-if="isLoading && worlds.length === 0" class="text-center py-4 text-sm text-zinc-500">
        加载中...
      </div>
      
      <div v-else-if="worlds.length === 0" class="text-center py-8 text-sm text-zinc-500">
        暂无存档
      </div>

      <div 
        v-for="world in worlds" 
        :key="world.world_id"
        class="group relative rounded-lg p-3 cursor-pointer transition-all duration-300 border"
        :class="currentWorldId === world.world_id 
          ? 'bg-zinc-800 border-[#ccff00]' 
          : 'bg-zinc-900 border-transparent hover:bg-zinc-800 hover:border-[#ccff00]'"
        @click="handleLoad(world.world_id)"
      >
        <div class="flex justify-between items-start">
          <h3 class="font-bold text-zinc-200 group-hover:text-[#ccff00] truncate pr-6 transition-colors">{{ world.title || world.name }}</h3>
          <button 
            @click.stop="handleDelete(world.world_id)"
            class="absolute top-3 right-3 text-zinc-600 hover:text-red-400 opacity-0 group-hover:opacity-100 transition-opacity"
            title="删除"
          >
            <Trash2 class="w-4 h-4" />
          </button>
        </div>
        <p class="text-xs text-zinc-500 mt-1">{{ world.era }}</p>
        <p class="text-xs text-zinc-600 mt-2 flex justify-between items-center">
          <span class="flex items-center gap-1">
            <Users class="w-3 h-3" />
            {{ world.npc_count }}
          </span>
          <span>{{ new Date(world.created_at).toLocaleDateString() }}</span>
        </p>
      </div>
    </div>
  </div>
</template>

<style scoped>
.custom-scrollbar::-webkit-scrollbar {
  width: 6px;
}

.custom-scrollbar::-webkit-scrollbar-track {
  background: transparent;
}

.custom-scrollbar::-webkit-scrollbar-thumb {
  background-color: #3f3f46; /* zinc-700 */
  border-radius: 3px;
}

.custom-scrollbar::-webkit-scrollbar-thumb:hover {
  background-color: #52525b; /* zinc-600 */
}
</style>

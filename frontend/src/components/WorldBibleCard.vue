<script setup lang="ts">
import { useGenesisStore } from '../stores/genesis';
import { useWorldStore } from '../stores/genesis/world';
import { useUIStore } from '../stores/ui';
import { computed, ref, nextTick } from 'vue';
import { ScrollText, Target, MapPin, Key, CheckCircle2, Loader2, Globe, Edit2, LayoutTemplate, Lock } from 'lucide-vue-next';

const genesisStore = useGenesisStore();
const worldStore = useWorldStore();
const uiStore = useUIStore();
const emit = defineEmits(['confirmed', 'updated']);

const bible = computed(() => worldStore.worldBible);

const isEditingTitle = ref(false);
const editTitleValue = ref('');
const titleInput = ref<HTMLInputElement | null>(null);

const startEditingTitle = () => {
  editTitleValue.value = bible.value?.title || bible.value?.scene?.name || '';
  isEditingTitle.value = true;
  nextTick(() => {
    titleInput.value?.focus();
  });
};

const saveTitle = async () => {
  if (!editTitleValue.value.trim()) {
    isEditingTitle.value = false;
    return;
  }
  
  try {
    await worldStore.updateWorldTitle(editTitleValue.value.trim());
    emit('updated');
  } catch (e) {
    console.error("Failed to save title", e);
  } finally {
    isEditingTitle.value = false;
  }
};

const handleConfirm = async () => {
  const confirmed = await uiStore.openModal(
    '确认世界设定',
    '确认以此设定创建世界吗？创建后核心设定将不可更改。确认后将进入第二阶段：居民生成 (NPC Roster)。',
    'confirm'
  );

  if (confirmed) {
    genesisStore.isLoading = true;
    try {
      // Need to pass session context from genesis store
      await worldStore.confirmWorld(genesisStore.sessionId, genesisStore.messages);
      
      // Update genesis store step to keep UI in sync (compatibility)
      genesisStore.currentStep = 'npc';
      
      // 给后端一点时间保存世界文件，确保 Sidebar 刷新时能获取到新世界
      await new Promise(resolve => setTimeout(resolve, 300));
      emit('confirmed');
    } catch (e) {
      console.error("Failed to confirm world", e);
    } finally {
      genesisStore.isLoading = false;
    }
  }
};
</script>

<template>
  <div v-if="bible" class="h-full bg-zinc-900 text-zinc-300 rounded-lg shadow-xl overflow-hidden flex flex-col border border-zinc-800">
    <div class="flex-1 overflow-y-auto p-6 space-y-8 custom-scrollbar">
      <!-- World Title -->
      <section>
        <div class="flex flex-col gap-1 mb-4">
          <h3 class="text-sm font-bold text-[#ccff00]/70 flex items-center gap-2 uppercase tracking-wider">
            <LayoutTemplate class="w-4 h-4" />
            世界 WORLD
          </h3>
          <div v-if="isEditingTitle" class="flex items-center gap-2">
              <input 
                  v-model="editTitleValue" 
                  ref="titleInput"
                  class="bg-zinc-800 border border-zinc-700 text-[#ccff00] px-3 py-2 rounded text-2xl font-black focus:border-[#ccff00] outline-none w-full shadow-inner"
                  @blur="saveTitle"
                  @keyup.enter="saveTitle"
              />
          </div>
          <div v-else class="flex items-center gap-2 cursor-pointer group" @click="startEditingTitle">
              <span class="text-3xl font-black text-[#ccff00] tracking-tight group-hover:opacity-80 transition-opacity">{{ bible.title || bible.scene?.name }}</span>
              <Edit2 class="w-5 h-5 text-[#ccff00]/50 group-hover:text-[#ccff00] transition-colors opacity-0 group-hover:opacity-100" />
          </div>
        </div>
      </section>

      <!-- Background -->
      <section>
        <h3 class="text-md font-bold text-[#ccff00] mb-3 flex items-center gap-2">
          <Globe class="w-4 h-4" />
          世界背景 WORLD SETTING
        </h3>
        <div class="space-y-3 text-sm text-zinc-400">
          <div class="grid grid-cols-2 gap-4">
            <div class="bg-zinc-950 p-3 rounded-lg border border-zinc-800">
              <strong class="text-zinc-500 block text-xs mb-1">时代</strong>
              {{ bible.background?.era }}
            </div>
            <div class="bg-zinc-950 p-3 rounded-lg border border-zinc-800">
              <strong class="text-zinc-500 block text-xs mb-1">社会</strong>
              {{ bible.background?.society }}
            </div>
          </div>
          <div class="bg-zinc-950 p-3 rounded-lg border border-zinc-800">
            <strong class="text-zinc-500 block text-xs mb-2">核心法则</strong>
            <ul class="space-y-1">
              <li v-for="(rule, i) in bible.background?.rules" :key="i" class="flex items-start gap-2">
                <span class="text-zinc-600">•</span>
                {{ rule }}
              </li>
            </ul>
          </div>
        </div>
      </section>

      <!-- Scene -->
      <section>
        <h3 class="text-md font-bold text-[#ccff00] mb-3 flex items-center gap-2">
          <MapPin class="w-4 h-4" />
          核心场景 CORE SCENE
        </h3>
        <div class="space-y-4 text-sm text-zinc-400">
          <div class="bg-zinc-950 p-4 rounded-lg border border-zinc-800">
            <p class="text-[#ccff00] font-bold mb-1 text-lg">{{ bible.scene?.name }}</p>
            <p class="text-zinc-500">{{ bible.scene?.description }}</p>
          </div>
          
          <div v-if="bible.scene?.locations?.length">
            <strong class="text-zinc-500 text-xs uppercase tracking-wider block mb-2">核心区域</strong>
            <div class="flex flex-wrap gap-2">
              <span 
                v-for="(loc, i) in bible.scene?.locations" 
                :key="i"
                class="bg-zinc-800 border border-zinc-700 px-3 py-1 rounded-md text-xs text-zinc-300 hover:border-zinc-500 transition-colors"
              >
                {{ loc }}
              </span>
            </div>
          </div>

          <div>
            <strong class="text-zinc-500 text-xs uppercase tracking-wider block mb-2 flex items-center gap-1">
              <Key class="w-3 h-3" /> 关键物品
            </strong>
            <div class="flex flex-wrap gap-2">
              <span 
                v-for="(obj, i) in bible.scene?.key_objects" 
                :key="i"
                class="bg-zinc-800 px-3 py-1 rounded-md text-xs border border-zinc-700 text-zinc-300"
              >
                {{ obj }}
              </span>
            </div>
          </div>
        </div>
      </section>

      <!-- Player Objective -->
      <section v-if="bible.player_objective" class="bg-zinc-950/50 p-4 rounded-lg border border-zinc-800 hover:border-[#ccff00]/50 transition-colors">
        <h3 class="text-md font-bold text-[#ccff00] mb-3 flex items-center gap-2">
          <Target class="w-4 h-4" />
          玩家使命 PLAYER OBJECTIVE
        </h3>
        <p class="text-sm text-zinc-400 leading-relaxed">{{ bible.player_objective }}</p>
      </section>
    </div>

    <!-- Action Area -->
    <div v-if="!worldStore.finalizedWorldBible" class="p-4 bg-zinc-950 border-t border-zinc-800">
      <button
        @click="handleConfirm"
        class="w-full bg-[#ccff00] hover:bg-[#b3e600] text-black font-extrabold py-3 px-4 rounded-lg transition-all flex items-center justify-center gap-2 shadow-[0_0_10px_rgba(204,255,0,0.3)] hover:shadow-[0_0_20px_rgba(204,255,0,0.6)]"
        :disabled="genesisStore.isLoading"
      >
        <Loader2 v-if="genesisStore.isLoading" class="w-5 h-5 animate-spin" />
        <CheckCircle2 v-else class="w-5 h-5 stroke-[3px]" />
        <span>确认世界之书定稿</span>
      </button>
    </div>
    <div v-else class="p-4 bg-zinc-950 border-t border-zinc-800">
      <div class="w-full bg-zinc-900/50 border border-zinc-800 text-[#ccff00] font-extrabold py-3 px-4 rounded-lg flex items-center justify-center gap-2">
        <CheckCircle2 class="w-5 h-5" />
        <span>定稿</span>
      </div>
    </div>
  </div>
  
  <div v-else class="h-full flex items-center justify-center bg-zinc-900 border border-dashed border-zinc-800 rounded-lg text-zinc-600">
    <div class="text-center">
      <ScrollText class="w-12 h-12 mx-auto mb-4 opacity-20" />
      <p>等待创世...</p>
      <p class="text-sm mt-2">请在左侧与播种者对话</p>
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
  background-color: #3f3f46;
  border-radius: 3px;
}
.custom-scrollbar::-webkit-scrollbar-thumb:hover {
  background-color: #52525b;
}
</style>

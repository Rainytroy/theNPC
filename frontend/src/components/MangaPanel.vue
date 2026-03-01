<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue';
import { Play, Pause, BookOpen, Clock, List, RefreshCw, Loader2, Settings2 } from 'lucide-vue-next';
import MangaStatusModal from './MangaStatusModal.vue';
import { useGenesisStore } from '../stores/genesis';
import worldApi from '../api/world';

const props = defineProps<{
  worldId: string;
}>();

const store = useGenesisStore();
const pageSize = ref(10);

interface MangaPage {
  id: string;
  timestamp: number;
  image_url: string;
  plot: string;
  events_range: {
    start: number;
    end: number;
  };
}

const pages = ref<MangaPage[]>([]);
const selectedPageIndex = ref(0);
const isGenerating = ref(false);
const showStatusModal = ref(false);
const regeneratingPageId = ref<string | null>(null);
let pollTimer: number | null = null;

const apiBase = `http://127.0.0.1:26000/api/worlds/${props.worldId}/manga`;

const updatePageSize = async () => {
  if (!store.finalizedWorldBible?.world_id) return;
  
  // Update local
  store.worldConfig.manga_page_size = pageSize.value;
  
  // Update server
  try {
    await worldApi.updateConfig(store.finalizedWorldBible.world_id, store.worldConfig);
  } catch (e) {
    console.error("Failed to update page size", e);
  }
};

const fetchPages = async () => {
  try {
    const res = await fetch(`${apiBase}/pages`);
    const data = await res.json();
    if (data.pages) {
      const isAtEnd = selectedPageIndex.value === pages.value.length - 1;
      const oldLength = pages.value.length;
      
      pages.value = data.pages;
      
      // Auto-scroll to new page if user was at end
      if (oldLength > 0 && data.pages.length > oldLength && isAtEnd) {
        selectedPageIndex.value = data.pages.length - 1;
      } else if (oldLength === 0 && data.pages.length > 0) {
        selectedPageIndex.value = 0;
      }
    }
  } catch (e) {
    console.error("Failed to fetch manga pages", e);
  }
};

const checkStatus = async () => {
  try {
    const res = await fetch(`${apiBase}/status`);
    const data = await res.json();
    isGenerating.value = data.is_running;
  } catch (e) {
    console.error("Failed to check status", e);
  }
};

const toggleGeneration = async () => {
  const action = isGenerating.value ? 'stop' : 'start';
  try {
    await fetch(`${apiBase}/${action}`, { method: 'POST' });
    isGenerating.value = !isGenerating.value;
  } catch (e) {
    console.error(`Failed to ${action} generation`, e);
  }
};

const regeneratePage = async (pageId: string) => {
  if (regeneratingPageId.value) return;
  regeneratingPageId.value = pageId;
  try {
    const res = await fetch(`${apiBase}/regenerate/${pageId}`, { method: 'POST' });
    if (res.ok) {
      const newPage = await res.json();
      // Update page in list
      const index = pages.value.findIndex(p => p.id === pageId);
      if (index !== -1) {
        pages.value[index] = newPage;
      }
    } else {
      console.error("Failed to regenerate page");
    }
  } catch (e) {
    console.error("Error regenerating page", e);
  } finally {
    regeneratingPageId.value = null;
  }
};

onMounted(() => {
  fetchPages();
  checkStatus();
  
  if (store.worldConfig?.manga_page_size) {
    pageSize.value = store.worldConfig.manga_page_size;
  }

  // Poll every 5 seconds
  pollTimer = window.setInterval(() => {
    fetchPages();
    checkStatus(); // Sync status in case it stopped automatically
  }, 5000);
});

onUnmounted(() => {
  if (pollTimer) clearInterval(pollTimer);
});

const selectPage = (index: number) => {
  selectedPageIndex.value = index;
};

const formatTime = (ts: number) => {
  return new Date(ts).toLocaleString();
};
</script>

<template>
  <div class="relative flex h-full bg-zinc-950 rounded-xl border border-zinc-800 overflow-hidden">
    
    <!-- Left Sidebar: Page List (20%) -->
    <div class="w-64 bg-zinc-900 border-r border-zinc-800 flex flex-col">
      <!-- Header -->
      <div class="p-4 border-b border-zinc-800 flex items-center justify-between">
        <h3 class="text-zinc-300 font-bold flex items-center gap-2">
          <BookOpen class="w-4 h-4 text-[#d946ef]" />
          <span>漫画章节</span>
        </h3>
        <span class="text-xs text-zinc-500">{{ pages.length }} 页</span>
      </div>

      <!-- Controls -->
      <div class="p-4 border-b border-zinc-800 flex gap-2">
        <button 
          @click="toggleGeneration"
          class="flex-1 flex items-center justify-center gap-2 py-2 rounded-lg font-bold text-sm transition-all"
          :class="isGenerating 
            ? 'bg-zinc-800 text-red-500 hover:bg-zinc-700' 
            : 'bg-[#d946ef] text-black hover:bg-[#c026d3]'"
        >
          <component :is="isGenerating ? Pause : Play" class="w-4 h-4 fill-current" />
          <span>{{ isGenerating ? '暂停' : '开始' }}</span>
        </button>

        <!-- Progress Button -->
        <button 
          @click="showStatusModal = true"
          class="w-10 flex items-center justify-center rounded-lg bg-zinc-800 text-zinc-400 hover:text-white hover:bg-zinc-700 transition-colors"
          title="查看生成进度"
        >
          <List class="w-4 h-4" />
        </button>
      </div>
      <p v-if="isGenerating" class="text-xs text-[#d946ef] text-center pb-2 -mt-2 animate-pulse">
        正在构思下一页...
      </p>

      <!-- Settings: Page Size -->
      <div class="px-4 py-3 border-b border-zinc-800 bg-zinc-900/50">
          <div class="flex justify-between items-center text-[10px] text-zinc-500 mb-2 uppercase tracking-wider font-bold">
              <span class="flex items-center gap-1"><Settings2 class="w-3 h-3" /> 篇幅控制</span>
              <span class="text-[#d946ef]">{{ pageSize }} 事件/页</span>
          </div>
          <input 
              type="range" 
              min="5" 
              max="40" 
              step="1"
              v-model.number="pageSize"
              @change="updatePageSize"
              class="w-full accent-[#d946ef] h-1.5 bg-zinc-800 rounded-lg appearance-none cursor-pointer hover:bg-zinc-700 transition-colors"
          />
      </div>

      <!-- Page Thumbnails -->
      <div class="flex-1 overflow-y-auto p-2 space-y-2 custom-scrollbar">
        <div 
          v-for="(page, index) in pages" 
          :key="page.id"
          @click="selectPage(index)"
          class="p-2 rounded-lg cursor-pointer border transition-all hover:bg-zinc-800"
          :class="selectedPageIndex === index ? 'border-[#d946ef] bg-zinc-800' : 'border-transparent'"
        >
          <div class="aspect-[2/3] w-full bg-black rounded mb-2 overflow-hidden relative">
            <img :src="page.image_url" class="w-full h-full object-cover" loading="lazy" />
            <div class="absolute bottom-0 right-0 bg-black/70 text-white text-[10px] px-1">
              #{{ index + 1 }}
            </div>
          </div>
          <div class="text-[10px] text-zinc-500 truncate flex items-center gap-1">
            <Clock class="w-3 h-3" />
            {{ formatTime(page.timestamp) }}
          </div>
        </div>
      </div>
    </div>

    <!-- Right Main View: Reader (80%) -->
    <div class="flex-1 bg-zinc-950 flex flex-col items-center justify-center relative overflow-hidden">
      <div v-if="pages.length > 0" class="h-full w-full p-4 overflow-y-auto flex items-center justify-center custom-scrollbar">
        <!-- Manga Page -->
        <div class="max-h-full aspect-[2/3] relative shadow-2xl group">
          <img 
            :src="pages[selectedPageIndex].image_url" 
            class="h-full w-full object-contain bg-white"
          />
          
          <!-- Redraw Button (Bottom Right) -->
          <div class="absolute bottom-4 right-4 opacity-0 group-hover:opacity-100 transition-opacity duration-300">
            <button 
              @click.stop="regeneratePage(pages[selectedPageIndex].id)"
              class="p-2 rounded-full bg-black/50 hover:bg-[#d946ef] text-white backdrop-blur-sm transition-all transform hover:scale-110"
              :disabled="!!regeneratingPageId"
              title="重绘此页"
            >
              <Loader2 v-if="regeneratingPageId === pages[selectedPageIndex].id" class="w-5 h-5 animate-spin" />
              <RefreshCw v-else class="w-5 h-5" />
            </button>
          </div>
        </div>
      </div>
      
      <div v-else class="text-center text-zinc-600">
        <BookOpen class="w-16 h-16 mx-auto mb-4 opacity-20" />
        <p>暂无漫画内容</p>
        <p class="text-sm mt-2">点击左侧“开始”生成第一页</p>
      </div>
    </div>

    <!-- Status Modal -->
    <MangaStatusModal 
      :show="showStatusModal" 
      :world-id="worldId"
      @close="showStatusModal = false" 
    />

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

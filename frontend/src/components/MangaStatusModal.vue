<script setup lang="ts">
import { ref, onMounted, watch } from 'vue';
import { X, RefreshCw, Loader2, Activity, AlertCircle } from 'lucide-vue-next';

const props = defineProps<{
  worldId: string;
  show: boolean;
}>();

const emit = defineEmits(['close']);

interface ProgressData {
  total_events: number;
  processed_events: number;
  queue_size: number;
  pages_generated: number;
  is_running: boolean;
}

const progress = ref<ProgressData | null>(null);
const isLoading = ref(false);
const error = ref<string | null>(null);

const fetchProgress = async () => {
  isLoading.value = true;
  error.value = null;
  console.log("Fetching progress for world:", props.worldId);
  try {
    const res = await fetch(`http://127.0.0.1:26000/api/worlds/${props.worldId}/manga/progress`);
    if (!res.ok) {
        throw new Error(`HTTP error! status: ${res.status}`);
    }
    progress.value = await res.json();
    console.log("Progress data received:", progress.value);
  } catch (e: any) {
    console.error("Failed to fetch progress", e);
    error.value = e.message || "Failed to load progress";
  } finally {
    isLoading.value = false;
  }
};

watch(() => props.show, (newVal) => {
  if (newVal) fetchProgress();
});

onMounted(() => {
  if (props.show) fetchProgress();
});
</script>

<template>
  <Transition name="modal">
    <div v-if="show" class="absolute inset-0 z-10 flex items-center justify-center p-4">
      <!-- Backdrop -->
      <div class="absolute inset-0 bg-black/80 backdrop-blur-sm" @click="emit('close')"></div>

      <!-- Modal Card -->
      <div class="relative w-96 bg-zinc-900 border border-zinc-800 rounded-xl overflow-hidden shadow-2xl transform transition-all">
        <div class="p-4 border-b border-zinc-800 flex items-center justify-between bg-zinc-950/50">
          <h3 class="text-zinc-200 font-bold flex items-center gap-2">
            <Activity class="w-4 h-4 text-[#d946ef]" />
            生成进度详情
          </h3>
          <button @click="emit('close')" class="text-zinc-500 hover:text-white transition-colors">
            <X class="w-4 h-4" />
          </button>
        </div>
        
        <div class="p-6 space-y-6">
          <div v-if="isLoading && !progress" class="flex justify-center py-8">
            <Loader2 class="w-8 h-8 text-[#d946ef] animate-spin" />
          </div>

          <div v-else-if="error" class="flex flex-col items-center justify-center py-6 text-center">
            <AlertCircle class="w-8 h-8 text-red-500 mb-2" />
            <p class="text-zinc-400 text-sm mb-4">{{ error }}</p>
            <button 
              @click="fetchProgress" 
              class="px-4 py-2 bg-zinc-800 hover:bg-zinc-700 text-white rounded text-sm transition-colors"
            >
              重试
            </button>
          </div>
          
          <div v-else-if="progress" class="space-y-4">
            <!-- Status Grid -->
            <div class="grid grid-cols-2 gap-3">
              <div class="bg-zinc-950 p-4 rounded-lg border border-zinc-800/50 hover:border-zinc-700 transition-colors">
                <div class="text-zinc-500 text-xs mb-1 uppercase tracking-wider">总事件数</div>
                <div class="text-2xl font-mono text-white font-bold">{{ progress.total_events }}</div>
              </div>
              <div class="bg-zinc-950 p-4 rounded-lg border border-zinc-800/50 hover:border-zinc-700 transition-colors">
                <div class="text-zinc-500 text-xs mb-1 uppercase tracking-wider">已生成页数</div>
                <div class="text-2xl font-mono text-[#d946ef] font-bold">{{ progress.pages_generated }}</div>
              </div>
              <div class="bg-zinc-950 p-4 rounded-lg border border-zinc-800/50 hover:border-zinc-700 transition-colors">
                <div class="text-zinc-500 text-xs mb-1 uppercase tracking-wider">已处理事件</div>
                <div class="text-2xl font-mono text-emerald-500 font-bold">{{ progress.processed_events }}</div>
              </div>
              <div class="bg-zinc-950 p-4 rounded-lg border border-zinc-800/50 hover:border-zinc-700 transition-colors">
                <div class="text-zinc-500 text-xs mb-1 uppercase tracking-wider">排队中</div>
                <div class="text-2xl font-mono text-amber-500 font-bold">{{ progress.queue_size }}</div>
              </div>
            </div>
            
            <!-- Running Status -->
            <div class="flex items-center justify-between p-4 bg-zinc-950 rounded-lg border border-zinc-800/50">
              <span class="text-sm text-zinc-400">后台服务状态</span>
              <span class="flex items-center gap-2 text-sm font-medium" 
                :class="progress.is_running ? 'text-emerald-500' : 'text-zinc-500'">
                <span class="w-2 h-2 rounded-full" :class="progress.is_running ? 'bg-emerald-500 animate-pulse' : 'bg-zinc-700'"></span>
                {{ progress.is_running ? '运行中' : '已停止' }}
              </span>
            </div>
          </div>
        </div>
        
        <div class="p-4 border-t border-zinc-800 flex justify-end bg-zinc-950/30">
          <button 
            @click="fetchProgress" 
            class="flex items-center gap-2 px-4 py-2 bg-zinc-800 hover:bg-zinc-700 hover:text-white text-zinc-300 rounded-lg text-sm transition-all border border-zinc-700 hover:border-zinc-600"
            :disabled="isLoading"
          >
            <RefreshCw class="w-3.5 h-3.5" :class="{ 'animate-spin': isLoading }" />
            刷新状态
          </button>
        </div>
      </div>
    </div>
  </Transition>
</template>

<style scoped>
.modal-enter-active,
.modal-leave-active {
  transition: opacity 0.3s ease;
}

.modal-enter-from,
.modal-leave-to {
  opacity: 0;
}

.modal-enter-active .relative,
.modal-leave-active .relative {
  transition: transform 0.3s ease;
}

.modal-enter-from .relative,
.modal-leave-to .relative {
  transform: scale(0.95) translateY(10px);
}
</style>

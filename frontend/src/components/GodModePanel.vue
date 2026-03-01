<script setup lang="ts">
import { ref, computed, onMounted } from 'vue';
import { useGenesisStore } from '../stores/genesis';
import { 
  User, ChevronDown, CheckCircle2, Circle, 
  XCircle, Clock, Target, Calendar, MapPin, Activity,
  RefreshCw, Loader2
} from 'lucide-vue-next';

const props = defineProps<{
  currentTime?: Date;
}>();

const store = useGenesisStore();
const selectedNpcId = ref<string>('');
const isDropdownOpen = ref(false);
const isRefreshing = ref(false);

const handleRefresh = async () => {
  isRefreshing.value = true;
  try {
    await store.refreshWorld();
  } finally {
    isRefreshing.value = false;
  }
};

// Ensure we have a selection on mount
onMounted(async () => {
  await handleRefresh(); // Auto refresh on enter
  if (store.npcs.length > 0 && !selectedNpcId.value) {
    selectedNpcId.value = store.npcs[0].id;
  }
});

const selectedNpc = computed(() => 
  store.npcs.find(n => n.id === selectedNpcId.value)
);

const currentGoals = computed(() => 
  selectedNpc.value?.goals || []
);

const currentSchedule = computed(() => {
  if (!selectedNpcId.value) return [];
  // Ensure sorted by time
  const schedule = [...(store.schedules[selectedNpcId.value] || [])];
  return schedule.sort((a, b) => {
    return a.time.localeCompare(b.time);
  });
});

const activeScheduleIndex = computed(() => {
  if (!props.currentTime || currentSchedule.value.length === 0) return -1;
  
  const now = props.currentTime;
  const currentMinutes = now.getHours() * 60 + now.getMinutes();
  
  let activeIndex = -1;
  
  for (let i = 0; i < currentSchedule.value.length; i++) {
    const item = currentSchedule.value[i];
    const [h, m] = item.time.split(':').map(Number);
    const itemMinutes = h * 60 + m;
    
    if (itemMinutes <= currentMinutes) {
      activeIndex = i;
    } else {
      break; 
    }
  }
  
  return activeIndex;
});

const selectNpc = (id: string) => {
  selectedNpcId.value = id;
  isDropdownOpen.value = false;
};

// Helper to determine status color
const getStatusColor = (status: string) => {
  switch (status) {
    case 'completed': return 'text-emerald-500';
    case 'in_progress': return 'text-[#d946ef]';
    case 'failed': return 'text-red-500';
    case 'abandoned': return 'text-zinc-600';
    default: return 'text-zinc-400';
  }
};

const getStatusIcon = (status: string) => {
  switch (status) {
    case 'completed': return CheckCircle2;
    case 'in_progress': return Activity;
    case 'failed': return XCircle;
    case 'abandoned': return XCircle;
    default: return Circle;
  }
};

</script>

<template>
  <div class="h-full flex flex-col bg-zinc-900/50 rounded-xl border border-zinc-800 backdrop-blur-sm overflow-hidden">
    
    <!-- Top Bar: NPC Selector -->
    <div class="p-4 border-b border-zinc-800 bg-zinc-950/50 flex items-center justify-between z-20 relative">
      <div class="flex items-center gap-3">
        <div class="w-10 h-10 rounded-lg bg-zinc-800 overflow-hidden border border-zinc-700">
          <img 
            v-if="selectedNpc?.profile.avatar_url" 
            :src="selectedNpc.profile.avatar_url" 
            class="w-full h-full object-cover object-top"
          />
          <User v-else class="w-full h-full p-2 text-zinc-500" />
        </div>
        <div>
          <h2 class="text-sm font-bold text-white">{{ selectedNpc?.profile.name || 'Select NPC' }}</h2>
          <p class="text-xs text-zinc-500">{{ selectedNpc?.profile.occupation || 'Unknown' }}</p>
        </div>
      </div>

      <div class="flex items-center gap-2">
        <button 
          @click="handleRefresh"
          :disabled="isRefreshing"
          class="p-1.5 bg-zinc-900 border border-zinc-800 rounded-lg hover:border-[#d946ef] hover:text-[#d946ef] transition-all text-zinc-400 disabled:opacity-50"
          title="Refresh Data"
        >
          <Loader2 v-if="isRefreshing" class="w-4 h-4 animate-spin" />
          <RefreshCw v-else class="w-4 h-4" />
        </button>

        <!-- Dropdown Trigger -->
        <div class="relative">
          <button 
            @click="isDropdownOpen = !isDropdownOpen"
            class="flex items-center gap-2 px-3 py-1.5 bg-zinc-900 border border-zinc-800 rounded-lg hover:border-[#d946ef] hover:text-[#d946ef] transition-all text-xs font-bold"
          >
            <span>SWITCH VIEW</span>
            <ChevronDown class="w-3 h-3 transition-transform" :class="{ 'rotate-180': isDropdownOpen }" />
          </button>

        <!-- Dropdown Menu -->
        <div 
          v-if="isDropdownOpen" 
          class="absolute right-0 top-full mt-2 w-64 bg-zinc-900 border border-zinc-800 rounded-xl shadow-xl overflow-hidden max-h-[400px] overflow-y-auto custom-scrollbar z-50"
        >
          <div 
            v-for="npc in store.npcs" 
            :key="npc.id"
            @click="selectNpc(npc.id)"
            class="flex items-center gap-3 p-3 hover:bg-zinc-800 cursor-pointer border-b border-zinc-800/50 last:border-0 transition-colors"
            :class="{ 'bg-zinc-800/50': npc.id === selectedNpcId }"
          >
            <div class="w-8 h-8 rounded bg-zinc-800 overflow-hidden flex-shrink-0">
              <img v-if="npc.profile.avatar_url" :src="npc.profile.avatar_url" class="w-full h-full object-cover object-top" />
              <User v-else class="w-full h-full p-1.5 text-zinc-500" />
            </div>
            <div class="flex-1 min-w-0">
              <div class="text-xs font-bold text-zinc-200 truncate">{{ npc.profile.name }}</div>
              <div class="text-[10px] text-zinc-500 truncate">{{ npc.profile.occupation }}</div>
            </div>
            <CheckCircle2 v-if="npc.id === selectedNpcId" class="w-4 h-4 text-[#d946ef]" />
          </div>
        </div>
      </div>
      </div>
    </div>

    <!-- Dropdown Backdrop -->
    <div v-if="isDropdownOpen" @click="isDropdownOpen = false" class="fixed inset-0 z-10"></div>

    <!-- Content Area -->
    <div class="flex-1 overflow-y-auto custom-scrollbar p-6 space-y-8" v-if="selectedNpc">
      
      <!-- 1. Goals Section -->
      <section>
        <h3 class="flex items-center gap-2 text-xs font-bold text-zinc-500 uppercase tracking-widest mb-4">
          <Target class="w-4 h-4" /> 当前目标 GOALS
        </h3>
        
        <div v-if="currentGoals.length === 0" class="text-zinc-600 text-sm italic">
          暂无明确目标
        </div>

        <div class="grid gap-3">
          <div 
            v-for="goal in currentGoals" 
            :key="goal.id"
            class="bg-zinc-950 border border-zinc-800 rounded-lg p-4 flex gap-4 transition-all hover:border-zinc-700"
          >
            <!-- Status Icon -->
            <component 
              :is="getStatusIcon(goal.status)" 
              class="w-5 h-5 flex-shrink-0 mt-0.5" 
              :class="getStatusColor(goal.status)"
            />
            
            <div class="flex-1">
              <div class="flex items-start justify-between gap-4">
                <p class="text-sm font-medium text-zinc-200">{{ goal.description }}</p>
                <span 
                  class="text-[10px] uppercase font-bold px-1.5 py-0.5 rounded border"
                  :class="[
                    getStatusColor(goal.status),
                    'border-current opacity-70'
                  ]"
                >
                  {{ goal.status }}
                </span>
              </div>
              
              <div class="flex items-center gap-2 mt-2 text-xs text-zinc-500">
                <span class="bg-zinc-900 px-1.5 py-0.5 rounded border border-zinc-800">
                  {{ goal.type === 'main' ? '主线' : '支线' }}
                </span>
                <span v-if="goal.trigger_condition">
                  触发: {{ goal.trigger_condition }}
                </span>
              </div>
            </div>
          </div>
        </div>
      </section>

      <!-- 2. Schedule Section -->
      <section>
        <h3 class="flex items-center gap-2 text-xs font-bold text-zinc-500 uppercase tracking-widest mb-4">
          <Calendar class="w-4 h-4" /> 今日日程 SCHEDULE
        </h3>

        <div v-if="currentSchedule.length === 0" class="text-zinc-600 text-sm italic">
          今日暂无安排（或正在生成中）
        </div>

        <div class="relative pl-4 border-l border-zinc-800 space-y-6">
          <div 
            v-for="(item, index) in currentSchedule" 
            :key="index"
            class="relative pl-6 group"
          >
            <!-- Timeline Dot -->
            <div 
              class="absolute -left-[5px] top-1.5 w-2.5 h-2.5 rounded-full border-2 border-zinc-950 group-hover:scale-125 transition-transform"
              :class="index === activeScheduleIndex ? 'bg-[#d946ef] shadow-[0_0_8px_#d946ef]' : 'bg-zinc-700'"
            ></div>

            <div class="flex flex-col sm:flex-row sm:items-baseline gap-1 sm:gap-4">
              <span class="font-mono text-[#d946ef] font-bold text-sm">{{ item.time }}</span>
              <div class="flex-1">
                <p 
                  class="text-sm transition-colors"
                  :class="index === activeScheduleIndex ? 'text-[#d946ef] font-bold' : 'text-zinc-400 group-hover:text-zinc-300'"
                >
                  {{ item.description }}
                </p>
                <div v-if="item.location" class="flex items-center gap-1 mt-1 text-xs text-zinc-600">
                  <MapPin class="w-3 h-3" />
                  {{ item.location }}
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

    </div>
    
    <div v-else class="flex-1 flex items-center justify-center text-zinc-600">
      Select an NPC to view details
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

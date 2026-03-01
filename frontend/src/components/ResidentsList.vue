<script setup lang="ts">
import { computed } from 'vue';
import { User, MapPin, Activity } from 'lucide-vue-next';
import { useGenesisStore } from '../stores/genesis';

interface NPC {
  id: string;
  profile: {
    name: string;
    age: number;
    gender: string;
    race: string;
    avatar_desc: string;
    occupation: string;
    avatar_url?: string;
  };
  dynamic: {
    personality_desc: string;
    values: string[];
    mood: string;
    current_location: string;
    current_action?: string;
  };
  [key: string]: any;
}

interface Props {
  npcs: NPC[];
  selectedNpcId: string | null;
  selectedLocation: string | null;
  locations: string[];
}

const props = defineProps<Props>();
const emit = defineEmits<{
  'select-npc': [npcId: string];
  'select-location': [location: string];
}>();

const store = useGenesisStore();

// 动态收集所有实际存在的地点（世界书地点 + NPC实际所在地点）
const allLocations = computed(() => {
  // 收集所有NPC实际所在的地点
  const npcLocations = props.npcs
    .map(npc => npc.dynamic.current_location)
    .filter(Boolean);
  
  // 合并世界书地点和实际地点，去重并保持顺序
  const uniqueLocations = Array.from(new Set([...props.locations, ...npcLocations]));
  
  return uniqueLocations;
});

// 按地点分组NPCs
const npcsByLocation = computed(() => {
  const grouped: Record<string, NPC[]> = {};
  
  // 初始化所有地点（包括动态发现的）
  allLocations.value.forEach(location => {
    grouped[location] = [];
  });
  
  // 将NPCs分配到各个地点
  props.npcs.forEach(npc => {
    const location = npc.dynamic.current_location;
    if (location && grouped[location]) {
      grouped[location].push(npc);
    }
  });
  
  return grouped;
});

// 获取指定地点的NPCs
const getNPCsAtLocation = (location: string) => {
  return npcsByLocation.value[location] || [];
};

// 处理NPC点击
const handleNpcClick = (npcId: string) => {
  emit('select-npc', npcId);
};

// 处理地点点击
const handleLocationClick = (location: string) => {
  emit('select-location', location);
};
</script>

<template>
  <div class="h-full flex flex-col bg-zinc-900/50 rounded-xl border border-zinc-800 backdrop-blur-sm overflow-hidden">
    <!-- 标题栏 -->
    <div class="p-4 border-b border-zinc-800">
      <h3 class="font-bold text-zinc-500 text-xs uppercase tracking-widest flex items-center gap-2">
        <User class="w-4 h-4" /> 居民列表 RESIDENTS
      </h3>
    </div>
    
    <!-- 地点卡片列表 -->
    <div class="flex-1 overflow-y-auto custom-scrollbar p-4 grid grid-cols-1 lg:grid-cols-2 xl:grid-cols-3 gap-4 auto-rows-min">
      <!-- 每个地点的卡片 -->
      <div 
        v-for="location in allLocations" 
        :key="location"
        @click="handleLocationClick(location)"
        class="rounded-lg border overflow-hidden transition-all flex flex-col cursor-pointer"
        :class="selectedLocation === location 
          ? 'bg-zinc-950 border-[#d946ef] shadow-[0_0_15px_rgba(217,70,239,0.15)]' 
          : 'bg-zinc-950 border-zinc-800 hover:border-zinc-700'"
      >
        <!-- 地点标题 -->
        <div class="px-3 py-2 border-b flex items-center justify-between transition-colors"
          :class="selectedLocation === location 
            ? 'bg-[#d946ef]/10 border-[#d946ef]/30' 
            : 'bg-zinc-900/80 border-zinc-800'"
        >
          <div class="flex items-center gap-2">
            <MapPin class="w-4 h-4" :class="selectedLocation === location ? 'text-[#d946ef] animate-pulse' : 'text-[#d946ef]'" />
            <span class="text-sm font-bold" :class="selectedLocation === location ? 'text-[#d946ef]' : 'text-[#d946ef]'">{{ location }}</span>
          </div>
          <span 
            class="text-sm font-bold"
            :class="getNPCsAtLocation(location).length > 0 ? 'text-[#d946ef]' : 'text-zinc-600'"
          >
            {{ getNPCsAtLocation(location).length }}
          </span>
        </div>
        
        <!-- NPCs容器 -->
        <div class="p-2 space-y-2" @click.stop>
          <!-- 空状态 -->
          <div 
            v-if="getNPCsAtLocation(location).length === 0"
            class="text-center py-4 text-zinc-600 text-xs"
          >
            无人在此
          </div>
          
          <!-- NPC小卡片 -->
          <div
            v-for="npc in getNPCsAtLocation(location)"
            :key="npc.id"
            @click="handleNpcClick(npc.id)"
            class="p-3 rounded-lg border transition-all cursor-pointer group relative"
            :class="selectedNpcId === npc.id 
              ? 'bg-[#d946ef]/10 border-[#d946ef]' 
              : 'bg-zinc-900 border-zinc-800 hover:border-zinc-600 hover:bg-zinc-800/50'"
          >
            <div class="flex items-start gap-3 relative z-10">
              <!-- 头像 -->
              <div 
                class="rounded-lg bg-zinc-800 flex items-center justify-center border border-zinc-700 flex-shrink-0 overflow-hidden relative transition-all"
                :class="store.isIllustratedMode ? 'w-10 aspect-[9/16]' : 'w-10 h-10'"
              >
                <img 
                  v-if="store.isIllustratedMode && npc.profile.avatar_url" 
                  :src="npc.profile.avatar_url" 
                  class="w-full h-full object-cover object-top"
                />
                <User v-else class="w-5 h-5 text-zinc-400" />
              </div>
              
              <!-- 信息 -->
              <div class="flex-1 min-w-0">
                <!-- 名称 -->
                <div class="flex items-center gap-2 mb-1">
                  <span 
                    class="text-sm font-bold text-zinc-200 group-hover:text-[#d946ef] transition-colors"
                  >
                    {{ npc.profile.name }}
                  </span>
                  <Activity 
                    v-if="npc.dynamic?.current_action" 
                    class="w-3 h-3 text-emerald-500 animate-pulse flex-shrink-0" 
                  />
                </div>
                
                <!-- 正在做什么：最多3行，无斜体无引号 -->
                <div 
                  v-if="npc.dynamic?.current_action" 
                  class="text-xs text-zinc-400 line-clamp-3"
                >
                  {{ npc.dynamic.current_action }}
                </div>
              </div>
            </div>
            
            <!-- 选中指示器 -->
            <div 
              v-if="selectedNpcId === npc.id" 
              class="absolute inset-0 bg-gradient-to-r from-[#d946ef]/5 to-transparent pointer-events-none rounded-lg"
            ></div>
          </div>
        </div>
      </div>
      
      <!-- 全局空状态 -->
      <div 
        v-if="npcs.length === 0"
        class="flex flex-col items-center justify-center text-zinc-600 py-8"
      >
        <User class="w-8 h-8 mb-2 opacity-20" />
        <p class="text-sm">暂无居民</p>
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
  background-color: #3f3f46;
  border-radius: 3px;
}
.custom-scrollbar::-webkit-scrollbar-thumb:hover {
  background-color: #52525b;
}
</style>

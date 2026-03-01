<script setup lang="ts">
import { ref, onMounted, onUnmounted, nextTick, computed } from 'vue';
import { useRoute } from 'vue-router';
import { useGenesisStore } from '../stores/genesis';
import { useWorldStore } from '../stores/genesis/world';
import { useNpcStore } from '../stores/genesis/npc';
import { useQuestStore } from '../stores/genesis/quest';
import worldApi from '../api/world';
import RuntimeSidebar from '../components/RuntimeSidebar.vue';
import ResidentsList from '../components/ResidentsList.vue';
import MangaPanel from '../components/MangaPanel.vue';
import GodModePanel from '../components/GodModePanel.vue';
import ArchiveModal from '../components/ArchiveModal.vue';
import QuestChips, { type QuestChip } from '../components/QuestChips.vue';
import { 
  Play, Pause, Clock, Send, MapPin,
  History, Loader2, ArrowRight, Archive 
} from 'lucide-vue-next';

const store = useGenesisStore();
const route = useRoute();

// 侧边栏状态管理
const activePanel = ref<string>('residents');

// 获取纪元标签
const displayYear = computed(() => {
  return store.finalizedWorldBible?.time_config?.display_year || null;
});

// 获取地点列表
const locations = computed(() => {
  return store.finalizedWorldBible?.scene?.locations || [];
});

interface GameEvent {
  content: string;
  category: string;
  source?: string;
  target?: string;
  timestamp: number;
  game_time?: string;
  metadata?: Record<string, any>;
}

interface ParsedContent {
  type: 'action' | 'dialogue';
  text: string;
}

const worldTime = ref("Loading...");
const currentWorldDate = ref<Date>(new Date());
const isRunning = ref(false);
const isLoading = ref(true);
const isInitializing = ref(false);
const initStatus = ref("正在连接世界...");
const events = ref<GameEvent[]>([]);
const playerInput = ref("");
const selectedNpcId = ref<string | null>(null);
const selectedLocation = ref<string | null>(null);
const currentScale = ref(24); 
const showArchiveModal = ref(false);
const logContainer = ref<HTMLElement | null>(null);
let socket: WebSocket | null = null;

// ==================== Quest Chips 状态 ====================
const activeChips = ref<QuestChip[]>([]);
const activeChipsNpcId = ref<string>('');
const activeChipsEventIndex = ref<number>(-1);  // 关联的事件索引
const isChipLoading = ref(false);

const connectWebSocket = (worldId: string) => {
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  socket = new WebSocket(`ws://127.0.0.1:26000/api/worlds/ws/${worldId}`);
  
  socket.onopen = () => {
    console.log("WebSocket Connected");
  };
  
  socket.onmessage = (event) => {
    const data = JSON.parse(event.data);
    
    if (data.type === 'init' || data.type === 'time_update') {
      const date = new Date(data.world_time);
      currentWorldDate.value = date;
      worldTime.value = date.toLocaleString('zh-CN', { 
        year: 'numeric',
        weekday: 'short', 
        month: 'short', 
        day: 'numeric', 
        hour: '2-digit', 
        minute: '2-digit' 
      });
      if (data.is_running !== undefined) isRunning.value = data.is_running;
    } 
    else if (data.type === 'status') {
      // 初始化状态更新
      isInitializing.value = true;
      initStatus.value = data.message;
    }
    else if (data.type === 'ready') {
      // 初始化完成
      isInitializing.value = false;
    }
    else if (data.type === 'history') {
      events.value = data.events.map((e: any) => ({
        ...e,
        timestamp: e.timestamp || Date.now()
      }));
      scrollToBottom();
    } 
    else if (data.type === 'history_chunk') {
      const newEvents = data.events.map((e: any) => ({
        ...e,
        timestamp: e.timestamp || Date.now()
      }));
      // Prepend events
      events.value = [...newEvents, ...events.value];
    }
    else if (data.type === 'event') {
      events.value.push({
        content: data.content,
        category: data.category || 'general',
        source: data.source,
        target: data.target,
        timestamp: data.timestamp || Date.now(),
        game_time: data.game_time,
        metadata: data.metadata
      });
      scrollToBottom();
    } 
    else if (data.type === 'npc_update') {
      const { npc_id, changes } = data.payload;
      const npc = store.npcs.find(n => n.id === npc_id);
      if (npc) {
        if (changes.location) npc.dynamic.current_location = changes.location;
        if (changes.current_action) npc.dynamic.current_action = changes.current_action;
        if (changes.goals) npc.goals = changes.goals;
      }
    }
    else if (data.type === 'schedule_update') {
      const { npc_id, schedule } = data;
      store.schedules[npc_id] = schedule;
    }
    // ==================== Quest Chips 处理 ====================
    else if (data.type === 'chips') {
      // 收到任务触发的 Chips 选项
      activeChips.value = data.chips || [];
      activeChipsNpcId.value = data.npc_id || '';
      activeChipsEventIndex.value = events.value.length - 1;
      isChipLoading.value = false;
      scrollToBottom();
    }
    else if (data.type === 'chip_response') {
      // Chip 点击后的响应
      isChipLoading.value = false;
      
      if (data.clear_chips) {
        activeChips.value = [];
        activeChipsNpcId.value = '';
        activeChipsEventIndex.value = -1;
      }
      
      // 如果有新的 chips（对话流的下一句）
      if (data.new_chips && data.new_chips.length > 0) {
        activeChips.value = data.new_chips;
        activeChipsEventIndex.value = events.value.length - 1;
      }
      
      scrollToBottom();
    }
    else if (data.type === 'dialogue_flow_end') {
      // 对话流结束
      activeChips.value = [];
      activeChipsNpcId.value = '';
      activeChipsEventIndex.value = -1;
      isChipLoading.value = false;
    }
  };
  
  socket.onclose = () => {
    console.log("WebSocket Disconnected");
  };
};

const scrollToBottom = () => {
  nextTick(() => {
    if (logContainer.value) {
      logContainer.value.scrollTop = logContainer.value.scrollHeight;
    }
  });
};

// Helper to check if WebSocket is ready
const isSocketReady = () => {
  return socket && socket.readyState === WebSocket.OPEN;
};

const toggleTime = () => {
  if (!isSocketReady()) {
    console.warn('WebSocket not ready, cannot toggle time');
    return;
  }
  const action = isRunning.value ? 'stop' : 'start';
  socket!.send(JSON.stringify({ action }));
  isRunning.value = !isRunning.value;
};

const setTimeScale = (scale: number) => {
  if (!isSocketReady()) {
    console.warn('WebSocket not ready, cannot set time scale');
    return;
  }
  currentScale.value = scale;
  socket!.send(JSON.stringify({ action: 'set_time_scale', scale }));
};

const sendPlayerAction = (content: string, targetId: string | null = null) => {
  if (!isSocketReady()) {
    console.warn('WebSocket not ready, cannot send player action');
    return;
  }
  
  const payload = {
    action: 'player_action',
    content: content,
    target_npc_id: targetId,
    location: selectedLocation.value // Add location context
  };
  
  socket!.send(JSON.stringify(payload));
};

const sendPlayerMessage = () => {
  if (!isSocketReady() || !playerInput.value.trim()) return;
  
  sendPlayerAction(playerInput.value.trim(), selectedNpcId.value);
  playerInput.value = "";
};

const handleStateChange = (targetLoc: string | null, targetNpcId: string | null) => {
  const oldLoc = selectedLocation.value;
  const newLoc = targetLoc;

  // Location Change Logic
  if (oldLoc !== newLoc) {
    if (oldLoc && !newLoc) {
      // Leaving current location
      sendPlayerAction(`*离开了 📍 ${oldLoc}*`);
    } else if (!oldLoc && newLoc) {
      // Entering new location
      sendPlayerAction(`*进入了 📍 ${newLoc}*`);
    } else if (oldLoc && newLoc) {
      // Moving from one location to another
      sendPlayerAction(`*离开了 📍 ${oldLoc}，来到了 📍 ${newLoc}*`);
    }
  }

  // Update State
  selectedLocation.value = newLoc;
  selectedNpcId.value = targetNpcId;
};

const selectNpc = (npcId: string) => {
  // Logic:
  // 1. Click NPC -> Always select that NPC
  // 2. If NPC is in a different location -> Trigger Move Event
  // 3. If clicking same NPC -> Deselect NPC, but KEEP Location
  
  if (selectedNpcId.value === npcId) {
    // Deselect NPC, stay in location
    handleStateChange(selectedLocation.value, null);
  } else {
    // Select new NPC
    const npc = store.npcs.find(n => n.id === npcId);
    if (npc) {
      const npcLoc = npc.dynamic.current_location;
      handleStateChange(npcLoc, npcId);
    }
  }
};

const selectLocation = (location: string) => {
  // Logic:
  // 1. Click Location -> Select Location
  // 2. If Location is different -> Trigger Move Event
  // 3. If clicking same Location -> Deselect Location (Leave)
  
  if (selectedLocation.value === location) {
    // Leave location
    handleStateChange(null, null);
  } else {
    // Enter/Move to location
    handleStateChange(location, null);
  }
};

const loadMoreEvents = () => {
  if (!isSocketReady() || events.value.length === 0) return;
  const firstEvent = events.value[0];
  socket!.send(JSON.stringify({
    action: 'load_history',
    before_timestamp: firstEvent.timestamp
  }));
};

const parseContent = (content: string): ParsedContent[] => {
  const textToParse = content.includes(':') 
    ? content.substring(content.indexOf(':') + 1) 
    : content;

  const parts = textToParse.split(/(\*[^*]+\*)/g);
  return parts
    .map(part => {
      const isAction = part.startsWith('*') && part.endsWith('*');
      const cleanText = isAction ? part.slice(1, -1).trim() : part.trim();
      return {
        text: cleanText,
        type: isAction ? 'action' : 'dialogue'
      } as ParsedContent;
    })
    .filter(p => p.text.length > 0);
};

const getNpcName = (id?: string) => {
  if (!id) return 'Unknown';
  if (id === 'player') return '我';
  if (id === 'system') return 'SYSTEM';
  return store.npcs.find(n => n.id === id)?.profile.name || 'Unknown';
};

const handleRestore = (archiveId: string) => {
  // Reload page to refresh everything from server
  window.location.reload();
};

const handleReset = () => {
  // Reload page to refresh everything from server
  window.location.reload();
};

// ==================== Quest Chip 点击处理 ====================
const handleChipClick = (chip: QuestChip) => {
  if (!isSocketReady()) {
    console.warn('WebSocket not ready, cannot handle chip click');
    return;
  }
  
  isChipLoading.value = true;
  
  // 发送 chip_click 事件到后端
  socket!.send(JSON.stringify({
    action: 'chip_click',
    chip_type: chip.type,
    chip_label: chip.label,
    quest_id: chip.quest_id,
    node_id: chip.node_id,
    npc_id: chip.npc_id || activeChipsNpcId.value,
    line_index: chip.line_index,
    item_action: chip.action
  }));
  
  // 如果是拒绝或忽略，清除 chips
  if (chip.type === 'reject' || chip.type === 'ignore') {
    activeChips.value = [];
    activeChipsEventIndex.value = -1;
    isChipLoading.value = false;
  }
};

onMounted(async () => {
  const worldId = route.params.id as string;
  if (!worldId) return;

  // 使用实际的子 stores
  const worldStore = useWorldStore();
  const npcStore = useNpcStore();
  const questStore = useQuestStore();

  if (!store.finalizedWorldBible || store.finalizedWorldBible.world_id !== worldId) {
    try {
      const data = await worldApi.loadWorld(worldId);
      
      // 更新 WorldStore
      worldStore.updateWorldBible(data.world_bible);
      worldStore.finalizedWorldBible = data.world_bible;
      if (data.config) {
        worldStore.updateConfig(data.config);
      }
      
      // 🔧 将 time_config 合并到 finalizedWorldBible
      if (data.time_config && worldStore.finalizedWorldBible) {
        worldStore.finalizedWorldBible.time_config = data.time_config;
      }
      
      // 🔧 将 locations 合并到 scene.locations
      if (data.locations && data.locations.length > 0 && worldStore.finalizedWorldBible?.scene) {
        worldStore.finalizedWorldBible.scene.locations = data.locations.map((loc: any) => loc.name || loc);
      }
      
      // 更新 NpcStore
      npcStore.setNpcs(data.npcs);
      
      // 更新 QuestStore
      questStore.setSchedules(data.schedules || {});
      if (data.quests) {
        questStore.setQuests(data.quests);
      }
      if (data.items) {
        questStore.setItems(data.items);
      }
      if (data.locations) {
        questStore.setLocations(data.locations);
      }
      if (data.time_config) {
        questStore.setTimeConfig(data.time_config);
      }
      
    } catch (e) {
      console.error("Failed to load world", e);
    }
  }
  
  isLoading.value = false;
  connectWebSocket(worldId);
});

onUnmounted(() => {
  if (socket) socket.close();
});
</script>

<template>
  <div class="h-full flex flex-col bg-black text-zinc-300 font-sans relative">
    
    <!-- Initialization Overlay -->
    <Transition name="fade">
      <div v-if="isInitializing" class="absolute inset-0 z-50 flex items-center justify-center bg-gradient-to-br from-black/20 via-zinc-900/20 to-black/20 backdrop-blur-md">
        <div class="text-center">
          <div class="relative mb-8">
            <div class="w-20 h-20 border-4 border-[#d946ef]/20 border-t-[#d946ef] rounded-full animate-spin mx-auto"></div>
            <div class="absolute inset-0 flex items-center justify-center">
              <Loader2 class="w-10 h-10 text-[#d946ef] animate-pulse" />
            </div>
          </div>
          <p class="text-2xl font-bold text-[#d946ef] mb-2 tracking-wider">{{ initStatus }}</p>
          <p class="text-sm text-zinc-500 animate-pulse">请稍候...</p>
        </div>
      </div>
    </Transition>

    <!-- Top Bar -->
    <div class="h-16 bg-zinc-950 border-b border-zinc-800 flex items-center justify-between px-6 shadow-xl z-10">
      <div class="flex items-center gap-4">
        <!-- 世界标题 -->
        <h1 class="text-xl font-bold text-zinc-300 tracking-wide">
          {{ store.finalizedWorldBible?.title || store.finalizedWorldBible?.scene?.name || '未命名世界' }}
        </h1>
        
        <!-- 分隔符 -->
        <span class="text-zinc-700 text-2xl font-thin">|</span>
        
        <!-- 纪元标签 + 时间 + 状态 -->
        <div class="flex items-center gap-3">
          <!-- 纪元标签（可选） -->
          <div v-if="displayYear" class="px-2.5 py-1 bg-[#d946ef]/10 border border-[#d946ef]/30 rounded">
            <span class="text-xs font-bold text-[#d946ef] tracking-wide">{{ displayYear }}</span>
          </div>
          
          <!-- 时间 -->
          <div class="text-base font-bold text-[#d946ef] flex items-center gap-2">
            <Clock class="w-4 h-4" />
            {{ worldTime }}
          </div>
          
          <!-- 状态标签 -->
          <div 
            class="px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-widest border transition-colors"
            :class="isRunning ? 'bg-[#d946ef]/10 border-[#d946ef]/50 text-[#d946ef]' : 'bg-red-500/10 border-red-500/50 text-red-500'"
          >
            {{ isRunning ? 'LIVE' : 'PAUSED' }}
          </div>
        </div>
      </div>
      
      <div class="flex gap-4 items-center">
        <!-- Archive Button -->
        <button 
          @click="showArchiveModal = true"
          class="flex items-center gap-2 bg-zinc-900 hover:bg-zinc-800 border border-zinc-800 hover:border-zinc-700 text-zinc-400 hover:text-[#d946ef] px-3 py-2 rounded-lg transition-all text-xs font-bold"
        >
          <Archive class="w-4 h-4" />
          <span>世界线管理</span>
        </button>

        <div class="h-6 w-px bg-zinc-800"></div>

        <!-- Time Scale Controls -->
        <div class="flex gap-3 items-center">
          <span class="text-xs text-zinc-500">游戏世界1天 =</span>
          <div class="flex bg-zinc-900 rounded-lg p-1 gap-1 border border-zinc-800">
              <button 
                v-for="scale in [1, 6, 24, 60, 1800]"
                :key="scale"
                @click="setTimeScale(scale)" 
                class="px-3 py-1 text-xs rounded transition-all"
                :class="currentScale === scale ? 'bg-[#d946ef] text-black font-bold' : 'hover:bg-zinc-800 text-zinc-500'"
              >
                {{ scale === 1 ? '1天' : scale === 6 ? '4小时' : scale === 24 ? '1小时' : scale === 60 ? '24分钟' : '48秒' }}
              </button>
          </div>
        </div>

        <!-- Play/Pause -->
        <button 
          @click="toggleTime"
          class="w-10 h-10 rounded-full flex items-center justify-center transition-all shadow-[0_0_15px_rgba(0,0,0,0.5)] border border-zinc-700 hover:border-[#d946ef]"
          :class="isRunning ? 'bg-zinc-900 text-red-500' : 'bg-[#d946ef] text-black'"
        >
          <Pause v-if="isRunning" class="w-5 h-5 fill-current" />
          <Play v-else class="w-5 h-5 fill-current ml-0.5" />
        </button>
      </div>
    </div>

    <!-- Main Content -->
    <div v-if="isLoading" class="flex-1 flex items-center justify-center text-[#d946ef]">
      <div class="text-center">
        <Loader2 class="w-10 h-10 animate-spin mx-auto mb-4" />
        <p class="text-sm tracking-widest">LOADING NEURAL LINK...</p>
      </div>
    </div>

    <div v-else class="flex-1 p-6 flex gap-6 overflow-hidden relative">
      <!-- Archive Modal -->
      <ArchiveModal 
        :is-open="showArchiveModal"
        :world-id="store.finalizedWorldBible?.world_id || ''"
        :world-name="store.finalizedWorldBible?.scene?.name"
        @close="showArchiveModal = false"
        @restore="handleRestore"
        @reset="handleReset"
      />

      <!-- Runtime Sidebar -->
      <RuntimeSidebar 
        :active-tab="activePanel"
        @change-view="activePanel = $event"
      />

      <!-- Dynamic Panel Area (50%) -->
      <div class="flex-1 flex flex-col gap-4 overflow-hidden">
        <ResidentsList 
          v-if="activePanel === 'residents'"
          :npcs="store.npcs"
          :selected-npc-id="selectedNpcId"
          :selected-location="selectedLocation"
          :locations="locations"
          @select-npc="selectNpc"
          @select-location="selectLocation"
        />
        <MangaPanel 
          v-if="activePanel === 'manga'"
          :world-id="route.params.id as string"
        />
        <GodModePanel 
          v-if="activePanel === 'godmode'"
          :current-time="currentWorldDate"
        />
        <!-- 未来扩展：其他Panel组件将在这里 -->
      </div>

      <!-- Event Log & Interaction (50%) -->
      <div class="flex-1 flex flex-col gap-4 h-full overflow-hidden">
        <!-- Log -->
        <div class="flex-1 bg-zinc-900/50 rounded-xl border border-zinc-800 p-4 flex flex-col backdrop-blur-sm overflow-hidden relative">
          
          <!-- Header -->
          <h3 class="font-bold text-zinc-500 mb-4 text-xs uppercase tracking-widest flex items-center gap-2">
            <History class="w-4 h-4" /> 世界事件 WORLD EVENTS
          </h3>
          
          <div ref="logContainer" class="flex-1 overflow-y-auto space-y-4 custom-scrollbar pr-2">
            
            <!-- Load More Button -->
            <div v-if="events.length > 0" class="text-center py-2">
               <button @click="loadMoreEvents" class="text-xs text-zinc-600 hover:text-[#d946ef] transition-colors">
                 Load older events...
               </button>
            </div>

            <div v-if="events.length === 0" class="text-zinc-600 text-center py-10">
              <History class="w-8 h-8 mx-auto mb-2 opacity-50" />
              Waiting for events...
            </div>

            <div v-for="(event, i) in events" :key="i" class="animate-fade-in group">
              <!-- Using items-baseline for perfect alignment between Time and Name -->
              <div class="flex gap-4 items-baseline">
                <!-- Timestamp -->
                <div class="flex-shrink-0 w-12 text-right">
                  <span v-if="event.game_time" class="text-sm font-mono text-zinc-600 group-hover:text-zinc-500 transition-colors">
                    {{ event.game_time }}
                  </span>
                </div>
                
                <div class="flex-1 pb-3 border-b border-zinc-800/30 last:border-0">
                  
                  <!-- 1. Player Interaction -->
                  <div v-if="event.category === 'player_interaction'" class="text-sm">
                    <!-- A. 移动事件 (进入/离开) - 极简系统风 -->
                    <template v-if="event.source === 'player' && (event.content.startsWith('*进入了') || event.content.startsWith('*离开了'))">
                      <div class="text-zinc-500">
                        我 {{ event.content.replace(/\*/g, '').replace(/📍/g, '').trim() }}
                      </div>
                    </template>

                    <!-- C. 区域广播 (我 -> All) - 酸性蓝风格 -->
                    <template v-else-if="event.target === 'all' && event.source === 'player'">
                      <div class="flex items-center gap-2 mb-1 text-sm font-bold text-[#00f0ff] uppercase tracking-wide">
                        <span>我</span>
                        <template v-if="event.metadata?.location">
                          <MapPin class="w-3 h-3 ml-1" />
                          <span>{{ event.metadata.location }}</span>
                        </template>
                      </div>
                      <div class="space-y-1">
                         <p class="text-[#00f0ff]">{{ event.content }}</p>
                      </div>
                    </template>

                    <!-- B. 私聊事件 (我 -> NPC) -->
                    <template v-else-if="event.source === 'player'">
                      <div class="flex items-center gap-2 mb-1 text-sm font-bold text-[#d946ef] uppercase tracking-wide">
                        <span>我</span>
                        <ArrowRight class="w-4 h-4 text-zinc-700" />
                        <span>{{ getNpcName(event.target) }}</span>
                        <template v-if="event.metadata?.location">
                          <MapPin class="w-3 h-3 ml-2 text-zinc-700" />
                          <span class="text-zinc-500 text-xs font-normal">{{ event.metadata.location }}</span>
                        </template>
                      </div>
                      <!-- Content -->
                      <div class="space-y-1">
                        <div v-for="(part, idx) in parseContent(event.content)" :key="idx">
                          <p v-if="part.type === 'action'" class="text-zinc-400 block mb-1">{{ part.text }}</p>
                          <p v-else class="text-[#d946ef]">{{ part.text }}</p>
                        </div>
                      </div>
                    </template>

                    <!-- D. NPC 回复 (NPC -> 我) -->
                    <template v-else>
                      <div class="flex items-center gap-2 mb-1 text-sm font-bold text-[#d946ef] uppercase tracking-wide">
                        <span>{{ getNpcName(event.source) }}</span>
                        <ArrowRight class="w-4 h-4 text-zinc-700" />
                        <span>{{ getNpcName(event.target) }}</span>
                        <template v-if="event.metadata?.location">
                          <MapPin class="w-3 h-3 ml-2 text-zinc-700" />
                          <span class="text-zinc-500 text-xs font-normal">{{ event.metadata.location }}</span>
                        </template>
                      </div>
                      <!-- Content -->
                      <div class="space-y-1">
                        <div v-for="(part, idx) in parseContent(event.content)" :key="idx">
                          <p v-if="part.type === 'action'" class="text-zinc-400 block mb-1">{{ part.text }}</p>
                          <p v-else class="text-[#d946ef]">{{ part.text }}</p>
                        </div>
                      </div>
                    </template>
                  </div>

                  <!-- 2. Social -->
                  <div v-else-if="event.category === 'social'" class="text-sm">
                    <div class="flex items-center gap-2 mb-1 text-sm font-bold text-amber-400 uppercase tracking-wide">
                      <span>{{ getNpcName(event.source) }}</span>
                      
                      <!-- Target Logic: Show arrow only if target exists, is not 'all', and is not self -->
                      <template v-if="event.target && event.target !== 'all' && event.target !== event.source">
                        <ArrowRight class="w-4 h-4 text-zinc-700" />
                        <!-- Handle Extra vs NPC -->
                        <span v-if="event.target === 'extra'">{{ event.metadata?.target_name || '路人' }}</span>
                        <span v-else>{{ getNpcName(event.target) }}</span>
                      </template>

                      <template v-if="event.metadata?.location">
                        <MapPin class="w-3 h-3 ml-2 text-zinc-700" />
                        <span class="text-zinc-500 text-xs font-normal">{{ event.metadata.location }}</span>
                      </template>
                    </div>
                    <!-- Content -->
                    <div class="space-y-1">
                      <div v-for="(part, idx) in parseContent(event.content)" :key="idx">
                        <p v-if="part.type === 'action'" class="text-zinc-400 block mb-1">{{ part.text }}</p>
                        <p v-else class="text-amber-400">{{ part.text }}</p>
                      </div>
                    </div>
                  </div>

                  <!-- 3. Action -->
                  <div v-else-if="event.category === 'action'" class="text-sm">
                    <div class="flex items-center gap-2 mb-1 text-sm font-bold text-emerald-400 uppercase tracking-wide">
                      <span>{{ getNpcName(event.source) }}</span>
                      <template v-if="event.metadata?.location">
                        <MapPin class="w-3 h-3 ml-2 text-zinc-700" />
                        <span class="text-zinc-500 text-xs font-normal">{{ event.metadata.location }}</span>
                      </template>
                    </div>
                    <p class="text-emerald-400">{{ event.content }}</p>
                  </div>

                  <!-- 4. Dialogue Flow (任务对话流 - 紫色风格，同 player_interaction) -->
                  <div v-else-if="event.category === 'dialogue_flow'" class="text-sm">
                    <div class="flex items-center gap-2 mb-1 text-sm font-bold text-[#d946ef] uppercase tracking-wide">
                      <span>{{ getNpcName(event.source) }}</span>
                      <ArrowRight class="w-4 h-4 text-zinc-700" />
                      <span>我</span>
                      <template v-if="event.metadata?.location">
                        <MapPin class="w-3 h-3 ml-2 text-zinc-700" />
                        <span class="text-zinc-500 text-xs font-normal">{{ event.metadata.location }}</span>
                      </template>
                    </div>
                    <!-- Content -->
                    <div class="space-y-1">
                      <div v-for="(part, idx) in parseContent(event.content)" :key="idx">
                        <p v-if="part.type === 'action'" class="text-zinc-400 block mb-1">{{ part.text }}</p>
                        <p v-else class="text-[#d946ef]">{{ part.text }}</p>
                      </div>
                    </div>
                  </div>

                  <!-- 5. Item Action (物品交互 - 琥珀色风格) -->
                  <div v-else-if="event.category === 'item_action'" class="text-sm">
                    <p class="text-amber-400">{{ event.content }}</p>
                  </div>

                  <!-- 6. Quest Update (任务更新 - 系统风格) -->
                  <div v-else-if="event.category === 'quest_update'" class="text-sm">
                    <p class="text-[#ccff00] font-bold">{{ event.content }}</p>
                  </div>

                  <!-- 7. System -->
                  <div v-else class="text-sm" :class="event.metadata?.type === 'objective' ? 'text-[#ccff00] font-bold tracking-wide' : 'text-zinc-500'">
                    {{ event.content }}
                  </div>
                </div>
              </div>
            </div>
            
            <!-- ==================== Quest Chips 显示区域 ==================== -->
            <QuestChips
              v-if="activeChips.length > 0"
              :chips="activeChips"
              :npc-id="activeChipsNpcId"
              :npc-name="getNpcName(activeChipsNpcId)"
              :is-loading="isChipLoading"
              @chip-click="handleChipClick"
            />
          </div>
        </div>
        
        <!-- Input Area -->
        <div class="bg-zinc-950 rounded-xl border border-zinc-800 p-4 shadow-lg">
          <div v-if="selectedNpcId" class="text-xs text-[#d946ef] mb-2 flex items-center gap-2 font-bold">
            <span class="w-2 h-2 rounded-full bg-[#d946ef] animate-pulse"></span>
            对 {{ store.npcs.find(n => n.id === selectedNpcId)?.profile.name }} 说 <MapPin class="w-3 h-3 inline mx-1" /> {{ selectedLocation }}
          </div>
          <div v-else-if="selectedLocation" class="text-xs text-[#d946ef] mb-2 flex items-center gap-2 font-bold">
            <span class="w-2 h-2 rounded-full bg-[#d946ef]"></span>
            在 <MapPin class="w-3 h-3 inline mx-1" /> {{ selectedLocation }} 说
          </div>
          <div v-else class="text-xs text-zinc-500 mb-2 flex items-center gap-2">
            <span class="w-2 h-2 rounded-full bg-zinc-700"></span>
            世界频道
          </div>

          <div class="flex gap-3">
            <input 
              v-model="playerInput"
              @keyup.enter="sendPlayerMessage"
              type="text" 
              :placeholder="selectedNpcId ? `对 ${store.npcs.find(n => n.id === selectedNpcId)?.profile.name} 说...` : (selectedLocation ? `在 ${selectedLocation} 说...` : '在世界频道发言...')"
              class="flex-1 bg-zinc-900 border border-zinc-800 rounded-lg px-4 py-3 text-zinc-200 focus:outline-none focus:border-[#d946ef] transition-colors placeholder-zinc-600"
            />
            <button 
              @click="sendPlayerMessage"
              class="bg-[#d946ef] hover:bg-[#c026d3] text-black px-6 py-2 rounded-lg font-bold transition-all shadow-[0_0_10px_rgba(217,70,239,0.2)] hover:shadow-[0_0_15px_rgba(217,70,239,0.4)] flex items-center gap-2"
            >
              <Send class="w-4 h-4" />
              <span>SEND</span>
            </button>
          </div>
        </div>
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

.animate-fade-in {
  animation: fadeIn 0.3s ease-out forwards;
}

@keyframes fadeIn {
  from { opacity: 0; transform: translateY(5px); }
  to { opacity: 1; transform: translateY(0); }
}

/* Fade transition for initialization overlay */
.fade-enter-active {
  transition: opacity 0.5s ease;
}

.fade-leave-active {
  transition: opacity 0.8s ease;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}
</style>

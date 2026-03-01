<script setup lang="ts">
import { useGenesisStore } from '../stores/genesis';
import { useWorldStore } from '../stores/genesis/world';
import { useNpcStore } from '../stores/genesis/npc';
import { useUIStore } from '../stores/ui';
import { computed, ref } from 'vue';
import { useRouter } from 'vue-router';
import { Users, Rocket, Zap, User, Star, Loader2, RefreshCw, X, MessageSquarePlus, AlertTriangle, Lock, SlidersHorizontal, Image as ImageIcon, Pencil, Upload, Save, CheckCircle2 } from 'lucide-vue-next';
import worldApi from '../api/world';

const store = useGenesisStore();
const worldStore = useWorldStore();
const npcStore = useNpcStore();
const uiStore = useUIStore();
const router = useRouter();
const emit = defineEmits(['generated']);
const npcs = computed(() => store.npcs);

const showConfigModal = ref(false);

const PRESETS = {
  default: "Japanese manga style, anime art style, vibrant colors, detailed character design, high quality illustration",
  realistic: "Cinematic lighting, photorealistic, 8k resolution, movie still, realistic texture, highly detailed face, depth of field",
  disney: "Disney style, 3D animation, Pixar art style, cute features, expressive eyes, vibrant colors, soft lighting, 3d render",
  game: "Unreal Engine 5 render, 3A game character, highly detailed, concept art, fantasy style, digital painting, sharp focus"
};

const toggleConfigModal = () => {
  // Ensure default style if empty when opening
  if (showConfigModal.value === false && !store.worldConfig.image_style) {
      store.worldConfig.image_style = PRESETS.default;
  }
  showConfigModal.value = !showConfigModal.value;
};

const saveConfig = async () => {
    if (worldStore.finalizedWorldBible?.world_id) {
        try {
            await worldApi.updateConfig(worldStore.finalizedWorldBible.world_id, store.worldConfig);
        } catch (e) {
            console.error("Failed to save config", e);
        }
    }
};

const setStyle = (key: keyof typeof PRESETS) => {
    store.worldConfig.image_style = PRESETS[key];
    saveConfig();
};

const isFinalized = computed(() => ['quest', 'launch'].includes(store.currentStep));

const confirmRoster = async () => {
  const confirmed = await uiStore.openModal(
    '确认居民名册',
    '确认居民名册定稿吗？确认后将不可新增或删除居民。确认后将进入第三阶段：任务蓝图 (Quest Blueprint)。',
    'confirm'
  );

  if (confirmed && worldStore.finalizedWorldBible?.world_id) {
    // 调用后端确认 Roster，生成摘要
    const genesisApi = (await import('../api/genesis')).default;
    await genesisApi.executeConfirmRoster(worldStore.finalizedWorldBible.world_id);
    
    // 刷新数据以获取生成的摘要消息
    await store.refreshWorld();

    // 保存 roster_confirmed 状态
    store.worldConfig.roster_confirmed = true;
    const worldApi = (await import('../api/world')).default;
    await worldApi.updateConfig(worldStore.finalizedWorldBible.world_id, store.worldConfig);
    
    // 切换到 quest 阶段，但不立即生成任务
    store.currentStep = 'quest';
    // Agent 会在 Quest 阶段询问用户需求
  }
};

// Check if all NPCs are complete or still generating (no failures)
const allNpcsComplete = computed(() => {
  if (npcs.value.length === 0) return false;
  return npcs.value.every(npc => 
    (npc.quest_role && npc.goals && npc.goals.length > 0 && npc.skills && npc.skills.length > 0) || // 已完成
    !npc._incomplete  // 或者正在生成中（未标记失败）
  );
});

// Count only truly failed NPCs (with _incomplete flag)
const failedCount = computed(() => {
  return npcs.value.filter(npc => npc._incomplete).length;
});

const showGenerationModal = ref(false);
const generationRequirements = ref('');
const generationCount = ref(3);
const retryingNpcId = ref<string | null>(null);

const openGenerationModal = () => {
  generationRequirements.value = ''; // Reset
  // Keep previous count or reset? Resetting to 3 is safer.
  generationCount.value = 3; 
  showGenerationModal.value = true;
};

const closeGenerationModal = () => {
  showGenerationModal.value = false;
};

const confirmGeneration = async () => {
  closeGenerationModal();
  await store.generateNPCs(generationRequirements.value, generationCount.value);
  emit('generated');
};

const retryNPC = async (npcId: string) => {
  try {
    retryingNpcId.value = npcId;
    await npcStore.regenerateNPC(npcId);
  } catch (error) {
    console.error('Failed to regenerate NPC:', error);
  } finally {
    retryingNpcId.value = null;
  }
};

const handleFullGeneration = () => {
  store.enableIllustratedMode(true);
  showConfigModal.value = false;
};

// Edit Modal Logic
const editingNpc = ref<any>(null);
const editDescription = ref('');
const isUploading = ref(false);
const fileInput = ref<HTMLInputElement | null>(null);

const openEditModal = (npc: any) => {
  editingNpc.value = npc;
  editDescription.value = npc.profile.avatar_desc || '';
};

const closeEditModal = () => {
  editingNpc.value = null;
  editDescription.value = '';
};

const saveDescription = async () => {
  if (!editingNpc.value) return;
  try {
    await npcStore.updateNPCProfile(editingNpc.value.id, editDescription.value);
    closeEditModal();
  } catch (e) {
    console.error("Failed to save description", e);
  }
};

const triggerFileUpload = () => {
  fileInput.value?.click();
};

const handleFileChange = async (event: Event) => {
  const input = event.target as HTMLInputElement;
  if (input.files && input.files[0] && editingNpc.value) {
    const file = input.files[0];
    isUploading.value = true;
    try {
      await npcStore.uploadAvatar(editingNpc.value.id, file);
    } catch (e) {
      console.error("Failed to upload file", e);
    } finally {
      isUploading.value = false;
      input.value = ''; // Reset
    }
  }
};
</script>

<template>
  <div class="h-full bg-zinc-900 rounded-lg shadow-xl border border-zinc-800 flex flex-col overflow-hidden">
    <!-- Header / Action Bar -->
    <div v-if="worldStore.finalizedWorldBible?.scene?.locations?.length || failedCount > 0" class="p-4 bg-zinc-950 shadow-sm flex flex-col gap-4 border-b border-zinc-800">
      
      <!-- Warning if NPCs failed -->
      <div v-if="failedCount > 0" class="flex items-center gap-2 text-xs text-yellow-500">
        <AlertTriangle class="w-4 h-4" />
        <span>{{ failedCount }} 个NPC生成失败，请重新生成</span>
      </div>

      <!-- Public Info: Locations -->
      <div v-if="worldStore.finalizedWorldBible?.scene?.locations?.length" class="bg-zinc-900 p-3 rounded-lg border border-zinc-800">
        <span class="text-xs font-bold text-zinc-500 uppercase mr-2">公共区域</span>
        <div class="flex flex-wrap gap-2 mt-1">
          <span 
            v-for="(loc, i) in worldStore.finalizedWorldBible.scene.locations" 
            :key="i"
            class="px-2 py-1 bg-zinc-800 border border-zinc-700 rounded-md text-xs text-zinc-400 shadow-sm"
          >
            {{ loc }}
          </span>
        </div>
      </div>
    </div>

    <!-- Content -->
    <div class="flex-1 min-h-0 overflow-y-auto custom-scrollbar p-4 grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 bg-zinc-950/50">
      <div 
        v-for="npc in npcs" 
        :key="npc.id" 
        class="bg-zinc-900 rounded-lg shadow-md hover:shadow-lg hover:border-[#d946ef]/50 transition-all border border-zinc-800 group"
      >
        <!-- Card Header -->
        <div class="bg-zinc-900 rounded-t-lg p-3 border-b border-zinc-800 flex flex-col items-start gap-1 group-hover:bg-zinc-800/50 transition-colors">
          <div class="flex items-center gap-2 flex-wrap">
            <h3 class="font-bold text-lg text-zinc-200 group-hover:text-[#d946ef] transition-colors leading-tight">{{ npc.profile.name }}</h3>
            <span class="text-[10px] px-1.5 py-0.5 bg-zinc-950 text-zinc-400 rounded border border-zinc-800 shrink-0">
              {{ npc.profile.race }}
            </span>
          </div>
          <p class="text-xs text-zinc-500">{{ npc.profile.occupation }} | {{ npc.profile.gender }} | {{ npc.profile.age }}岁</p>
        </div>

        <!-- NPC Image (Illustrated Mode) -->
        <div v-if="store.isIllustratedMode" class="w-full bg-black/20 border-b border-zinc-800 relative">
          <div v-if="npc.profile.avatar_url" class="relative group/image overflow-hidden aspect-[9/16]">
            <img 
              :src="npc.profile.avatar_url" 
              alt="NPC Portrait" 
              class="w-full h-full object-cover object-top hover:scale-105 transition-transform duration-700"
            />
            <div class="absolute inset-0 bg-gradient-to-t from-zinc-900 via-transparent to-transparent opacity-60"></div>
            
            <!-- Edit Button -->
            <button 
              @click.stop="openEditModal(npc)"
              class="absolute bottom-3 right-14 p-2 bg-black/50 backdrop-blur-md rounded-full text-zinc-300 hover:text-white hover:bg-[#d946ef] transition-all opacity-0 group-hover/image:opacity-100 transform translate-y-2 group-hover/image:translate-y-0"
              title="编辑立绘设定"
            >
              <Pencil class="w-4 h-4" />
            </button>

            <!-- Regenerate Button -->
            <button 
              @click.stop="npcStore.generateNPCImage(npc.id)"
              :disabled="store.generatingNpcIds.includes(npc.id) || store.queuedNpcIds.includes(npc.id)"
              class="absolute bottom-3 right-3 p-2 bg-black/50 backdrop-blur-md rounded-full text-zinc-300 hover:text-white hover:bg-[#d946ef] transition-all opacity-0 group-hover/image:opacity-100 transform translate-y-2 group-hover/image:translate-y-0 disabled:opacity-100 disabled:cursor-wait"
              title="重新生成立绘"
            >
              <Loader2 v-if="store.generatingNpcIds.includes(npc.id)" class="w-4 h-4 animate-spin" />
              <RefreshCw v-else class="w-4 h-4" />
            </button>
          </div>
          <div v-else class="aspect-[9/16] flex flex-col items-center justify-center text-zinc-600 bg-zinc-950/30 gap-3 group/placeholder cursor-pointer hover:bg-zinc-950/50 transition-colors" @click="npcStore.generateNPCImage(npc.id)">
             <template v-if="npc._imageError">
                <AlertTriangle class="w-8 h-8 text-red-500 mb-1" />
                <span class="text-xs text-red-500 font-bold">生成失败</span>
                <span class="text-[10px] text-zinc-500 group-hover/placeholder:text-zinc-300 transition-colors">点击重试</span>
             </template>
             <template v-else>
                <ImageIcon class="w-8 h-8 opacity-20 group-hover/placeholder:opacity-50 group-hover/placeholder:text-[#d946ef] transition-all" />
                <span class="text-xs opacity-50 group-hover/placeholder:text-[#d946ef] transition-colors">点击生成立绘</span>
             </template>
          </div>

          <!-- Generation Status Overlay -->
          <div 
            v-if="store.generatingNpcIds.includes(npc.id) || store.queuedNpcIds.includes(npc.id)"
            class="absolute inset-0 z-20 flex flex-col items-center justify-center bg-black/70 backdrop-blur-sm transition-all"
          >
             <Loader2 v-if="store.generatingNpcIds.includes(npc.id)" class="w-8 h-8 animate-spin text-[#d946ef] mb-3" />
             <div v-else class="w-8 h-8 rounded-full border-2 border-zinc-600 border-t-zinc-400 animate-spin mb-3 opacity-50"></div>
             
             <span class="text-sm font-bold text-white tracking-wide mb-1">
               {{ store.generatingNpcIds.includes(npc.id) ? '正在生成' : '排队中' }}
             </span>
             <span class="text-[10px] text-zinc-400 font-medium">请勿关闭页面 一会就好</span>
          </div>
        </div>

        <!-- Body -->
        <div class="p-4 space-y-6">
          <!-- Personality -->
          <div class="text-sm text-zinc-400 leading-relaxed">
            {{ npc.dynamic.personality_desc }}
          </div>

          <div v-if="!npc.quest_role && !npc._incomplete" class="py-8 flex flex-col items-center justify-center text-zinc-600 animate-pulse">
            <User class="w-8 h-8 mb-2 opacity-50" />
            <span class="text-xs">正在构建思维模型...</span>
          </div>
          <div v-else-if="!npc.quest_role && npc._incomplete" class="py-8 flex flex-col items-center justify-center gap-3">
            <AlertTriangle class="w-8 h-8 text-yellow-500" />
            <span class="text-xs text-zinc-400">生成失败或未完成</span>
            <button
              @click="retryNPC(npc.id)"
              :disabled="retryingNpcId === npc.id"
              class="px-3 py-1.5 bg-[#d946ef] hover:bg-[#c026d3] text-black text-xs rounded-md flex items-center gap-1.5 transition-all font-bold shadow-[0_0_10px_rgba(217,70,239,0.3)] hover:shadow-[0_0_15px_rgba(217,70,239,0.5)] disabled:opacity-70 disabled:cursor-not-allowed"
            >
              <Loader2 v-if="retryingNpcId === npc.id" class="w-3 h-3 animate-spin" />
              <RefreshCw v-else class="w-3 h-3" />
              <span>{{ retryingNpcId === npc.id ? '重试中...' : '重试生成' }}</span>
            </button>
          </div>
          <div v-else class="space-y-6 animate-fade-in">
            <!-- Goals -->
            <div>
                <div class="text-xs font-bold text-zinc-600 uppercase mb-2">目标 GOALS</div>
                <ul class="space-y-3">
                <li 
                    v-for="goal in npc.goals" 
                    :key="goal.id"
                    class="text-sm flex items-start gap-2 leading-snug"
                >
                    <Star class="w-4 h-4 mt-0.5 flex-shrink-0" :class="goal.type === 'main' ? 'text-[#d946ef] fill-[#d946ef]' : 'text-zinc-700'" />
                    <span :class="goal.type === 'main' ? 'font-bold text-zinc-200' : 'text-zinc-400'">
                    {{ goal.description }}
                    </span>
                </li>
                </ul>
            </div>

            <!-- Skills -->
            <div>
                <div class="text-xs font-bold text-zinc-600 uppercase mb-2">技能 SKILLS</div>
                <div class="flex flex-wrap gap-2">
                <span 
                    v-for="(skill, i) in npc.skills" 
                    :key="i"
                    class="text-xs bg-zinc-950 text-zinc-300 px-3 py-1.5 rounded-md border border-zinc-700"
                >
                    {{ skill.name }} <span class="text-zinc-500 ml-1">Lv.{{ skill.level }}</span>
                </span>
                </div>
            </div>

            <!-- Quest Role -->
            <div v-if="npc.quest_role" class="bg-zinc-950 p-3 rounded-md border border-zinc-800">
                <div class="flex justify-between items-center mb-2">
                    <span class="text-xs font-bold text-indigo-400 uppercase">角色定位 QUEST ROLE</span>
                    <span 
                        class="text-[10px] px-1.5 py-0.5 rounded text-black uppercase font-bold"
                        :class="{
                            'bg-[#ccff00]': npc.quest_role.role === 'helper',
                            'bg-red-500 text-white': npc.quest_role.role === 'blocker',
                            'bg-zinc-600 text-white': npc.quest_role.role === 'neutral'
                        }"
                    >{{ npc.quest_role.role }}</span>
                </div>
                <p class="text-xs text-zinc-400 leading-relaxed">{{ npc.quest_role.clue }}</p>
            </div>
          </div>
        </div>
      </div>
      
      <!-- Empty State -->
      <div v-if="npcs.length === 0 && !store.isLoading" class="col-span-full flex flex-col items-center justify-center text-zinc-600 py-12">
        <Users class="w-12 h-12 mb-2 opacity-20" />
        <p>尚未生成任何居民</p>
        <p class="text-sm opacity-50">点击下方按钮唤醒塑造者 Agent</p>
      </div>

       <!-- Loading Skeleton -->
       <div v-if="store.isLoading && npcs.length === 0" class="col-span-full flex flex-col items-center justify-center text-[#d946ef] py-12">
        <RefreshCw class="w-10 h-10 mb-2 animate-spin" />
        <p>塑造者正在捏人中...</p>
        <p class="text-xs mt-2 text-zinc-500">正在根据世界设定计算性格与动机</p>
      </div>

    </div>

    <!-- Action Footer -->
    <div v-if="!isFinalized" class="p-4 bg-zinc-950 border-t border-zinc-800 flex justify-between items-center">
       <div class="flex items-center gap-3">
          <div class="flex items-center gap-2 px-4 py-3 bg-zinc-900 rounded-lg border border-zinc-800 h-full mr-2">
             <Users class="w-4 h-4 text-[#d946ef]" />
             <span class="text-sm font-bold text-zinc-400">Total: <span class="text-zinc-200">{{ npcs.length }}</span></span>
          </div>
          
            <button 
                @click="toggleConfigModal"
                class="flex items-center gap-2 px-4 py-3 rounded-lg bg-zinc-900 border border-zinc-800 text-[#d946ef] hover:bg-[#d946ef]/10 transition-colors text-sm font-bold"
            >
                <ImageIcon class="w-4 h-4" />
                <span>立绘设置</span>
            </button>

          <button 
            @click="openGenerationModal"
            :disabled="store.isLoading || store.isLocked"
            class="flex items-center gap-2 px-4 py-3 rounded-lg bg-zinc-900 border border-zinc-800 text-zinc-400 hover:text-zinc-200 transition-colors text-sm font-bold disabled:opacity-50 disabled:cursor-not-allowed"
          >
             <RefreshCw class="w-4 h-4" />
             <span>重新生成</span>
          </button>
       </div>

       <button 
          @click="confirmRoster"
          :disabled="store.isLoading || npcs.length === 0"
          class="bg-[#d946ef] hover:bg-[#c026d3] text-black px-4 py-3 rounded-lg flex items-center gap-2 transition-all font-bold shadow-[0_0_10px_rgba(217,70,239,0.3)] hover:shadow-[0_0_15px_rgba(217,70,239,0.5)] disabled:opacity-50 disabled:cursor-not-allowed"
       >
          <CheckCircle2 class="w-4 h-4" />
          <span>确认居民名册定稿</span>
       </button>
    </div>
    
    <!-- Finalized Footer -->
    <div v-else class="p-4 bg-zinc-950 border-t border-zinc-800 flex justify-between items-center">
        <div class="flex items-center gap-3">
            <div class="flex items-center gap-2 px-4 py-3 bg-zinc-900 rounded-lg border border-zinc-800 h-full mr-2">
                <Users class="w-4 h-4 text-[#d946ef]" />
                <span class="text-sm font-bold text-zinc-400">Total: <span class="text-zinc-200">{{ npcs.length }}</span></span>
            </div>
            <button 
                @click="toggleConfigModal"
                class="flex items-center gap-2 px-4 py-3 rounded-lg bg-zinc-900 border border-zinc-800 text-[#d946ef] hover:bg-[#d946ef]/10 transition-colors text-sm font-bold"
            >
                <ImageIcon class="w-4 h-4" />
                <span>立绘设置</span>
            </button>
        </div>
        
        <div class="text-[#d946ef] font-extrabold flex items-center gap-2 px-4 py-3 bg-zinc-900/50 rounded-lg border border-zinc-800">
            <CheckCircle2 class="w-5 h-5" />
            <span>定稿</span>
        </div>
    </div>

  </div>

  <!-- Global Config Modal -->
  <Teleport to="body">
    <Transition name="modal">
      <div v-if="showConfigModal" class="fixed inset-0 z-[100] flex items-center justify-center p-4">
        <div class="absolute inset-0 bg-black/80 backdrop-blur-sm" @click="showConfigModal = false"></div>
        
        <div class="relative w-full max-w-lg bg-zinc-900 border border-zinc-800 rounded-lg shadow-2xl overflow-hidden transform transition-all">
          <button @click="showConfigModal = false" class="absolute top-4 right-4 text-zinc-500 hover:text-[#d946ef] transition-colors z-10">
            <X class="w-5 h-5" />
          </button>

          <div class="p-6">
            <div class="flex items-center gap-3 mb-6">
              <div class="w-10 h-10 rounded-full bg-[#d946ef]/10 border border-[#d946ef]/50 text-[#d946ef] flex items-center justify-center">
                <ImageIcon class="w-5 h-5" />
              </div>
              <h3 class="text-xl font-bold text-zinc-100">立绘设置</h3>
            </div>

            <div class="bg-zinc-950/50 rounded-lg border border-zinc-800 p-4 flex flex-col gap-4">
               <!-- Toggle -->
               <div class="flex items-center justify-between">
                  <div class="flex items-center gap-3">
                    <div class="p-2 rounded-full bg-[#d946ef]/10 text-[#d946ef]">
                      <ImageIcon class="w-5 h-5" />
                    </div>
                    <div>
                      <h4 class="font-bold text-zinc-200">启用立绘</h4>
                      <p class="text-xs text-zinc-500">为所有 NPC 生成 16:9 的角色立绘</p>
                    </div>
                  </div>
                  <!-- Switch -->
                  <div 
                    @click="store.toggleIllustratedMode(!store.worldConfig.is_illustrated)"
                    class="w-10 h-6 rounded-full p-1 transition-all duration-300 cursor-pointer relative"
                    :class="store.worldConfig.is_illustrated ? 'bg-[#d946ef]' : 'bg-zinc-800'"
                  >
                    <div 
                      class="w-4 h-4 rounded-full bg-white shadow-md transform transition-transform duration-300 absolute top-1"
                      :class="store.worldConfig.is_illustrated ? 'translate-x-4' : 'translate-x-0 bg-zinc-500'"
                    ></div>
                  </div>
               </div>

               <!-- Prompt Input and Generate Action -->
               <div class="pt-4 border-t border-zinc-800/50 space-y-3 transition-opacity duration-300" :class="{'opacity-50 pointer-events-none grayscale': !store.worldConfig.is_illustrated}">
                  <div>
                    <label class="text-xs font-bold text-zinc-500 uppercase mb-1 block">风格设定 STYLE PROMPT</label>
                    <textarea 
                      v-model="store.worldConfig.image_style"
                      @change="saveConfig"
                      class="w-full bg-zinc-900 border border-zinc-700 rounded p-2 text-xs text-zinc-300 resize-none h-24 focus:outline-none focus:border-[#d946ef] leading-relaxed"
                      placeholder="Enter style keywords..."
                    ></textarea>
                  </div>

                  <div class="grid grid-cols-2 gap-2 mb-2">
                    <button @click="setStyle('default')" class="bg-zinc-800 hover:bg-zinc-700 text-zinc-400 text-xs py-2 rounded font-bold transition-colors">日式漫画（默认）</button>
                    <button @click="setStyle('realistic')" class="bg-zinc-800 hover:bg-zinc-700 text-zinc-400 text-xs py-2 rounded font-bold transition-colors">写实电影风</button>
                    <button @click="setStyle('disney')" class="bg-zinc-800 hover:bg-zinc-700 text-zinc-400 text-xs py-2 rounded font-bold transition-colors">迪斯尼3D</button>
                    <button @click="setStyle('game')" class="bg-zinc-800 hover:bg-zinc-700 text-zinc-400 text-xs py-2 rounded font-bold transition-colors">3A游戏风</button>
                  </div>

                  <button 
                    @click="handleFullGeneration" 
                    :disabled="store.isLoading"
                    class="w-full bg-[#d946ef] hover:bg-[#c026d3] text-black text-xs py-2.5 rounded font-bold transition-colors shadow-[0_0_10px_rgba(217,70,239,0.3)] flex items-center justify-center gap-2 disabled:opacity-50 disabled:cursor-wait"
                  >
                    <Loader2 v-if="store.isLoading" class="w-3 h-3 animate-spin" />
                    <span>生成/更新所有立绘</span>
                  </button>
               </div>
            </div>

            <div class="flex justify-end gap-3 mt-6">
              <button 
                @click="showConfigModal = false"
                class="px-4 py-2 rounded-lg bg-zinc-800 hover:bg-zinc-700 text-zinc-300 font-bold transition-colors text-sm"
              >
                关闭
              </button>
            </div>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>

  <!-- Edit Avatar Modal -->
  <Teleport to="body">
    <Transition name="modal">
      <div v-if="editingNpc" class="fixed inset-0 z-[100] flex items-center justify-center p-4">
        <div class="absolute inset-0 bg-black/80 backdrop-blur-sm" @click="closeEditModal"></div>
        
        <div class="relative w-full max-w-lg bg-zinc-900 border border-zinc-800 rounded-lg shadow-2xl overflow-hidden transform transition-all">
          <button @click="closeEditModal" class="absolute top-4 right-4 text-zinc-500 hover:text-[#d946ef] transition-colors">
            <X class="w-5 h-5" />
          </button>

          <div class="p-6">
            <div class="flex items-center gap-3 mb-6">
              <div class="w-10 h-10 rounded-full bg-[#d946ef]/10 border border-[#d946ef]/50 text-[#d946ef] flex items-center justify-center">
                <Pencil class="w-5 h-5" />
              </div>
              <div>
                <h3 class="text-xl font-bold text-zinc-100">编辑立绘设定</h3>
                <p class="text-xs text-zinc-500">{{ editingNpc.profile.name }}</p>
              </div>
            </div>

            <div class="space-y-6">
              <!-- Edit Description -->
              <div>
                <label class="block text-sm font-bold text-zinc-400 mb-2">立绘描述词 (Avatar Desc)</label>
                <textarea 
                  v-model="editDescription"
                  class="w-full bg-zinc-950 border border-zinc-800 rounded-lg p-3 text-zinc-300 focus:outline-none focus:border-[#d946ef] transition-colors resize-none text-sm leading-relaxed"
                  rows="6"
                  placeholder="描述角色的外貌特征..."
                ></textarea>
                <p class="text-xs text-zinc-500 mt-2">修改描述后，点击下方保存。之后重新生成立绘将使用此新描述。</p>
              </div>

              <!-- Actions -->
              <div class="flex flex-col gap-3">
                 <button 
                    @click="saveDescription"
                    class="w-full py-2 bg-[#d946ef] hover:bg-[#c026d3] text-black font-bold rounded-lg transition-colors flex items-center justify-center gap-2"
                  >
                    <Save class="w-4 h-4" />
                    <span>保存描述修改</span>
                  </button>

                 <div class="relative">
                    <div class="absolute inset-0 flex items-center">
                      <span class="w-full border-t border-zinc-800"></span>
                    </div>
                    <div class="relative flex justify-center text-xs uppercase">
                      <span class="bg-zinc-900 px-2 text-zinc-500">OR</span>
                    </div>
                  </div>

                  <div class="flex gap-2">
                     <button 
                        @click="triggerFileUpload"
                        :disabled="isUploading"
                        class="flex-1 py-2 bg-zinc-800 hover:bg-zinc-700 text-zinc-300 font-bold rounded-lg transition-colors flex items-center justify-center gap-2 disabled:opacity-50"
                      >
                        <Loader2 v-if="isUploading" class="w-4 h-4 animate-spin" />
                        <Upload v-else class="w-4 h-4" />
                        <span>{{ isUploading ? '上传中...' : '上传图片替代' }}</span>
                      </button>
                      <input 
                        type="file" 
                        ref="fileInput" 
                        class="hidden" 
                        accept="image/*"
                        @change="handleFileChange"
                      />
                  </div>
                  <p class="text-[10px] text-zinc-600 text-center">建议比例 9:16，支持 JPG/PNG</p>
              </div>
            </div>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>

  <!-- Generation Config Modal -->
  <Teleport to="body">
    <Transition name="modal">
      <div v-if="showGenerationModal" class="fixed inset-0 z-[100] flex items-center justify-center p-4">
        <div class="absolute inset-0 bg-black/80 backdrop-blur-sm" @click="closeGenerationModal"></div>
        
        <div class="relative w-full max-w-md bg-zinc-900 border border-zinc-800 rounded-lg shadow-2xl overflow-hidden transform transition-all">
          <button @click="closeGenerationModal" class="absolute top-4 right-4 text-zinc-500 hover:text-[#d946ef] transition-colors">
            <X class="w-5 h-5" />
          </button>

          <div class="p-6">
            <div class="flex items-center gap-3 mb-6">
              <div class="w-10 h-10 rounded-full bg-[#d946ef]/10 border border-[#d946ef]/50 text-[#d946ef] flex items-center justify-center">
                <MessageSquarePlus class="w-5 h-5" />
              </div>
              <h3 class="text-xl font-bold text-zinc-100">生成配置</h3>
            </div>

            <div class="grid grid-cols-1 gap-6 mb-6">
              <!-- Count Slider -->
              <div>
                <label class="block text-sm font-bold text-zinc-400 mb-2 flex justify-between">
                  <div class="flex items-center gap-2">
                     <span>生成数量</span>
                     <span v-if="generationCount > 5" class="text-xs text-yellow-500 font-normal opacity-80 animate-pulse">(>5属于Beta功能)</span>
                  </div>
                  <span class="text-[#d946ef] font-mono">{{ generationCount }} 人</span>
                </label>
                <input 
                  v-model.number="generationCount" 
                  type="range" 
                  min="1" 
                  max="10" 
                  step="1"
                  class="w-full accent-[#d946ef] h-2 bg-zinc-800 rounded-lg appearance-none cursor-pointer"
                />
                <div class="flex justify-between text-[10px] text-zinc-600 mt-1 font-mono">
                  <span>1</span>
                  <span>10</span>
                </div>
              </div>

              <!-- Requirements -->
              <div>
                <label class="block text-sm font-bold text-zinc-400 mb-2">额外要求 (可选)</label>
                <textarea 
                  v-model="generationRequirements"
                  class="w-full bg-zinc-950 border border-zinc-800 rounded-lg p-3 text-zinc-300 focus:outline-none focus:border-[#d946ef] transition-colors resize-none text-sm leading-relaxed"
                  rows="4"
                  placeholder="例如：希望有一个性格阴暗的刺客，或者所有NPC都必须是赛博格..."
                ></textarea>
                <p class="text-xs text-zinc-500 mt-2">这些要求将注入到 NPC 生成的 Prompt 中，指导塑造者 (Shaper) 进行创作。</p>
              </div>
            </div>

            <div class="flex justify-end gap-3">
              <button 
                @click="closeGenerationModal"
                class="px-4 py-2 rounded-lg border border-zinc-700 text-zinc-400 hover:border-zinc-500 hover:text-zinc-200 transition-colors font-medium text-sm"
              >
                取消
              </button>
              <button 
                @click="confirmGeneration"
                class="px-6 py-2 rounded-lg bg-[#d946ef] hover:bg-[#c026d3] text-black font-bold shadow-[0_0_15px_rgba(217,70,239,0.3)] hover:shadow-[0_0_20px_rgba(217,70,239,0.5)] transition-all flex items-center gap-2 text-sm"
              >
                <Zap class="w-4 h-4 fill-current" />
                <span>确认开始生成</span>
              </button>
            </div>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped>
.modal-enter-active,
.modal-leave-active {
  transition: opacity 0.2s ease;
}

.modal-enter-from,
.modal-leave-to {
  opacity: 0;
}

.modal-enter-active .relative,
.modal-leave-active .relative {
  transition: transform 0.2s ease;
}

.modal-enter-from .relative,
.modal-leave-to .relative {
  transform: scale(0.95) translateY(10px);
}

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

<script setup lang="ts">
import { computed, ref } from 'vue';
import { useGenesisStore } from '../stores/genesis';
import { useUIStore } from '../stores/ui';
import { Map, ScrollText, User, CheckCircle2, Circle, Flag, RefreshCw, Pencil, X, Save, Target, Package, MapPin, Clock, Heart, AlertCircle } from 'lucide-vue-next';

const store = useGenesisStore();
const uiStore = useUIStore();

const mainQuest = computed(() => store.quests.find(q => q.type === 'main'));
const sideQuests = computed(() => store.quests.filter(q => q.type === 'side'));
const worldItems = computed(() => store.items || []);
const locations = computed(() => store.locations || []);
const timeConfig = computed(() => store.timeConfig || null);

const getSideQuestForNpc = (npcId: string) => {
    return store.quests.find(q => q.type === 'side' && (q as any).target_npc_id === npcId);
};

const hasLoadingSideQuests = computed(() => Object.values(store.loadingSideQuests).some(v => v));
const hasAnyQuests = computed(() => store.quests.length > 0);
const isGenerating = computed(() => 
    store.loadingMainQuest || 
    hasLoadingSideQuests.value ||
    store.loadingItems ||
    store.loadingLocations
);

const handleGenerate = async () => {
  await store.generateQuests();
};

const handleRegenerate = async () => {
    const confirmed = await uiStore.openModal(
        '重新生成任务',
        '确定要重新生成任务蓝图吗？当前的修改将丢失。',
        'confirm'
    );
    if (confirmed) {
        await store.generateQuests();
    }
};

const handleConfirm = async () => {
    const confirmed = await uiStore.openModal(
        '确认任务蓝图',
        '您确定要以此蓝图构建世界吗？确认后将解锁启动世界。',
        'confirm'
    );
    if (confirmed) {
        await store.confirmQuests();
        // Show success
        uiStore.openModal('蓝图已确认', '世界构建完成，您现在可以启动世界了。', 'info');
    }
};

const isFinalized = computed(() => store.currentStep === 'launch' || store.worldConfig.quest_confirmed);

// Edit Modal
const editingQuest = ref<any>(null);
const editForm = ref({ title: '', description: '' });
const showEditModal = ref(false);

const openEditModal = (quest: any) => {
    if (isFinalized.value) return; // Prevent edit if finalized
    editingQuest.value = quest;
    editForm.value = { 
        title: quest.title, 
        description: quest.description 
    };
    showEditModal.value = true;
};

const closeEditModal = () => {
    showEditModal.value = false;
    editingQuest.value = null;
};

const saveQuest = async () => {
    if (!editingQuest.value) return;
    try {
        await store.updateQuest(
            editingQuest.value.id, 
            editForm.value.title, 
            editForm.value.description
        );
        closeEditModal();
    } catch (e) {
        console.error("Failed to save quest", e);
    }
};

// Helper for Item Name Lookup
const getItemName = (itemId: string) => {
    const item = worldItems.value.find((i: any) => i.id === itemId);
    return item ? item.name : itemId;
};

// Helper for Location Name Lookup
const getLocationName = (locationId: string) => {
    const loc = locations.value.find((l: any) => l.id === locationId);
    return loc ? loc.name : locationId;
};

// Helper for Owner Info Lookup (Returns {name, type, icon, style})
const getOwnerInfo = (ownerId: string | null) => {
    if (!ownerId) return null;
    
    // 1. NPC owner (cyan - matching task tags)
    if (ownerId.startsWith('npc_')) {
        const npc = store.npcs.find((n: any) => n.id === ownerId);
        return npc ? {
            name: npc.profile.name,
            type: 'npc',
            icon: User,
            style: 'text-cyan-400 bg-cyan-950/20 border-cyan-900/30'
        } : {
            name: ownerId,
            type: 'unknown',
            icon: User,
            style: 'text-zinc-500 bg-zinc-900/20 border-zinc-800/30'
        };
    }
    
    // 2. Location owner (emerald/green - matching task tags)
    if (ownerId.startsWith('loc_')) {
        const loc = store.locations.find((l: any) => l.id === ownerId);
        return loc ? {
            name: loc.name,
            type: 'location',
            icon: MapPin,
            style: 'text-emerald-400 bg-emerald-950/30 border-emerald-900/50'
        } : {
            name: ownerId,
            type: 'unknown',
            icon: MapPin,
            style: 'text-zinc-500 bg-zinc-900/20 border-zinc-800/30'
        };
    }
    
    // 3. Fallback: try both
    const npc = store.npcs.find((n: any) => n.id === ownerId);
    if (npc) {
        return {
            name: npc.profile.name,
            type: 'npc',
            icon: User,
            style: 'text-cyan-400 bg-cyan-950/20 border-cyan-900/30'
        };
    }
    
    const loc = store.locations.find((l: any) => l.id === ownerId);
    if (loc) {
        return {
            name: loc.name,
            type: 'location',
            icon: MapPin,
            style: 'text-emerald-400 bg-emerald-950/30 border-emerald-900/50'
        };
    }
    
    return {
        name: ownerId,
        type: 'unknown',
        icon: AlertCircle,
        style: 'text-zinc-500 bg-zinc-900/20 border-zinc-800/30'
    };
};

// Helper for Tags Construction
const getNodeTags = (node: any) => {
    const tags = [];

    // 1. Location (First)
    const locId = node.location_id || node.target_location_id;
    if (locId) {
        tags.push({
            type: 'location',
            label: getLocationName(locId),
            icon: MapPin,
            style: 'text-emerald-400 bg-emerald-950/30 border-emerald-900/50'
        });
    }

    // 2. NPC (Second)
    if (node.target_npc_id) {
        const npcName = store.npcs.find((n: any) => n.id === node.target_npc_id)?.profile.name || 'Unknown';
        tags.push({
            type: 'npc',
            label: npcName,
            icon: User,
            style: 'text-cyan-400/80 bg-cyan-950/20 border-cyan-900/30'
        });
    }

    // 3. Affinity (Third)
    const affinityCond = node.conditions?.find((c: any) => c.type === 'affinity');
    if (affinityCond) {
        tags.push({
            type: 'affinity',
            label: `好感度 Lv.${affinityCond.params?.value}`,
            icon: Heart,
            style: 'text-rose-400 bg-rose-950/30 border-rose-900/50'
        });
    }

    // 4. Time (Fourth) - Only if restricted
    const timeCond = node.conditions?.find((c: any) => c.type === 'time');
    if (timeCond) {
        const start = timeCond.params?.start || timeCond.params?.hour_start;
        const end = timeCond.params?.end || timeCond.params?.hour_end;
        
        if (start && end) {
             tags.push({
                type: 'time',
                label: `${String(start).padStart(5, '0')} - ${String(end).padStart(5, '0')}`,
                icon: Clock,
                style: 'text-blue-400 bg-blue-950/30 border-blue-900/50'
            });
        }
    }

    // 5. Item (Fifth)
    // 5a. Show/Give (Conditions) - Support both old and new formats
    const itemConds = node.conditions?.filter((c: any) => c.type === 'item') || [];
    itemConds.forEach((cond: any) => {
        // Support both formats:
        // Old: {type: "item", item_id: "xxx", action: "show"}
        // New: {type: "item", params: {item_id: "xxx", action: "show"}}
        const itemId = cond.params?.item_id || cond.item_id;
        const action = cond.params?.action || cond.action || 'show';
        const itemName = getItemName(itemId);
        
        // 根据action类型显示不同文本
        const actionText = action === 'give' ? '给出' : '展示';
        
        tags.push({
            type: 'item_req',
            label: `${actionText} ${itemName}`,
            icon: Package,
            style: 'text-amber-400 bg-amber-950/30 border-amber-900/50'
        });
    });

    // 5b. Receive (Rewards) - Support both old and new formats
    if (Array.isArray(node.rewards)) {
        node.rewards.filter((r: any) => r.type === 'item').forEach((r: any) => {
             // Support both formats:
             // Old: {type: "item", item_id: "xxx", action: "receive"}
             // New: {type: "item", params: {item_id: "xxx", action: "receive"}}
             const itemId = r.params?.item_id || r.item_id;
             const itemName = r.params?.item_name || getItemName(itemId);
             tags.push({
                type: 'item_get',
                label: `得到 ${itemName}`,
                icon: Package,
                style: 'text-violet-400 bg-violet-950/30 border-violet-900/50'
            });
        });
    }

    return tags;
}

const formatType = (type?: string) => {
    switch (type) {
        case 'dialogue': return '对话 Dialogue';
        case 'collect': return '收集 Collect';
        case 'investigate': return '调查 Investigate';
        case 'wait': return '等待 Wait';
        case 'choice': return '抉择 Choice';
        default: return type?.toUpperCase() || '一般 GENERAL';
    }
};

const getTypeStyle = (type?: string) => {
    switch (type) {
        case 'dialogue': return 'text-sky-400 border-sky-900/50 bg-sky-950/30';
        case 'collect': return 'text-amber-400 border-amber-900/50 bg-amber-950/30';
        case 'investigate': return 'text-emerald-400 border-emerald-900/50 bg-emerald-950/30';
        case 'wait': return 'text-purple-400 border-purple-900/50 bg-purple-950/30';
        case 'choice': return 'text-rose-400 border-rose-900/50 bg-rose-950/30';
        default: return 'text-zinc-500 border-zinc-800 bg-zinc-900';
    }
};

const getMainTypeStyle = (type?: string) => {
    switch (type) {
        case 'dialogue': return 'bg-cyan-400 text-black border-cyan-500 shadow-[0_0_10px_rgba(6,182,212,0.2)]';
        case 'collect': return 'bg-amber-400 text-black border-amber-500 shadow-[0_0_10px_rgba(251,191,36,0.2)]';
        case 'investigate': return 'bg-emerald-400 text-black border-emerald-500 shadow-[0_0_10px_rgba(52,211,153,0.2)]';
        case 'wait': return 'bg-purple-400 text-black border-purple-500 shadow-[0_0_10px_rgba(192,132,252,0.2)]';
        case 'choice': return 'bg-rose-400 text-black border-rose-500 shadow-[0_0_10px_rgba(251,113,133,0.2)]';
        default: return 'bg-zinc-400 text-black border-zinc-500';
    }
};

</script>

<template>
  <div class="h-full bg-zinc-900 rounded-lg shadow-xl border border-zinc-800 flex flex-col overflow-hidden">
    
    <!-- Content Area -->
    <div class="flex-1 min-h-0 overflow-y-auto custom-scrollbar p-6 space-y-8 animate-fade-in-up bg-zinc-950/50">
      
      <!-- Empty State (Only when nothing exists AND nothing is loading) -->
      <div v-if="!hasAnyQuests && !isGenerating" class="h-full flex flex-col items-center justify-center text-center">
        <div class="w-24 h-24 bg-zinc-900 rounded-full flex items-center justify-center mb-6 relative group">
            <Map class="w-12 h-12 text-zinc-600 group-hover:text-cyan-400 transition-colors" />
            <div class="absolute inset-0 border border-zinc-800 rounded-full animate-pulse-slow"></div>
        </div>
        
        <h3 class="text-2xl font-bold text-zinc-200 mb-2">任务蓝图规划</h3>
        <p class="text-zinc-500 max-w-md mb-8">
            根据世界设定书和居民关系，自动生成主线剧情与支线任务。
            这将赋予世界目标感和探索动力。
        </p>
        
        <button 
            @click="handleGenerate"
            class="group relative px-8 py-4 bg-cyan-900/20 border border-cyan-800 text-cyan-400 rounded-lg hover:bg-cyan-900/40 hover:border-cyan-400 transition-all overflow-hidden"
        >
            <span class="flex items-center gap-2 font-bold tracking-wider">
                <ScrollText class="w-5 h-5" />
                生成任务蓝图
            </span>
        </button>
      </div>

      <!-- Quest Blueprint View (Show if we have content OR we are loading) -->
      <template v-else>
        <!-- Header Info -->
        <div class="flex items-center gap-3 mb-6">
            <div class="p-2 bg-cyan-950/30 rounded-lg border border-cyan-900/50">
                <Map class="w-6 h-6 text-cyan-400" />
            </div>
            <div>
                <h2 class="text-xl font-bold text-zinc-200">剧情蓝图</h2>
                <p class="text-xs text-zinc-500">
                    共 {{ store.quests.length }} 个任务链 ({{ sideQuests.length }} 支线)
                </p>
            </div>
        </div>

        <!-- Section 0: World Era (Chronicles) -->
        <div v-if="timeConfig" class="bg-zinc-900/50 border border-zinc-800 rounded-lg p-4 mb-6">
            <div class="flex items-center gap-2 text-zinc-400 text-sm font-bold tracking-widest uppercase mb-2">
                <Clock class="w-4 h-4 text-purple-500" />
                纪年 World Chronicles
            </div>
            <div class="flex items-baseline gap-3">
                <span class="text-2xl font-bold text-zinc-200">{{ timeConfig.display_year }}</span>
                <span class="text-sm text-zinc-500 font-mono">Start: {{ timeConfig.start_datetime }}</span>
            </div>
        </div>


        <!-- Section 2: Main Quest -->
        <div class="space-y-4 pt-4 border-t border-zinc-800/50">
            <div class="flex items-center justify-between">
                <div class="flex items-center gap-2 text-zinc-400 text-sm font-bold tracking-widest uppercase">
                    <Flag class="w-4 h-4 text-amber-500" />
                    主线任务 Main Quest
                </div>
            </div>
            
            <!-- Loading State -->
            <div v-if="store.loadingMainQuest" class="bg-zinc-900/30 border border-zinc-800/50 rounded-xl p-6 flex flex-col gap-4 animate-pulse">
                <div class="h-6 w-1/3 bg-zinc-800 rounded"></div>
                <div class="h-4 w-2/3 bg-zinc-800/50 rounded"></div>
                <div class="space-y-2 mt-4">
                    <div class="h-12 w-full bg-zinc-800/30 rounded border border-zinc-800"></div>
                    <div class="h-12 w-full bg-zinc-800/30 rounded border border-zinc-800"></div>
                </div>
                <div class="flex items-center justify-center text-zinc-500 text-sm mt-2 gap-2">
                    <span class="animate-spin">⟳</span> 正在构思宏大的主线剧情...
                </div>
            </div>

            <!-- Content -->
            <div v-else-if="mainQuest" class="bg-gradient-to-br from-amber-950/10 to-zinc-900/50 border border-amber-900/30 rounded-xl p-6 relative overflow-hidden group hover:border-amber-700/50 transition-colors">
                <!-- Edit Button -->
                <button 
                    v-if="!isFinalized"
                    @click.stop="openEditModal(mainQuest)"
                    class="absolute top-4 right-4 p-2 rounded-full text-zinc-500 hover:text-amber-400 hover:bg-amber-950/30 transition-colors opacity-0 group-hover:opacity-100"
                    title="编辑任务"
                >
                    <Pencil class="w-4 h-4" />
                </button>

                <!-- Title & Desc -->
                <div class="relative z-10 pr-8">
                    <h3 class="text-xl font-bold text-amber-100 mb-2">{{ mainQuest.title }}</h3>
                    <p class="text-amber-200/60 text-sm leading-relaxed max-w-3xl mb-6 whitespace-pre-wrap">
                        {{ mainQuest.description }}
                    </p>

                    <!-- Nodes Flow -->
                    <div class="relative">
                        <!-- Line -->
                        <div class="absolute left-6 top-4 bottom-4 w-0.5 bg-zinc-800"></div>

                        <div class="space-y-4">
                            <div 
                                v-for="(node, idx) in mainQuest.nodes" 
                                :key="node.id"
                                class="relative flex items-start gap-4 pl-2 group/node"
                            >
                                <!-- Dot -->
                                <div class="relative z-10 w-8 h-8 rounded-full bg-zinc-900 border border-zinc-700 flex items-center justify-center shrink-0 group-hover/node:border-amber-500/50 group-hover/node:text-amber-500 transition-colors text-xs font-mono text-zinc-500">
                                    {{ idx + 1 }}
                                </div>

                                <!-- Content -->
                                <div class="flex-1 bg-zinc-950/30 rounded-lg p-3 border border-zinc-800/50 hover:bg-zinc-900/50 transition-colors">
                                    <div class="flex items-center gap-2 mb-2">
                                        <span class="text-[10px] font-bold px-1.5 py-0.5 rounded border" :class="getMainTypeStyle(node.type)">
                                            {{ formatType(node.type) }}
                                        </span>
                                    </div>
                                    <p class="text-zinc-300 text-sm mb-2">{{ node.description }}</p>
                                    
                                    <!-- Conditions & Meta -->
                                    <div class="flex flex-wrap gap-2 text-xs">
                                        <div v-for="(tag, tIdx) in getNodeTags(node)" :key="tIdx" 
                                            class="flex items-center gap-1.5 px-2 py-0.5 rounded border"
                                            :class="tag.style"
                                        >
                                            <component :is="tag.icon" class="w-3 h-3" />
                                            <span>{{ tag.label }}</span>
                                        </div>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
                
                <!-- Bg Decoration -->
                <div class="absolute -right-20 -top-20 w-64 h-64 bg-amber-500/5 rounded-full blur-3xl pointer-events-none"></div>
            </div>

            <!-- Error State -->
            <div v-else class="p-6 border border-red-900/30 bg-red-950/10 rounded-xl flex items-center justify-between text-red-400">
                <span>主线任务生成失败</span>
                <button @click="store.retryMainQuest()" class="flex items-center gap-2 px-3 py-1.5 bg-red-900/20 hover:bg-red-900/40 border border-red-800 rounded text-xs font-bold transition-colors">
                    <RefreshCw class="w-3 h-3" /> 重试
                </button>
            </div>
        </div>

        <!-- Side Quests Section (Granular Grid) -->
        <div class="space-y-4">
            <div class="flex items-center gap-2 text-zinc-400 text-sm font-bold tracking-widest uppercase mt-8">
                <Circle class="w-4 h-4 text-zinc-500" />
                支线任务 Side Quests
            </div>

            <div class="grid grid-cols-1 gap-4">
                <template v-for="npc in store.npcs" :key="npc.id">
                    
                    <div v-if="getSideQuestForNpc(npc.id)"
                        class="bg-zinc-900/30 border border-zinc-800 rounded-lg p-5 hover:bg-zinc-900/50 transition-colors group relative"
                    >
                        <!-- Quest Card Logic -->
                        <button 
                            v-if="!isFinalized"
                            @click.stop="openEditModal(getSideQuestForNpc(npc.id))"
                            class="absolute top-4 right-4 p-1.5 rounded text-zinc-600 hover:text-zinc-300 hover:bg-zinc-800 transition-colors opacity-0 group-hover:opacity-100"
                            title="编辑任务"
                        >
                            <Pencil class="w-3 h-3" />
                        </button>

                        <div class="flex justify-between items-start mb-3 pr-8">
                            <h4 class="font-bold text-zinc-300">{{ getSideQuestForNpc(npc.id)?.title }}</h4>
                            <div class="flex items-center gap-2">
                                <div class="flex items-center gap-1.5 px-1.5 py-0.5 rounded bg-zinc-950/50 border border-zinc-800/50">
                                    <User class="w-3 h-3 text-zinc-500" />
                                    <span class="text-[10px] text-zinc-400">{{ npc.profile.name }}</span>
                                </div>
                                <span class="text-[10px] font-mono text-zinc-600 bg-zinc-950 px-2 py-1 rounded shrink-0">SIDE</span>
                            </div>
                        </div>
                        <p class="text-zinc-500 text-sm mb-4 line-clamp-2 whitespace-pre-wrap">{{ getSideQuestForNpc(npc.id)?.description }}</p>
                        
                        <!-- Rich Nodes Flow -->
                        <div class="relative">
                            <!-- Line -->
                            <div class="absolute left-6 top-4 bottom-4 w-0.5 bg-zinc-800"></div>

                            <div class="space-y-4">
                                <div 
                                    v-for="(node, idx) in (getSideQuestForNpc(npc.id)?.nodes || [])" 
                                    :key="idx"
                                    class="relative flex items-start gap-4 pl-2 group/node"
                                >
                                    <!-- Dot -->
                                    <div class="relative z-10 w-8 h-8 rounded-full bg-zinc-900 border border-zinc-700 flex items-center justify-center shrink-0 group-hover/node:border-cyan-500/50 group-hover/node:text-cyan-500 transition-colors text-xs font-mono text-zinc-500">
                                        {{ idx + 1 }}
                                    </div>

                                    <!-- Content -->
                                    <div class="flex-1 bg-zinc-950/30 rounded-lg p-3 border border-zinc-800/50 hover:bg-zinc-900/50 transition-colors">
                                        <div class="flex items-center gap-2 mb-2">
                                            <span class="text-[10px] font-bold px-1.5 py-0.5 rounded border" :class="getMainTypeStyle(node.type)">
                                                {{ formatType(node.type) }}
                                            </span>
                                        </div>
                                        <p class="text-zinc-300 text-sm mb-2">{{ node.description }}</p>
                                        
                                        <!-- Conditions & Meta -->
                                        <div class="flex flex-wrap gap-2 text-xs">
                                            <div v-for="(tag, tIdx) in getNodeTags(node)" :key="tIdx" 
                                                class="flex items-center gap-1.5 px-2 py-0.5 rounded border"
                                                :class="tag.style"
                                            >
                                                <component :is="tag.icon" class="w-3 h-3" />
                                                <span>{{ tag.label }}</span>
                                            </div>
                                        </div>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                    <div v-else-if="store.loadingSideQuests[npc.id]" class="bg-zinc-900/20 border border-zinc-800/50 rounded-lg p-5 flex items-center gap-4 animate-pulse">
                        <div class="w-10 h-10 rounded-full bg-zinc-800 flex items-center justify-center">
                            <User class="w-5 h-5 text-zinc-600" />
                        </div>
                        <div class="flex-1">
                            <div class="h-4 w-1/3 bg-zinc-800 rounded mb-2"></div>
                            <div class="h-3 w-1/2 bg-zinc-800/50 rounded"></div>
                        </div>
                        <span class="text-xs text-zinc-600">Generating for {{ npc.profile.name }}...</span>
                    </div>
                    <div v-else class="bg-zinc-900/20 border border-red-900/20 rounded-lg p-4 flex items-center justify-between group">
                        <div class="flex items-center gap-3 opacity-60">
                            <User class="w-8 h-8 text-zinc-700 bg-zinc-900 rounded-full p-1.5" />
                            <span class="text-sm text-zinc-500">{{ npc.profile.name }}: 任务生成中断</span>
                        </div>
                        <button @click="store.retrySideQuest(npc.id)" class="px-3 py-1.5 text-xs font-bold text-zinc-400 hover:text-zinc-200 border border-zinc-700 hover:bg-zinc-800 rounded transition-colors flex items-center gap-2">
                            <RefreshCw class="w-3 h-3" /> 重试
                        </button>
                    </div>

                </template>
            </div>
        </div>

            <!-- Section 3.5: World Items (Moved) -->
            <div class="space-y-4 pt-8 border-t border-zinc-800/50">
                <div class="flex items-center gap-2 text-zinc-400 text-sm font-bold tracking-widest uppercase">
                    <Package class="w-4 h-4 text-amber-500" />
                    关键道具 Key Items
                </div>
                
                <!-- Loading State -->
                <div v-if="store.loadingItems" class="grid grid-cols-2 md:grid-cols-3 gap-3">
                    <div v-for="i in 3" :key="i" class="bg-zinc-900/30 border border-zinc-800/50 rounded-lg p-3 animate-pulse">
                        <div class="h-4 w-2/3 bg-zinc-800 rounded mb-2"></div>
                        <div class="h-3 w-full bg-zinc-800/50 rounded mb-1"></div>
                        <div class="h-3 w-4/5 bg-zinc-800/50 rounded"></div>
                    </div>
                </div>
                
                <div v-else-if="worldItems.length > 0" class="grid grid-cols-2 md:grid-cols-3 gap-3">
                    <div v-for="item in worldItems" :key="item.id" 
                        class="bg-zinc-900/50 border border-zinc-800 rounded-lg p-3 hover:bg-zinc-900 hover:border-zinc-700 transition-colors group cursor-help relative flex flex-col"
                    >
                        <div class="flex justify-between items-start mb-1">
                            <h4 class="font-bold text-zinc-300 text-sm group-hover:text-amber-200 transition-colors truncate pr-2">{{ item.name }}</h4>
                        </div>
                        <p class="text-xs text-zinc-500 leading-relaxed flex-grow">{{ item.description }}</p>
                        
                        <!-- Source & Owner -->
                        <div v-if="item.obtain_methods && item.obtain_methods.length > 0" class="mt-2 pt-2 border-t border-zinc-800/50 flex justify-between items-center gap-2">
                            <span class="text-[10px] text-zinc-600 flex items-center gap-1">
                                <MapPin class="w-3 h-3 opacity-70" />
                                {{ item.obtain_methods[0].source }}
                            </span>
                            <span v-if="getOwnerInfo(item.owner_id)" class="text-[10px] flex items-center gap-1 px-1.5 py-0.5 rounded border" :class="getOwnerInfo(item.owner_id)?.style">
                                <component :is="getOwnerInfo(item.owner_id)?.icon" class="w-3 h-3" />
                                {{ getOwnerInfo(item.owner_id)?.name }}
                            </span>
                        </div>
                    </div>
                </div>
                <div v-else class="text-sm text-zinc-600 italic px-2">暂无关键物品数据</div>
            </div>

            <!-- Section 4: World Map (Locations) -->
            <div class="space-y-4 pt-8 border-t border-zinc-800/50">
                <div class="flex items-center gap-2 text-zinc-400 text-sm font-bold tracking-widest uppercase">
                    <MapPin class="w-4 h-4 text-emerald-500" />
                    关键地点 World Map
                </div>
                
                <!-- Loading State -->
                <div v-if="store.loadingLocations" class="grid grid-cols-2 md:grid-cols-3 gap-3">
                    <div v-for="i in 3" :key="i" class="bg-zinc-900/30 border border-zinc-800/50 rounded-lg p-3 animate-pulse">
                        <div class="h-4 w-1/2 bg-zinc-800 rounded mb-2"></div>
                        <div class="h-3 w-full bg-zinc-800/50 rounded"></div>
                    </div>
                </div>
                
                <div v-else-if="locations.length > 0" class="grid grid-cols-2 md:grid-cols-3 gap-3">
                    <div v-for="loc in locations" :key="loc.id" 
                        class="bg-zinc-900/30 border border-zinc-800 rounded-lg p-3 hover:bg-zinc-900 transition-colors group relative cursor-help"
                    >
                        <div class="flex items-center justify-between mb-1">
                            <span class="text-sm font-bold text-zinc-300 group-hover:text-emerald-300 transition-colors">{{ loc.name }}</span>
                            <span class="text-[10px] text-zinc-600 bg-zinc-950 px-1.5 py-0.5 rounded border border-zinc-800 uppercase font-mono">
                                {{ loc.type }}
                            </span>
                        </div>
                        <p class="text-xs text-zinc-500 leading-relaxed">{{ loc.description }}</p>
                    </div>
                </div>
                <div v-else class="text-sm text-zinc-600 italic px-2">暂无地点数据</div>
            </div>
        </template>

    </div>

    <!-- Action Footer (Show when有任务 OR 正在生成) -->
    <div v-if="store.quests.length > 0 || isGenerating" class="p-4 bg-zinc-950 border-t border-zinc-800 flex justify-between items-center shrink-0">
        <div class="flex items-center gap-3">
            <!-- Stats -->
            <div class="flex items-center gap-2 px-4 py-3 bg-zinc-900 rounded-lg border border-zinc-800 h-full">
                <Target class="w-4 h-4 text-cyan-500" />
                <span class="text-sm font-bold text-zinc-400">Total: <span class="text-zinc-200">{{ store.quests.length }}</span></span>
            </div>

            <!-- Regenerate -->
            <button 
                v-if="!isFinalized"
                @click="handleRegenerate"
                :disabled="store.isLoading || isGenerating"
                class="flex items-center gap-2 px-4 py-3 rounded-lg bg-zinc-900 border border-zinc-800 text-zinc-400 hover:text-zinc-200 transition-colors text-sm font-bold disabled:opacity-50 disabled:cursor-not-allowed"
            >
                <RefreshCw class="w-4 h-4" :class="{'animate-spin': store.isLoading || isGenerating}" />
                <span>重新生成</span>
            </button>
        </div>

        <!-- Confirm / Finalized Status -->
        <button 
            v-if="!isFinalized"
            @click="handleConfirm"
            :disabled="store.isLoading || isGenerating"
            class="bg-cyan-500 hover:bg-cyan-400 text-black px-6 py-3 rounded-lg flex items-center gap-2 transition-all font-bold shadow-[0_0_10px_rgba(6,182,212,0.3)] hover:shadow-[0_0_15px_rgba(6,182,212,0.5)] disabled:opacity-50 disabled:cursor-not-allowed"
        >
            <CheckCircle2 class="w-4 h-4" />
            <span>确认任务蓝图</span>
        </button>
        
        <div v-else class="text-cyan-500 font-extrabold flex items-center gap-2 px-4 py-3 bg-zinc-900/50 rounded-lg border border-zinc-800">
            <CheckCircle2 class="w-5 h-5" />
            <span>已定稿</span>
        </div>
    </div>

  </div>

  <!-- Edit Modal -->
  <Teleport to="body">
    <Transition name="modal">
      <div v-if="showEditModal" class="fixed inset-0 z-[100] flex items-center justify-center p-4">
        <div class="absolute inset-0 bg-black/80 backdrop-blur-sm" @click="closeEditModal"></div>
        
        <div class="relative w-full max-w-lg bg-zinc-900 border border-zinc-800 rounded-lg shadow-2xl overflow-hidden transform transition-all">
          <button @click="closeEditModal" class="absolute top-4 right-4 text-zinc-500 hover:text-cyan-400 transition-colors">
            <X class="w-5 h-5" />
          </button>

          <div class="p-6">
            <div class="flex items-center gap-3 mb-6">
              <div class="w-10 h-10 rounded-full bg-cyan-900/20 border border-cyan-500/30 text-cyan-400 flex items-center justify-center">
                <Pencil class="w-5 h-5" />
              </div>
              <h3 class="text-xl font-bold text-zinc-100">编辑任务</h3>
            </div>

            <div class="space-y-4">
              <div>
                <label class="block text-xs font-bold text-zinc-500 uppercase mb-1">标题 Title</label>
                <input 
                  v-model="editForm.title"
                  class="w-full bg-zinc-950 border border-zinc-800 rounded-lg p-3 text-zinc-200 focus:outline-none focus:border-cyan-500 transition-colors font-bold"
                />
              </div>

              <div>
                <label class="block text-xs font-bold text-zinc-500 uppercase mb-1">描述 Description</label>
                <textarea 
                  v-model="editForm.description"
                  class="w-full bg-zinc-950 border border-zinc-800 rounded-lg p-3 text-zinc-300 focus:outline-none focus:border-cyan-500 transition-colors resize-none text-sm leading-relaxed"
                  rows="6"
                ></textarea>
              </div>
            </div>

            <div class="flex justify-end gap-3 mt-6">
              <button 
                @click="closeEditModal"
                class="px-4 py-2 rounded-lg border border-zinc-700 text-zinc-400 hover:border-zinc-500 hover:text-zinc-200 transition-colors font-medium text-sm"
              >
                取消
              </button>
              <button 
                @click="saveQuest"
                class="px-6 py-2 rounded-lg bg-cyan-500 hover:bg-cyan-400 text-black font-bold shadow-lg transition-all flex items-center gap-2 text-sm"
              >
                <Save class="w-4 h-4" />
                <span>保存修改</span>
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

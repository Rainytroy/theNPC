<script setup lang="ts">
import GenesisChat from '../components/GenesisChat.vue';
import WorldBibleCard from '../components/WorldBibleCard.vue';
import NPCList from '../components/NPCList.vue';
import QuestBlueprint from '../components/QuestBlueprint.vue';
import LaunchProgress from '../components/LaunchProgress.vue';
import WorldSidebar from '../components/WorldSidebar.vue';
import { useGenesisStore } from '../stores/genesis';
import { useWorldStore } from '../stores/genesis/world';
import { ref, computed, watch, onMounted, onUnmounted } from 'vue';
import { useRouter } from 'vue-router';
import { ScrollText, Users, Map, Rocket, Lock, CheckCircle2, Loader2, RefreshCw } from 'lucide-vue-next';
import genesisApi from '../api/genesis';
import { useUIStore } from '../stores/ui';

const store = useGenesisStore();
const worldStore = useWorldStore();
const uiStore = useUIStore();
const router = useRouter();
const sidebarRef = ref<InstanceType<typeof WorldSidebar> | null>(null);
let pollInterval: any = null;

// Tab State
const activeTab = ref('world');

// Sync active tab with store step
const syncTab = () => {
    activeTab.value = store.currentStep;
};

watch(() => store.currentStep, syncTab);

// Watch for sessionId changes (new world creation)
watch(() => store.sessionId, (newId, oldId) => {
    // When sessionId changes, force reset tab to 'world'
    if (newId && newId !== oldId) {
        console.log('[GenesisView] New session detected, resetting tab to world');
        activeTab.value = 'world';
    }
});

// Watch for world_id changes to refresh sidebar
watch(() => worldStore.finalizedWorldBible?.world_id, (newId, oldId) => {
    // When world_id changes from null to a value (world created)
    if (newId && !oldId) {
        console.log('[GenesisView] New world created, refreshing sidebar...');
        setTimeout(() => {
            sidebarRef.value?.refresh();
        }, 500); // Give backend time to save
    }
});

// Watch for world confirmation to auto-migrate focus
watch(() => worldStore.finalizedWorldBible, (newBible, oldBible) => {
    // When bible goes from null to defined (world just confirmed)
    if (newBible && !oldBible) {
        console.log('[GenesisView] World confirmed detected, auto-migrating focus to NPC tab');
        activeTab.value = 'npc';
    }
});

const startPolling = () => {
    if (!pollInterval) {
        store.pollLaunchStatus(); // Immediate first call
        pollInterval = setInterval(async () => {
            await store.pollLaunchStatus();
            
            // Auto-stop polling when launch is complete
            if (store.launchProgress?.current_phase === 'ready') {
                console.log('[GenesisView] Launch completed, stopping poll');
                clearInterval(pollInterval);
                pollInterval = null;
            }
        }, 2000); // Poll every 2 seconds
    }
};

const stopPolling = () => {
    if (pollInterval) {
        clearInterval(pollInterval);
        pollInterval = null;
    }
};

// Watch active tab for polling
watch(activeTab, (newTab) => {
    if (newTab === 'launch') {
        startPolling();
    } else {
        stopPolling();
    }
}, { immediate: true });

// Watch launch progress phase to restart polling if needed
watch(() => store.launchProgress?.current_phase, (newPhase) => {
    if (activeTab.value === 'launch' && newPhase !== 'ready' && !pollInterval) {
        console.log('[GenesisView] Phase reverted to non-ready, restarting poll');
        startPolling();
    }
});

const handleRegenerate = async () => {
    const confirmed = await uiStore.openModal(
        '重新构建世界',
        '确定要重新执行初始化流程吗？这将覆盖当前生成的开场白、任务细节和日程。',
        'confirm'
    );
    
    if (confirmed && worldStore.finalizedWorldBible?.world_id) {
        try {
            await genesisApi.executeConfirmQuestBlueprint(worldStore.finalizedWorldBible.world_id);
            // Trigger poll immediately
            store.pollLaunchStatus();
            // Ensure polling is running
            startPolling();
        } catch (e) {
            console.error("Failed to regenerate world", e);
        }
    }
};

onMounted(() => {
    if (store.currentStep !== 'world') {
        activeTab.value = store.currentStep;
    }
});

onUnmounted(() => {
    stopPolling();
});

const tabs = computed(() => [
    { 
        id: 'world', 
        label: '世界设定书', 
        enLabel: 'WORLD BIBLE',
        icon: ScrollText,
        colorClass: 'text-[#ccff00]',
        bgClass: 'bg-[#ccff00]',
        isCompleted: !!worldStore.finalizedWorldBible,
        isActive: activeTab.value === 'world',
        isLocked: false 
    },
    { 
        id: 'npc', 
        label: '居民名册', 
        enLabel: 'NPC ROSTER', 
        icon: Users,
        colorClass: 'text-[#d946ef]',
        bgClass: 'bg-[#d946ef]',
        isCompleted: ['quest', 'launch'].includes(store.currentStep),
        isActive: activeTab.value === 'npc',
        isLocked: !worldStore.finalizedWorldBible
    },
    { 
        id: 'quest', 
        label: '任务蓝图', 
        enLabel: 'QUEST BLUEPRINT',
        icon: Map, 
        colorClass: 'text-cyan-400',
        bgClass: 'bg-cyan-400',
        isCompleted: store.currentStep === 'launch',
        isActive: activeTab.value === 'quest',
        isLocked: !['quest', 'launch'].includes(store.currentStep)
    },
    { 
        id: 'launch', 
        label: '启动世界', 
        enLabel: 'LAUNCH WORLD',
        icon: Rocket,
        colorClass: 'text-[#ccff00]', // Reusing green for launch
        bgClass: 'bg-[#ccff00]',
        isCompleted: store.isLocked,
        isActive: activeTab.value === 'launch',
        isLocked: store.currentStep !== 'launch' 
    }
]);

const handleTabClick = (tab: any) => {
    if (tab.isLocked) return;
    activeTab.value = tab.id;
};

// When world is confirmed or NPC generated, refresh the list
const onStateChange = () => {
  sidebarRef.value?.refresh();
};

const onWorldConfirmed = () => {
    // 1. Refresh Sidebar
    sidebarRef.value?.refresh();

    // 2. Ensure Store Step is NPC (兜底确保 store 同步)
    if (store.currentStep !== 'npc') {
        store.currentStep = 'npc';
    }

    // 3. 硬编码焦点迁移到 NPC Tab (直接设置，不依赖 watcher)
    activeTab.value = 'npc';
    console.log('[GenesisView] World confirmed, force migrated focus to NPC tab');
};
</script>

<template>
  <div class="h-full bg-black flex overflow-hidden text-zinc-300">
    <!-- Sidebar -->
    <WorldSidebar ref="sidebarRef" />

    <!-- Main Content Area -->
    <div class="flex-1 flex gap-6 p-6 transition-all duration-500 overflow-hidden">
      <!-- Left Panel: Chat (Always Visible, Flexible Width) -->
      <div class="flex-1 h-full min-w-0">
        <GenesisChat />
      </div>

      <!-- Right Panel: Fixed Width (Bible or NPC List) -->
      <div class="w-2/3 h-full transition-all duration-500 flex-shrink-0 flex flex-col min-h-0">
        
        <!-- Wizard Navigation -->
        <div class="flex-none flex items-center gap-3 mb-6 bg-zinc-950/50 p-2 rounded-xl border border-zinc-800 w-full h-20">
          <button 
            v-for="tab in tabs" 
            :key="tab.id"
            @click="handleTabClick(tab)"
            :disabled="tab.isLocked"
            class="flex-1 h-full rounded-lg flex items-center px-4 gap-3 transition-all duration-300 relative group overflow-hidden border"
            :class="[
                tab.isActive ? tab.bgClass + ' text-black shadow-lg border-transparent' : (
                    !tab.isLocked ? 'bg-zinc-900/50 hover:bg-zinc-900 border-zinc-800 ' + tab.colorClass : 'border-transparent text-zinc-500'
                ),
                tab.isLocked ? 'opacity-60 cursor-not-allowed' : 'cursor-pointer'
            ]"
          >
            <!-- Identity Icon (Left) - Always shows the tab's specific icon -->
            <div class="w-10 h-10 flex items-center justify-center shrink-0">
                <component :is="tab.icon" class="w-8 h-8" />
            </div>
            
            <!-- Text Container -->
            <div class="flex flex-col text-left leading-none gap-1 flex-1 min-w-0">
                <div class="flex items-center gap-2">
                    <span class="text-lg font-black tracking-wide whitespace-nowrap">
                        {{ tab.label }}
                    </span>
                    
                    <!-- Status Icon (Right of CN Text) -->
                    <!-- Completed -->
                    <CheckCircle2 v-if="tab.isCompleted" class="w-4 h-4" />
                    <!-- Locked -->
                    <Lock v-else-if="tab.isLocked" class="w-4 h-4 opacity-70" />
                    <!-- Active & In Progress -->
                    <div v-else-if="tab.isActive" class="w-2 h-2 rounded-full animate-pulse bg-black shadow-[0_0_8px_currentColor]"></div>
                </div>
                
                <span class="text-[10px] font-mono font-bold tracking-[0.1em] opacity-60 truncate">
                    {{ tab.enLabel }}
                </span>
            </div>
          </button>
        </div>

        <!-- Content Area -->
        <div class="flex-1 min-h-0 relative bg-zinc-900/20 rounded-lg border border-transparent">
            <!-- Step 1: World Bible -->
            <div v-show="activeTab === 'world'" class="h-full absolute inset-0">
                <WorldBibleCard @confirmed="onWorldConfirmed" @updated="onStateChange" />
            </div>

            <!-- Step 2: NPC List -->
            <div v-if="worldStore.finalizedWorldBible" v-show="activeTab === 'npc'" class="h-full absolute inset-0 animate-fade-in-up">
                <NPCList @generated="onStateChange" />
            </div>

            <!-- Step 3: Quest Blueprint -->
            <div v-if="['quest', 'launch'].includes(store.currentStep)" v-show="activeTab === 'quest'" class="h-full absolute inset-0 animate-fade-in-up">
                <QuestBlueprint />
            </div>

            <!-- Step 4: Launch World -->
            <div v-if="store.currentStep === 'launch'" v-show="activeTab === 'launch'" class="h-full absolute inset-0 animate-fade-in-up flex items-center justify-center border border-dashed border-zinc-800 rounded-lg bg-zinc-900/50">
                <div class="w-full h-full">
                    <LaunchProgress />
                </div>
            </div>
        </div>

      </div>
    </div>
  </div>
</template>

<style>
@keyframes fadeInUp {
  from {
    opacity: 0;
    transform: translateY(20px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}
.animate-fade-in-up {
  animation: fadeInUp 0.5s ease-out forwards;
}
</style>

<script setup lang="ts">
import { computed, ref, watch, onMounted, nextTick } from 'vue';
import { useGenesisStore } from '../stores/genesis';
import { useUIStore } from '../stores/ui';
import genesisApi from '../api/genesis';
import { useRouter } from 'vue-router';
import { 
    Zap, Rocket, CheckCircle2, Circle, RefreshCw, 
    Play, Terminal, ChevronRight
} from 'lucide-vue-next';

const store = useGenesisStore();
const uiStore = useUIStore();
const router = useRouter();

const progress = computed(() => store.launchProgress?.progress || {});
const currentPhase = computed(() => store.launchProgress?.current_phase || 'launch');
const isDataEmpty = computed(() => Object.keys(progress.value).length === 0);

// Local State for Log Stream
const logContainer = ref<HTMLElement | null>(null);
const logs = ref<Array<{ id: number, text: string, type: 'info' | 'success' | 'warning' | 'error', timestamp: string }>>([]);
let logCounter = 0;

const addLog = (text: string, type: 'info' | 'success' | 'warning' | 'error' = 'info') => {
    if (!text) return;
    // Avoid duplicate consecutive logs
    if (logs.value.length > 0 && logs.value[logs.value.length - 1].text === text) return;
    
    logs.value.push({
        id: logCounter++,
        text,
        type,
        timestamp: new Date().toLocaleTimeString()
    });
    
    scrollToBottom();
};

const scrollToBottom = () => {
    nextTick(() => {
        if (logContainer.value) {
            logContainer.value.scrollTop = logContainer.value.scrollHeight;
        }
    });
};

// Status Helpers
const getStatus = (key: string) => {
    if (currentPhase.value === 'ready') return 'completed';
    const section = progress.value[key];
    if (!section) return isDataEmpty.value ? 'initializing' : 'pending';
    if (section.status === 'completed') return 'completed';
    if (section.status === 'failed') return 'failed';
    if (section.status === 'processing' || section.status === 'running') return 'active';
    return 'pending';
};


const isReady = computed(() => {
    if (currentPhase.value === 'ready') return true;
    const introDone = getStatus('intro') === 'completed';
    const questDone = getStatus('quest_enrich') === 'completed';
    const scheduleDone = getStatus('schedule') === 'completed';
    return introDone && questDone && scheduleDone;
});


watch(() => isReady.value, (ready) => {
    if (ready) {
        addLog("系统初始化完成。世界已就绪。", 'success');
        scrollToBottom();
    }
});

// Regenerate Logic
const isRegenerating = ref(false);

const handleRegenerate = async () => {
    const confirmed = await uiStore.openModal(
        '重新构建世界',
        '确定要重新执行初始化流程吗？这将覆盖当前生成的开场白、任务细节和日程。',
        'confirm'
    );
    
    if (confirmed && store.finalizedWorldBible?.world_id) {
        try {
            isRegenerating.value = true;
            logs.value = []; // Clear logs
            
            // Clear local intro state to force fresh fetch and typewriter effect
            introText.value = '';
            displayedIntro.value = '';
            
            // Clear sessionStorage flag
            const worldId = store.finalizedWorldBible.world_id;
            sessionStorage.removeItem(`intro_played_${worldId}`);

            addLog("开始重新生成世界...", 'warning');
            await genesisApi.executeConfirmQuestBlueprint(worldId);
            store.pollLaunchStatus();
        } catch (e) {
            console.error("Failed to regenerate world", e);
            addLog("重新生成失败", 'error');
        } finally {
            isRegenerating.value = false;
        }
    }
};

const handleEnterWorld = () => {
    if (store.finalizedWorldBible?.world_id) {
        router.push(`/world/${store.finalizedWorldBible.world_id}`);
    }
};

// Intro Typewriter Effect
const introText = ref('');
const displayedIntro = ref('');
const isTyping = ref(false);
const introContainer = ref<HTMLElement | null>(null);

const formattedIntro = computed(() => {
    if (!displayedIntro.value) return '';
    // Replace **text** with styled span (bold + neon green)
    return displayedIntro.value.replace(/\*\*(.*?)\*\*/g, '<span class="font-bold text-[#ccff00]">$1</span>');
});

const fetchIntro = async () => {
    const worldId = store.finalizedWorldBible?.world_id;
    if (!worldId) return;

    try {
        // ✅ 方案B：直接从后端 API 获取 intro（不依赖 status.json，避免串世界）
        const data = await genesisApi.getIntro(worldId);
        if (data.intro) {
            introText.value = data.intro;
        } else {
            // Fallback: 如果 API 没返回，尝试从 progress 读取（兼容旧逻辑）
            const introContent = progress.value.intro?.content;
            if (introContent) {
                introText.value = introContent;
            }
        }
    } catch (e) {
        console.error("Failed to fetch intro", e);
    }
};

const scrollToIntroTop = () => {
    nextTick(() => {
        if (introContainer.value) {
            introContainer.value.scrollIntoView({ behavior: 'smooth', block: 'start' });
        }
    });
};

const startTypewriter = () => {
    if (!introText.value || isTyping.value) return;
    
    isTyping.value = true;
    displayedIntro.value = '';
    
    let currentIndex = 0;
    const text = introText.value;
    const speed = 30; // milliseconds per character
    
    const typeInterval = setInterval(() => {
        if (currentIndex < text.length) {
            displayedIntro.value += text[currentIndex];
            currentIndex++;
            scrollToBottom(); // ✅ 每打一个字就滚动到底部，跟随光标
        } else {
            clearInterval(typeInterval);
            isTyping.value = false;
            // 标记打字机动画已播放
            if (store.finalizedWorldBible?.world_id) {
                sessionStorage.setItem(`intro_played_${store.finalizedWorldBible.world_id}`, 'true');
            }
            // 🎬 播放完成后，滚动到 Intro 顶部方便阅读
            scrollToIntroTop();
        }
    }, speed);
};

// ✅ 监听世界ID变化，强制刷新launchProgress（修复切换世界时数据串的问题）
watch(() => store.finalizedWorldBible?.world_id, async (newId, oldId) => {
    if (newId !== oldId && oldId !== undefined) {
        // 切换世界时清空缓存
        introText.value = '';
        displayedIntro.value = '';
        isTyping.value = false;
        
        // 🎯 关键：强制poll新世界的status，确保launchProgress是最新的
        await store.pollLaunchStatus();
        
        // 如果新世界已经就绪，立即获取并显示intro
        if (isReady.value) {
            await fetchIntro();
            if (introText.value) {
                displayedIntro.value = introText.value;
                scrollToIntroTop();
            }
        }
    }
});

// Watch isReady to trigger intro fetch and typewriter
watch(() => isReady.value, async (ready) => {
    if (ready && !introText.value) {
        await fetchIntro();
        
        // 检查是否已播放过打字机动画
        const worldId = store.finalizedWorldBible?.world_id;
        const hasPlayed = worldId && sessionStorage.getItem(`intro_played_${worldId}`) === 'true';
        
        if (hasPlayed) {
            // 直接显示完整文本
            displayedIntro.value = introText.value;
            scrollToIntroTop();
        } else {
            // 首次显示，播放打字机动画
            setTimeout(() => {
                startTypewriter();
            }, 500);
        }
    }
});

onMounted(async () => {
    scrollToBottom();
    
    // 如果页面加载时世界已就绪，获取并显示intro（不播放动画）
    if (isReady.value && !introText.value) {
        await fetchIntro();
        if (introText.value) {
            displayedIntro.value = introText.value;
            scrollToIntroTop();
        }
    }
});

</script>

<template>
    <div class="h-full bg-zinc-950 rounded-lg shadow-xl border border-zinc-800 flex flex-col overflow-hidden relative">
        
        <!-- Matrix/Terminal Background Effect -->
        <div class="absolute inset-0 pointer-events-none opacity-5 bg-[url('/img/grid.png')]"></div>

        <!-- Header -->
        <div class="p-4 border-b border-zinc-800 bg-zinc-900/50 flex justify-between items-center z-10 backdrop-blur-sm">
            <div class="flex items-center gap-3">
                <div class="p-2 bg-black rounded-lg border border-zinc-700 shadow-inner">
                    <Terminal class="w-5 h-5 text-[#ccff00]" />
                </div>
                <div>
                    <h2 class="text-lg font-bold text-zinc-100 font-mono tracking-wide">SYSTEM INITIALIZATION</h2>
                    <p class="text-[10px] text-zinc-500 font-mono">WORLD_ENGINE::V1.0.0</p>
                </div>
            </div>
            <!-- Global Status Indicator -->
            <div class="px-3 py-1 rounded-full border text-xs font-mono flex items-center gap-2"
                :class="isReady ? 'bg-[#ccff00]/10 border-[#ccff00]/30 text-[#ccff00]' : 'bg-zinc-800 border-zinc-700 text-zinc-400'">
                <div class="w-2 h-2 rounded-full" :class="isReady ? 'bg-[#ccff00] animate-pulse' : 'bg-zinc-500'"></div>
                {{ isReady ? 'READY' : 'PROCESSING' }}
            </div>
        </div>

        <!-- Scrollable Log Stream Area -->
        <div ref="logContainer" class="flex-1 min-h-0 overflow-y-auto custom-scrollbar p-6 space-y-8 z-0">
            
            <!-- Connection Loading -->
            <div v-if="isDataEmpty" class="flex flex-col items-center justify-center py-20 animate-pulse">
                <Zap class="w-12 h-12 text-zinc-600 mb-4" />
                <p class="text-zinc-500 font-mono">ESTABLISHING CONNECTION...</p>
            </div>

            <template v-else>
                <!-- 1. Intro Section -->
                <div class="relative pl-8 transition-all duration-500"
                    :class="getStatus('intro') === 'completed' ? 'opacity-100' : 'opacity-50'">
                    
                    <!-- Icon: 简化版本 -->
                    <div class="absolute left-0 top-1/2 -translate-y-1/2 w-3 h-3 rounded-full transition-all duration-500"
                        :class="{
                            'bg-[#ccff00]': getStatus('intro') === 'completed',
                            'bg-[#ccff00] animate-pulse': getStatus('intro') === 'active',
                            'border-2 border-zinc-700': getStatus('intro') === 'pending'
                        }">
                    </div>

                    <h3 class="text-sm font-bold text-zinc-200 mb-2 font-mono flex items-center gap-2">
                        MODULE::INTRO
                        <span v-if="getStatus('intro') === 'active'" class="text-[#ccff00] text-xs animate-pulse">[GENERATING...]</span>
                    </h3>

                    <!-- 完成后只显示总结 -->
                    <div v-if="getStatus('intro') === 'completed'" class="font-mono text-xs text-zinc-500">
                        > Intro generated successfully.
                    </div>
                </div>

                <!-- 2. Quest Section -->
                <div class="relative pl-8 transition-all duration-500"
                    :class="getStatus('quest_enrich') === 'completed' ? 'opacity-100' : 
                            getStatus('quest_enrich') === 'active' ? 'opacity-100' : 'opacity-50'">
                    
                    <!-- Icon: 简化版本 -->
                    <div class="absolute left-0 top-1/2 -translate-y-1/2 w-3 h-3 rounded-full transition-all duration-500"
                        :class="{
                            'bg-[#ccff00]': getStatus('quest_enrich') === 'completed',
                            'bg-[#ccff00] animate-pulse': getStatus('quest_enrich') === 'active',
                            'border-2 border-zinc-700': getStatus('quest_enrich') === 'pending'
                        }">
                    </div>

                    <h3 class="text-sm font-bold text-zinc-200 mb-2 font-mono flex items-center gap-2">
                        MODULE::QUEST_ENRICH
                        <span v-if="getStatus('quest_enrich') === 'active'" class="text-[#ccff00] text-xs animate-pulse">[PROCESSING...]</span>
                    </h3>

                    <!-- Quest Progress Bar -->
                    <div v-if="getStatus('quest_enrich') === 'active'" class="mb-3">
                        <div class="flex justify-between text-[10px] font-mono text-zinc-500 mb-1">
                            <span>PROGRESS</span>
                            <span>{{ progress.quest_enrich?.current || 0 }} / {{ progress.quest_enrich?.total || '?' }}</span>
                        </div>
                        <div class="w-full bg-zinc-900 h-1.5 rounded-full overflow-hidden border border-zinc-800">
                            <div class="bg-[#ccff00] h-full transition-all duration-300 ease-out" 
                                 :style="{ width: `${(progress.quest_enrich?.current / (progress.quest_enrich?.total || 1)) * 100}%` }"></div>
                        </div>
                    </div>

                    <!-- Quest Active Logs -->
                    <div v-if="getStatus('quest_enrich') === 'active'" class="font-mono text-xs space-y-1 text-zinc-500">
                        <!-- 当前处理项 - 唯一显示，黄色闪动 -->
                        <div class="flex gap-2 animate-pulse text-[#ccff00]">
                            <span class="text-zinc-600">[NOW]</span>
                            <span>> {{ progress.quest_enrich?.message || 'Processing...' }}</span>
                        </div>
                    </div>
                    
                    <!-- 完成后只显示总结 -->
                    <div v-else-if="getStatus('quest_enrich') === 'completed'" class="font-mono text-xs text-zinc-500">
                        > All quests enriched successfully.
                    </div>
                </div>

                <!-- 3. Schedule Section -->
                <div class="relative pl-8 transition-all duration-500"
                    :class="getStatus('schedule') === 'completed' ? 'opacity-100' : 
                            getStatus('schedule') === 'active' ? 'opacity-100' : 'opacity-50'">
                    
                    <!-- Icon: 简化版本 -->
                    <div class="absolute left-0 top-1/2 -translate-y-1/2 w-3 h-3 rounded-full transition-all duration-500"
                        :class="{
                            'bg-[#ccff00]': getStatus('schedule') === 'completed',
                            'bg-[#ccff00] animate-pulse': getStatus('schedule') === 'active',
                            'border-2 border-zinc-700': getStatus('schedule') === 'pending'
                        }">
                    </div>

                    <h3 class="text-sm font-bold text-zinc-200 mb-2 font-mono flex items-center gap-2">
                        MODULE::SCHEDULER
                        <span v-if="getStatus('schedule') === 'active'" class="text-[#ccff00] text-xs animate-pulse">[GENERATING...]</span>
                    </h3>

                    <!-- Schedule Progress Bar -->
                    <div v-if="getStatus('schedule') === 'active'" class="mb-3">
                        <div class="flex justify-between text-[10px] font-mono text-zinc-500 mb-1">
                            <span>PROGRESS</span>
                            <span>{{ progress.schedule?.current || 0 }} / {{ progress.schedule?.total || '?' }}</span>
                        </div>
                        <div class="w-full bg-zinc-900 h-1.5 rounded-full overflow-hidden border border-zinc-800">
                            <div class="bg-[#ccff00] h-full transition-all duration-300 ease-out" 
                                 :style="{ width: `${(progress.schedule?.current / (progress.schedule?.total || 1)) * 100}%` }"></div>
                        </div>
                    </div>

                    <!-- Schedule Logs -->
                    <div v-if="getStatus('schedule') === 'active'" class="font-mono text-xs space-y-1 text-zinc-500">
                        <!-- 当前处理项 - 唯一显示，黄色闪动 -->
                        <div class="flex gap-2 animate-pulse text-[#ccff00]">
                            <span class="text-zinc-600">[NOW]</span>
                            <span>> {{ progress.schedule?.message || 'Processing...' }}</span>
                        </div>
                    </div>

                    <!-- 完成后只显示总结 - 统一样式，无边框 -->
                    <div v-else-if="getStatus('schedule') === 'completed'" class="font-mono text-xs text-zinc-500">
                        > Daily routines generated for all residents.
                    </div>
                </div>

                <!-- 4. Final Ready Block -->
                <div v-if="isReady" ref="introContainer" class="pt-8 pb-4 animate-fade-in-up flex flex-col items-center text-center scroll-mt-5">
                    <Rocket class="w-20 h-20 text-[#ccff00] mb-6 drop-shadow-[0_0_20px_rgba(204,255,0,0.4)]" />
                    <h2 class="text-3xl font-bold text-white mb-2 sans-serif">世界已就绪</h2>
                    <p class="text-zinc-500 text-sm font-mono mb-8">一切准备就绪，点击下方按钮开始模拟</p>
                    
                    <!-- Intro Typewriter Display -->
                    <div v-if="displayedIntro" class="max-w-2xl mx-auto px-8 animate-fade-in-up">
                        <div class="text-zinc-400 text-base leading-relaxed sans-serif whitespace-pre-wrap text-center">
                            <span v-html="formattedIntro"></span><span v-if="isTyping" class="inline-block w-0.5 h-5 bg-[#ccff00] ml-1 animate-pulse"></span>
                        </div>
                    </div>
                </div>
            </template>
            
            <!-- Spacer for footer -->
            <div class="h-12"></div>
        </div>

        <!-- Sticky Footer Toolbar -->
        <div class="p-4 bg-zinc-950/80 backdrop-blur border-t border-zinc-800 flex justify-between items-center z-20 shrink-0">
            <!-- Left: Regenerate -->
            <button 
                @click="handleRegenerate"
                :disabled="isRegenerating || !isReady"
                class="flex items-center gap-2 px-4 py-3 rounded-lg bg-zinc-900 border border-zinc-800 text-zinc-400 hover:text-zinc-200 hover:border-zinc-600 transition-colors font-bold disabled:opacity-50 disabled:cursor-not-allowed"
            >
                <RefreshCw class="w-3 h-3" :class="{'animate-spin': isRegenerating}" />
                <span>重新生成 REGENERATE</span>
            </button>

            <!-- Right: Enter World -->
            <button 
                @click="handleEnterWorld"
                :disabled="!isReady"
                class="group relative px-8 py-3 rounded-lg font-bold shadow-lg transition-all overflow-hidden disabled:opacity-50 disabled:cursor-not-allowed disabled:shadow-none"
                :class="isReady ? 'bg-[#ccff00] hover:bg-[#b3e600] text-black shadow-[0_0_20px_rgba(204,255,0,0.3)]' : 'bg-zinc-800 text-zinc-500'"
            >
                <div class="relative z-10 flex items-center gap-2">
                    <Play class="w-4 h-4 fill-current" />
                    <span>开始 PLAY</span>
                </div>
                <!-- Shine Effect -->
                <div v-if="isReady" class="absolute inset-0 bg-gradient-to-r from-transparent via-white/20 to-transparent -translate-x-full group-hover:animate-shine"></div>
            </button>
        </div>
    </div>
</template>

<style scoped>
/* Sans-serif font for Chinese text - no italic */
.sans-serif {
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC", "Hiragino Sans GB", "Microsoft YaHei", "Helvetica Neue", Helvetica, Arial, sans-serif;
  font-style: normal;
}

.custom-scrollbar::-webkit-scrollbar {
  width: 4px;
}
.custom-scrollbar::-webkit-scrollbar-track {
  background: rgba(0,0,0,0.2);
}
.custom-scrollbar::-webkit-scrollbar-thumb {
  background-color: #3f3f46;
  border-radius: 2px;
}
.custom-scrollbar::-webkit-scrollbar-thumb:hover {
  background-color: #52525b;
}

@keyframes fade-in-left {
    from { opacity: 0; transform: translateX(-10px); }
    to { opacity: 1; transform: translateX(0); }
}
.animate-fade-in-left {
    animation: fade-in-left 0.3s ease-out forwards;
}

@keyframes ping-slow {
    75%, 100% {
        transform: scale(1.5);
        opacity: 0;
    }
}
.animate-ping-slow {
    animation: ping-slow 2s cubic-bezier(0, 0, 0.2, 1) infinite;
}

@keyframes shine {
    100% {
        transform: translateX(100%);
    }
}
.animate-shine {
    animation: shine 1s;
}
</style>

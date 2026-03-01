<script setup lang="ts">
import { useGenesisStore } from '../stores/genesis';
import { Check, Brain, Cloud, Key } from 'lucide-vue-next';
import { computed } from 'vue';

const store = useGenesisStore();

// 定义 Claude 选项列表
const claudeOptions = [
  { 
    id: 'azure-sonnet', 
    name: 'Sonnet 4.5', 
    provider: 'azure', 
    providerName: 'Azure',
    model: 'claude-sonnet-4-5', 
    desc: '平衡性能 (默认推荐)',
    icon: Cloud 
  },
  { 
    id: 'azure-haiku', 
    name: 'Haiku 4.5', 
    provider: 'azure', 
    providerName: 'Azure',
    model: 'claude-haiku-4-5', 
    desc: '最快速度',
    icon: Cloud 
  },
  { 
    id: 'azure-opus', 
    name: 'Opus 4.5', 
    provider: 'azure', 
    providerName: 'Azure',
    model: 'claude-opus-4-5', 
    desc: '最强性能',
    icon: Cloud 
  },
  { 
    id: 'azure-sonnet-1m', 
    name: 'Sonnet 4.5 1M', 
    provider: 'azure', 
    providerName: 'Azure',
    model: 'claude-sonnet-4-5', 
    desc: '1M 长上下文',
    icon: Cloud 
  }
];

const currentSelection = computed({
    get: () => {
        // 根据 store 中的 config 和 model 反推当前选中的项
        const match = claudeOptions.find(opt => 
            opt.provider === store.currentApiConfig && 
            opt.model === store.currentApiModel
        );
        return match ? match.id : 'azure-sonnet'; // 默认回退
    },
    set: (val) => {
        const option = claudeOptions.find(opt => opt.id === val);
        if (option) {
            // 设置 Model (UI Store)
            store.setModel('claude'); 
            // 设置 API Config (Backend)
            store.setApiConfig(option.provider as 'azure', option.model);
        }
    }
});

const selectOption = (option: any) => {
    currentSelection.value = option.id;
};

</script>

<template>
  <div class="min-h-screen bg-black text-zinc-300 font-sans flex flex-col">
    <!-- Content -->
    <main class="flex-1 container mx-auto max-w-2xl py-12 px-6">
        <h1 class="text-3xl font-bold text-white mb-8">系统设置 SETTINGS</h1>

        <!-- Claude Provider Card -->
        <section class="bg-zinc-900 border border-zinc-800 rounded-xl p-6 mb-6">
            <h2 class="text-lg font-bold text-white mb-4 flex items-center gap-2">
                <Brain class="w-5 h-5 text-[#ccff00]" />
                模型供应商 CLAUDE
            </h2>
            
            <div class="space-y-1">
                <div 
                    v-for="option in claudeOptions" 
                    :key="option.id"
                    @click="selectOption(option)"
                    class="flex items-center justify-between p-3 rounded-lg border cursor-pointer transition-all group"
                    :class="currentSelection === option.id 
                        ? 'bg-zinc-800 border-[#ccff00] shadow-[0_0_15px_rgba(204,255,0,0.1)]' 
                        : 'bg-zinc-950 border-zinc-800 hover:border-zinc-700'"
                >
                    <div class="flex items-center gap-4">
                        <!-- Provider Icon/Badge -->
                        <div class="flex flex-col items-center justify-center w-12 h-12 rounded bg-zinc-900 border border-zinc-700">
                            <component :is="option.icon" class="w-5 h-5 text-blue-400" />
                            <span class="text-[10px] uppercase font-bold mt-1 text-blue-400">
                                {{ option.providerName }}
                            </span>
                        </div>

                        <div class="flex flex-col">
                            <span class="font-bold text-white text-sm">{{ option.name }}</span>
                            <span class="text-xs text-zinc-500 font-mono mt-0.5">{{ option.model }}</span>
                        </div>
                    </div>
                    
                    <div class="flex items-center gap-3">
                        <span class="text-xs text-zinc-500 hidden sm:block">{{ option.desc }}</span>
                        <div class="w-5 h-5 rounded-full border border-zinc-600 flex items-center justify-center transition-colors"
                            :class="{ 'bg-[#ccff00] border-[#ccff00]': currentSelection === option.id }"
                        >
                            <Check v-if="currentSelection === option.id" class="w-3 h-3 text-black" />
                        </div>
                    </div>
                </div>
            </div>
        </section>
    </main>
  </div>
</template>

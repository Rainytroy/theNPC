<script setup lang="ts">
import { Settings, LogOut } from 'lucide-vue-next';
import { useRouter, useRoute } from 'vue-router';
import { computed } from 'vue';

const router = useRouter();
const route = useRoute();

const isSettingsPage = computed(() => route.path === '/settings');

const handleSettingsAction = () => {
  if (isSettingsPage.value) {
    if (window.history.length > 1) {
      router.back();
    } else {
      router.push('/');
    }
  } else {
    router.push('/settings');
  }
};
</script>

<template>
  <nav class="bg-zinc-950 text-white border-b border-zinc-800 h-16 flex items-center pl-2 pr-6 justify-between shadow-md z-50 relative">
    <!-- Logo -->
    <router-link to="/" class="h-full flex items-center">
      <img src="@/assets/logo.svg" alt="theNPC Logo" class="h-full w-auto block" />
    </router-link>

    <!-- Right Actions -->
    <div class="flex items-center gap-4">
      
      <!-- User/Settings -->
      <button 
        v-if="!isSettingsPage"
        @click="handleSettingsAction"
        class="w-9 h-9 rounded-full bg-zinc-900 hover:bg-zinc-800 border border-zinc-800 hover:border-[#ccff00] flex items-center justify-center text-zinc-400 hover:text-[#ccff00] transition-all hover:shadow-[0_0_10px_rgba(204,255,0,0.2)]"
      >
        <Settings class="w-4 h-4" />
      </button>

      <!-- Exit Settings -->
      <button 
        v-else
        @click="handleSettingsAction"
        class="flex items-center gap-2 text-zinc-500 hover:text-white transition-colors uppercase font-bold text-xs tracking-widest group"
      >
        <LogOut class="w-4 h-4 group-hover:-translate-x-1 transition-transform" />
        退出设置 EXIT SETTINGS
      </button>
    </div>
  </nav>
</template>

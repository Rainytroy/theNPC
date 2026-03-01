<script setup lang="ts">
import { useUIStore } from '../stores/ui';
import { AlertTriangle, Info, CheckCircle2, X } from 'lucide-vue-next';

const uiStore = useUIStore();

const handleConfirm = () => {
  uiStore.closeModal(true);
};

const handleCancel = () => {
  uiStore.closeModal(false);
};
</script>

<template>
  <Transition name="modal">
    <div v-if="uiStore.isModalOpen" class="fixed inset-0 z-50 flex items-center justify-center p-4">
      <!-- Backdrop -->
      <div class="absolute inset-0 bg-black/80 backdrop-blur-sm" @click="handleCancel"></div>

      <!-- Modal Card -->
      <div class="relative w-full max-w-md bg-zinc-900 border border-zinc-800 rounded-lg shadow-2xl overflow-hidden transform transition-all">
        <!-- Close Button -->
        <button 
          @click="handleCancel" 
          class="absolute top-4 right-4 text-zinc-500 hover:text-[#ccff00] transition-colors"
        >
          <X class="w-5 h-5" />
        </button>

        <div class="p-6">
          <!-- Icon & Title -->
          <div class="flex items-center gap-3 mb-4">
            <div 
              class="w-10 h-10 rounded-full flex items-center justify-center border"
              :class="{
                'bg-blue-900/20 border-blue-500/50 text-blue-400': uiStore.modalType === 'info',
                'bg-[#ccff00]/10 border-[#ccff00]/50 text-[#ccff00]': uiStore.modalType === 'confirm',
                'bg-red-900/20 border-red-500/50 text-red-400': uiStore.modalType === 'alert'
              }"
            >
              <Info v-if="uiStore.modalType === 'info'" class="w-5 h-5" />
              <CheckCircle2 v-else-if="uiStore.modalType === 'confirm'" class="w-5 h-5" />
              <AlertTriangle v-else class="w-5 h-5" />
            </div>
            <h3 class="text-xl font-bold text-zinc-100">{{ uiStore.modalTitle }}</h3>
          </div>

          <!-- Content -->
          <div class="text-zinc-400 mb-8 leading-relaxed">
            {{ uiStore.modalContent }}
          </div>

          <!-- Actions -->
          <div class="flex justify-end gap-3">
            <button 
              v-if="uiStore.modalType === 'confirm'"
              @click="handleCancel"
              class="px-4 py-2 rounded-lg border border-zinc-700 text-zinc-400 hover:border-zinc-500 hover:text-zinc-200 transition-colors font-medium"
            >
              取消
            </button>
            <button 
              @click="handleConfirm"
              class="px-6 py-2 rounded-lg bg-[#ccff00] hover:bg-[#b3e600] text-black font-bold shadow-[0_0_15px_rgba(204,255,0,0.3)] hover:shadow-[0_0_20px_rgba(204,255,0,0.5)] transition-all"
            >
              确定
            </button>
          </div>
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

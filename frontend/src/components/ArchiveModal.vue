<script setup lang="ts">
import { ref, onMounted, computed, watch } from 'vue';
import { X, Save, RotateCcw, Trash2, AlertTriangle, Loader2, Edit2, Check } from 'lucide-vue-next';
import type { WorldMeta } from '../api/world'; // Assuming type exists or define locally

// Define simplified types
interface Archive {
  id: string;
  name: string;
  created_at: string;
}

interface Props {
  isOpen: boolean;
  worldId: string;
  worldName?: string;
}

const props = defineProps<Props>();
const emit = defineEmits<{
  'close': [];
  'restore': [id: string];
  'reset': [];
}>();

const archives = ref<Archive[]>([]);
const isLoading = ref(false);
const isSaving = ref(false);
const isRestoring = ref(false);
const isResetting = ref(false);
const showResetConfirm = ref(false);

const editingId = ref<string | null>(null);
const editName = ref('');
const confirmingRestoreId = ref<string | null>(null);
const confirmingDeleteId = ref<string | null>(null);

const fetchArchives = async () => {
  if (!props.worldId) return;
  isLoading.value = true;
  try {
    const res = await fetch(`/api/worlds/${props.worldId}/archives`);
    if (res.ok) {
      const data = await res.json();
      archives.value = data.archives;
    }
  } catch (e) {
    console.error("Failed to fetch archives", e);
  } finally {
    isLoading.value = false;
  }
};

const createArchive = async () => {
  if (!props.worldId) return;
  isSaving.value = true;
  try {
    const res = await fetch(`/api/worlds/${props.worldId}/archive`, {
      method: 'POST'
    });
    if (res.ok) {
      await fetchArchives(); // Refresh list
    }
  } catch (e) {
    console.error("Failed to create archive", e);
  } finally {
    isSaving.value = false;
  }
};

const deleteArchive = async (archiveId: string) => {
  if (!props.worldId) return;
  try {
    const res = await fetch(`/api/worlds/${props.worldId}/archives/${archiveId}`, {
      method: 'DELETE'
    });
    if (res.ok) {
      await fetchArchives();
      confirmingDeleteId.value = null;
    }
  } catch (e) {
    console.error("Failed to delete archive", e);
  }
};

const confirmRestore = async (archiveId: string) => {
  if (!props.worldId) return;
  
  isRestoring.value = true;
  try {
    const res = await fetch(`/api/worlds/${props.worldId}/archives/${archiveId}/restore`, {
      method: 'POST'
    });
    if (res.ok) {
      emit('restore', archiveId);
      emit('close');
    }
  } catch (e) {
    console.error("Failed to restore archive", e);
  } finally {
    isRestoring.value = false;
    confirmingRestoreId.value = null;
  }
};

// Deprecated: restoreArchive with system confirm
const restoreArchive = async (archiveId: string) => {
  // Keeping mainly for fallback, but UI now uses confirmRestore
  confirmRestore(archiveId);
};

const resetWorld = async () => {
  if (!props.worldId) return;
  isResetting.value = true;
  try {
    const res = await fetch(`/api/worlds/${props.worldId}/reset`, {
      method: 'POST'
    });
    if (res.ok) {
      emit('reset');
      emit('close');
    }
  } catch (e) {
    console.error("Failed to reset world", e);
  } finally {
    isResetting.value = false;
    showResetConfirm.value = false;
  }
};

onMounted(() => {
  if (props.isOpen) {
    fetchArchives();
  }
});

watch(() => props.isOpen, (newVal) => {
  if (newVal) {
    fetchArchives();
  }
});

const startEditing = (archive: Archive) => {
  editingId.value = archive.id;
  editName.value = archive.name;
};

const saveName = async (archiveId: string) => {
  if (!editName.value.trim() || !props.worldId) return;
  
  try {
    const res = await fetch(`/api/worlds/${props.worldId}/archives/${archiveId}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name: editName.value })
    });
    
    if (res.ok) {
      // Update local list
      const archive = archives.value.find(a => a.id === archiveId);
      if (archive) archive.name = editName.value;
      editingId.value = null;
    }
  } catch (e) {
    console.error("Failed to rename archive", e);
  }
};
</script>

<template>
  <div v-if="isOpen" class="fixed inset-0 z-[100] flex items-center justify-center bg-black/80 backdrop-blur-sm">
    <div class="bg-zinc-900 w-[800px] h-[600px] rounded-xl border border-zinc-800 shadow-2xl flex overflow-hidden relative">
      
      <!-- Close Button -->
      <button 
        @click="$emit('close')"
        class="absolute top-4 right-4 p-2 text-zinc-500 hover:text-white transition-colors z-10"
      >
        <X class="w-6 h-6" />
      </button>

      <!-- Left: Archive List -->
      <div class="w-1/2 border-r border-zinc-800 flex flex-col bg-zinc-900/50">
        <div class="p-6 border-b border-zinc-800">
          <h2 class="text-xl font-bold text-[#d946ef] flex items-center gap-2">
            <RotateCcw class="w-5 h-5" /> 时间锚点 ARCHIVES
          </h2>
          <p class="text-xs text-zinc-500 mt-1">选择一个时间点进行回溯</p>
        </div>
        
        <div class="flex-1 overflow-y-auto p-4 space-y-3 custom-scrollbar">
          <div v-if="isLoading" class="flex justify-center py-8">
            <Loader2 class="w-6 h-6 animate-spin text-zinc-600" />
          </div>
          
          <div v-else-if="archives.length === 0" class="text-center py-12 text-zinc-600">
            <Save class="w-8 h-8 mx-auto mb-2 opacity-20" />
            <p>暂无存档</p>
          </div>

          <div 
            v-for="archive in archives" 
            :key="archive.id"
            class="group bg-zinc-950 border border-zinc-800 hover:border-zinc-600 rounded-lg p-4 transition-all flex items-center justify-between"
          >
            <div class="flex-1 mr-4">
              <div v-if="editingId === archive.id" class="flex items-center gap-2">
                <input 
                  v-model="editName"
                  @keyup.enter="saveName(archive.id)"
                  class="bg-zinc-900 border border-zinc-700 text-white text-sm px-2 py-1 rounded w-full focus:outline-none focus:border-[#d946ef]"
                  autoFocus
                />
                <button 
                  @click="saveName(archive.id)"
                  class="text-green-500 hover:text-green-400 p-1"
                >
                  <Check class="w-4 h-4" />
                </button>
              </div>
              <div v-else class="flex items-center gap-2">
                <div class="font-mono text-sm text-[#d946ef]">{{ archive.name }}</div>
                <button 
                  @click="startEditing(archive)"
                  class="opacity-0 group-hover:opacity-100 text-zinc-600 hover:text-white transition-opacity"
                >
                  <Edit2 class="w-3 h-3" />
                </button>
              </div>
              <div class="text-xs text-zinc-600 mt-1 flex gap-2">
                <span>{{ archive.created_at }}</span>
                <span class="opacity-50">#{{ archive.id.slice(-6) }}</span>
              </div>
            </div>
            
            <div class="flex items-center gap-2 opacity-0 group-hover:opacity-100 transition-opacity">
              <!-- Delete Confirm Logic -->
              <template v-if="confirmingDeleteId === archive.id">
                <button 
                  @click="deleteArchive(archive.id)"
                  class="bg-red-900/50 hover:bg-red-600 text-white px-2 py-1.5 rounded text-xs"
                  title="Confirm Delete"
                >
                  <Check class="w-3 h-3" />
                </button>
                <button 
                  @click="confirmingDeleteId = null"
                  class="bg-zinc-800 hover:bg-zinc-700 text-zinc-400 px-2 py-1.5 rounded text-xs"
                  title="Cancel"
                >
                  <X class="w-3 h-3" />
                </button>
              </template>
              <button 
                v-else
                @click="confirmingDeleteId = archive.id; confirmingRestoreId = null"
                class="bg-zinc-900 hover:bg-red-900/30 text-zinc-500 hover:text-red-500 px-2 py-1.5 rounded text-xs transition-colors"
                title="Delete Archive"
              >
                <Trash2 class="w-3 h-3" />
              </button>

              <!-- Restore Confirm Logic -->
              <template v-if="confirmingRestoreId === archive.id">
                <div class="flex items-center gap-1 bg-zinc-800 rounded p-0.5">
                  <button 
                    @click="confirmRestore(archive.id)"
                    :disabled="isRestoring"
                    class="bg-[#d946ef] text-black px-2 py-1 rounded text-[10px] font-bold"
                  >
                    CONFIRM
                  </button>
                  <button 
                    @click="confirmingRestoreId = null"
                    class="text-zinc-400 hover:text-white px-1"
                  >
                    <X class="w-3 h-3" />
                  </button>
                </div>
              </template>
              <button 
                v-else
                @click="confirmingRestoreId = archive.id; confirmingDeleteId = null"
                :disabled="isRestoring"
                class="bg-zinc-800 hover:bg-[#d946ef] hover:text-black text-zinc-300 px-3 py-1.5 rounded text-xs font-bold transition-colors flex items-center gap-2"
              >
                <RotateCcw class="w-3 h-3" />
                LOAD
              </button>
            </div>
          </div>
        </div>
      </div>

      <!-- Right: Actions -->
      <div class="w-1/2 flex flex-col bg-zinc-900/50">
        <!-- Main Content -->
        <div class="p-8 flex-1 overflow-y-auto">
          <h3 class="text-lg font-bold text-zinc-200 mb-6">当前世界: {{ worldName }}</h3>
          
          <!-- Create Archive -->
          <div class="bg-zinc-950/50 rounded-xl border border-zinc-800 p-6">
            <h4 class="text-sm font-bold text-zinc-400 uppercase tracking-widest mb-4">Create Checkpoint</h4>
            <p class="text-xs text-zinc-500 mb-4 leading-relaxed">
              创建一个当前世界的完整快照，包含所有 NPC 的状态、记忆和日程。您可以随时回滚到这个状态。
            </p>
            <button 
              @click="createArchive"
              :disabled="isSaving"
              class="w-full bg-zinc-800 hover:bg-zinc-700 text-white py-3 rounded-lg font-bold transition-all flex items-center justify-center gap-2 border border-zinc-700"
            >
              <Loader2 v-if="isSaving" class="w-4 h-4 animate-spin" />
              <Save v-else class="w-4 h-4" />
              <span>新建存档 (SAVE)</span>
            </button>
          </div>
        </div>

        <!-- Footer: Danger Zone -->
        <div class="p-8 border-t border-zinc-800/30 bg-red-950/10">
          <h4 class="text-xs font-bold text-red-900/50 uppercase tracking-widest mb-4 flex items-center gap-2">
            <AlertTriangle class="w-4 h-4" /> Danger Zone
          </h4>
          
          <div v-if="!showResetConfirm">
            <button 
              @click="showResetConfirm = true"
              class="w-full border border-red-900/30 text-red-700 hover:bg-red-900/10 hover:border-red-900/50 py-3 rounded-lg font-bold transition-all text-sm"
            >
              重置世界 (RESET WORLD)
            </button>
          </div>
          
          <div v-else class="bg-red-900/10 border border-red-900/50 rounded-lg p-4 animate-in fade-in slide-in-from-bottom-2">
            <p class="text-red-500 text-xs font-bold mb-3">
              警告：这将清除所有历史记录和日程安排，让世界回到初始状态。此操作不可逆！
            </p>
            <div class="flex gap-3">
              <button 
                @click="showResetConfirm = false"
                class="flex-1 bg-zinc-900 text-zinc-400 hover:text-white py-2 rounded text-xs font-bold"
              >
                取消
              </button>
              <button 
                @click="resetWorld"
                :disabled="isResetting"
                class="flex-1 bg-red-600 hover:bg-red-500 text-white py-2 rounded text-xs font-bold flex items-center justify-center gap-2"
              >
                <Loader2 v-if="isResetting" class="w-3 h-3 animate-spin" />
                <span>确认重置</span>
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.custom-scrollbar::-webkit-scrollbar {
  width: 4px;
}
.custom-scrollbar::-webkit-scrollbar-track {
  background: transparent;
}
.custom-scrollbar::-webkit-scrollbar-thumb {
  background-color: #3f3f46;
  border-radius: 2px;
}
</style>

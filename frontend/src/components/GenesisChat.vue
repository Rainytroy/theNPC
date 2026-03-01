<script setup lang="ts">
import { ref, onMounted, nextTick, watch } from 'vue';
import { useGenesisStore } from '../stores/genesis';
import { Sprout, Send, Loader2 } from 'lucide-vue-next';
import MarkdownIt from 'markdown-it';

const md = new MarkdownIt({
  html: true,
  linkify: true,
  typographer: true
});

const store = useGenesisStore();
const input = ref('');
const messagesContainer = ref<HTMLElement | null>(null);

const scrollToBottom = async () => {
  await nextTick();
  if (messagesContainer.value) {
    messagesContainer.value.scrollTop = messagesContainer.value.scrollHeight;
  }
};

const renderMarkdown = (content: string) => {
  return md.render(content);
};

const handleSend = async () => {
  if (!input.value.trim() || store.isLoading) return;
  const content = input.value;
  input.value = '';
  await store.sendMessage(content);
};

onMounted(() => {
  if (!store.sessionId) {
    store.initSession();
  }
});

watch(
  () => store.messages.length,
  () => scrollToBottom()
);
</script>

<template>
  <div class="flex flex-col h-full bg-zinc-900 rounded-lg shadow-lg overflow-hidden border border-zinc-800">
    <!-- Header -->
    <div class="bg-zinc-900 p-4 font-bold text-xl flex items-center border-b border-zinc-800">
      <div class="flex items-center gap-2 text-[#00f2ff]">
        <Sprout class="w-5 h-5" />
        <span>播种者 THE SOWER</span>
      </div>
      <Loader2 v-if="store.isLoading" class="ml-auto w-5 h-5 text-[#00f2ff] animate-spin" />
    </div>

    <!-- Messages -->
    <div ref="messagesContainer" class="flex-1 overflow-y-auto p-4 space-y-6 bg-zinc-950 custom-scrollbar">
      <div
        v-for="(msg, index) in store.messages"
        :key="index"
        class="flex w-full"
        :class="msg.role === 'user' ? 'justify-end' : 'justify-start'"
      >
        <div
          v-if="msg.role === 'user'"
          class="max-w-[85%] rounded-2xl p-4 shadow-md whitespace-pre-wrap leading-relaxed bg-[#00f2ff] text-black rounded-tr-none shadow-[0_0_10px_rgba(0,242,255,0.2)] font-medium"
        >
          {{ msg.content }}
        </div>
        <div
          v-else
          class="max-w-[85%] flex flex-col gap-2"
        >
          <div
            class="rounded-2xl p-4 shadow-md leading-relaxed bg-zinc-900 text-[#00f2ff] rounded-tl-none border border-zinc-800 prose-custom"
            v-html="renderMarkdown(msg.content)"
          >
          </div>
          
          <!-- Choice Buttons -->
          <div v-if="msg.choices && msg.choices.length > 0" class="flex flex-wrap gap-2 mt-1 animate-fade-in-up">
            <button
                v-for="choice in msg.choices"
                :key="choice.action"
                @click="store.handleChatAction(choice.action, index)"
                class="px-4 py-2 rounded-lg text-sm font-bold transition-all shadow-lg border"
                :class="[
                    choice.style === 'primary' 
                        ? 'bg-[#00f2ff] text-black border-transparent hover:bg-[#00d0dd] hover:shadow-[0_0_10px_rgba(0,242,255,0.3)]' 
                        : 'bg-zinc-900 text-zinc-400 border-zinc-700 hover:bg-zinc-800 hover:text-zinc-200 hover:border-zinc-500'
                ]"
            >
                {{ choice.label }}
            </button>
          </div>
        </div>
      </div>

      <!-- Thinking Bubble -->
      <div v-if="store.isLoading" class="flex w-full justify-start animate-fade-in-up">
        <div class="max-w-[85%] flex flex-col gap-2">
          <div class="rounded-2xl p-4 shadow-md bg-zinc-900 text-[#00f2ff] rounded-tl-none border border-zinc-800 flex items-center justify-center w-16 h-12">
             <Loader2 class="w-5 h-5 animate-spin" />
          </div>
        </div>
      </div>
    </div>

    <!-- Input -->
    <div class="p-4 bg-zinc-900 border-t border-zinc-800">
      <div class="flex space-x-3">
        <input
          v-model="input"
          @keyup.enter="handleSend"
          type="text"
          placeholder="描述你想创造的世界..."
          class="flex-1 bg-zinc-950 border border-zinc-800 rounded-lg px-4 py-3 text-zinc-100 focus:outline-none focus:border-[#00f2ff] focus:shadow-[0_0_10px_rgba(0,242,255,0.1)] placeholder-zinc-600 transition-all"
          :disabled="store.isLoading"
        />
        <button
          @click="handleSend"
          class="bg-[#00f2ff] hover:bg-[#00d0dd] text-black px-6 py-3 rounded-lg font-bold transition-all disabled:opacity-50 disabled:cursor-not-allowed shadow-[0_0_10px_rgba(0,242,255,0.2)] hover:shadow-[0_0_15px_rgba(0,242,255,0.4)] flex items-center justify-center"
          :disabled="store.isLoading || !input.trim()"
        >
          <Send class="w-5 h-5" />
        </button>
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

/* Custom Prose for Acid Blue Markdown */
:deep(.prose-custom) {
  font-size: 0.95rem;
}
:deep(.prose-custom h1), :deep(.prose-custom h2), :deep(.prose-custom h3) {
  color: #fff;
  font-weight: 700;
  margin-top: 1em;
  margin-bottom: 0.5em;
}
:deep(.prose-custom strong) {
  color: #fff;
  font-weight: 800;
}
:deep(.prose-custom ul), :deep(.prose-custom ol) {
  padding-left: 1.5em;
  list-style-type: disc;
}
:deep(.prose-custom li) {
  margin-bottom: 0.25em;
}
:deep(.prose-custom p) {
  margin-bottom: 0.75em;
}
:deep(.prose-custom pre) {
  white-space: pre-wrap;
  word-wrap: break-word;
  overflow-wrap: break-word;
  max-width: 100%;
}
:deep(.prose-custom code) {
  background-color: #000;
  color: #00f2ff;
  padding: 0.2em 0.4em;
  border-radius: 4px;
  font-family: monospace;
}
</style>

import { defineStore } from 'pinia';
import { ref } from 'vue';

export const useUIStore = defineStore('ui', () => {
    const isModalOpen = ref(false);
    const modalTitle = ref('');
    const modalContent = ref('');
    const modalType = ref<'info' | 'confirm' | 'alert'>('info');
    const resolvePromise = ref<((value: boolean) => void) | null>(null);

    const openModal = (title: string, content: string, type: 'info' | 'confirm' | 'alert' = 'info'): Promise<boolean> => {
        modalTitle.value = title;
        modalContent.value = content;
        modalType.value = type;
        isModalOpen.value = true;

        return new Promise((resolve) => {
            resolvePromise.value = resolve;
        });
    };

    const closeModal = (result: boolean) => {
        isModalOpen.value = false;
        if (resolvePromise.value) {
            resolvePromise.value(result);
            resolvePromise.value = null;
        }
    };

    return {
        isModalOpen,
        modalTitle,
        modalContent,
        modalType,
        openModal,
        closeModal
    };
});

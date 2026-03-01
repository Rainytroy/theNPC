/**
 * 世界之书Store
 * 负责管理Genesis阶段的世界设定相关状态和业务逻辑
 */
import { defineStore } from 'pinia';
import genesisApi, { WorldBible } from '../../api/genesis';
import { WorldConfig } from '../../api/world';
import type { ChatMessage } from '../genesis';

export const useWorldStore = defineStore('world', {
    state: () => ({
        // 世界之书草稿
        worldBible: null as any,
        // 定稿后的世界之书
        finalizedWorldBible: null as WorldBible | null,
        // 世界是否已锁定（进入Runtime）
        isLocked: false,
        // 世界设定是否已确认
        worldConfirmed: false,
        // Agent是否建议可以确认世界设定
        isReady: false,
        // 世界配置
        worldConfig: {
            is_illustrated: false,
            enable_advanced_tasks: false,
            world_confirmed: false,
            roster_confirmed: false,
            quest_confirmed: false
        } as WorldConfig,
    }),

    getters: {
        /**
         * 世界是否已经确认定稿
         */
        isWorldConfirmed: (state) => !!state.finalizedWorldBible,

        /**
         * 获取世界标题
         */
        worldTitle: (state) => {
            return state.finalizedWorldBible?.title
                || state.worldBible?.title
                || state.worldBible?.scene?.name
                || '';
        },
    },

    actions: {
        /**
         * 更新世界标题
         * @param title 新标题
         */
        async updateWorldTitle(title: string) {
            if (!this.finalizedWorldBible?.world_id) {
                // 草稿模式：仅更新本地状态
                if (this.worldBible) this.worldBible.title = title;
                if (this.finalizedWorldBible) this.finalizedWorldBible.title = title;
                return;
            }

            try {
                const worldApi = (await import('../../api/world')).default;
                await worldApi.updateTitle(this.finalizedWorldBible.world_id, title);

                // 更新本地状态
                if (this.worldBible) this.worldBible.title = title;
                if (this.finalizedWorldBible) this.finalizedWorldBible.title = title;
            } catch (e) {
                console.error("Failed to update world title", e);
                throw e;
            }
        },

        /**
         * 确认世界之书定稿
         * @param sessionId 会话ID
         * @param messages 聊天历史
         * @returns 定稿后的世界之书
         */
        async confirmWorld(sessionId: string, messages: ChatMessage[]) {
            if (!this.worldBible) {
                throw new Error('No world bible to confirm');
            }

            // 准备payload：注入现有world_id（如果是更新草稿）
            const payloadBible = { ...this.worldBible };
            if (this.finalizedWorldBible?.world_id) {
                payloadBible.world_id = this.finalizedWorldBible.world_id;
            }

            try {
                const data = await genesisApi.confirmWorld(sessionId, payloadBible, messages);

                console.log('[WorldStore] confirmWorld response:', data);

                // 更新锁定状态
                if (data.status === 'success') {
                    console.log('[WorldStore] Force unlocking new world');
                    this.isLocked = false;
                } else {
                    this.isLocked = data.is_locked === undefined ? false : data.is_locked;
                }

                console.log('[WorldStore] isLocked set to:', this.isLocked);

                // 更新定稿的世界之书
                this.finalizedWorldBible = data.world_bible;

                // 保存确认状态
                this.worldConfirmed = true;
                this.worldConfig.world_confirmed = true;

                if (this.finalizedWorldBible?.world_id) {
                    const worldApi = (await import('../../api/world')).default;
                    await worldApi.updateConfig(this.finalizedWorldBible.world_id, this.worldConfig);
                }

                return data.world_bible;
            } catch (error) {
                console.error('[WorldStore] Failed to confirm world:', error);
                throw error;
            }
        },

        /**
         * 编辑世界（返回草稿模式）
         */
        editWorld() {
            this.finalizedWorldBible = null;
            this.isLocked = false;
            this.worldConfirmed = false;
            console.log('[WorldStore] Entered edit mode (draft)');
        },

        /**
         * 更新世界之书草稿
         * @param bible 新的世界之书数据
         */
        updateWorldBible(bible: any) {
            this.worldBible = bible;
            console.log('[WorldStore] worldBible updated:', bible);
        },

        /**
         * 更新世界配置
         * @param config 新的配置
         */
        updateConfig(config: WorldConfig) {
            this.worldConfig = config;
        },

        /**
         * 设置Agent的确认建议状态
         * @param ready 是否建议确认
         */
        setReady(ready: boolean) {
            this.isReady = ready;
        },

        /**
         * 从后端刷新世界数据
         * @param worldId 世界ID
         */
        async refreshFromBackend(worldId: string) {
            try {
                const worldApi = (await import('../../api/world')).default;
                const data = await worldApi.loadWorld(worldId);

                // 更新状态
                this.worldBible = data.world_bible;
                this.finalizedWorldBible = data.world_bible;
                this.worldConfirmed = data.config?.world_confirmed || false;
                this.isLocked = data.is_locked === undefined ? false : data.is_locked;

                if (data.config) {
                    this.worldConfig = data.config;
                }

                console.log('[WorldStore] Refreshed from backend');
            } catch (e) {
                console.error('[WorldStore] Failed to refresh from backend', e);
            }
        },

        /**
         * 重置所有状态（用于创建新世界）
         */
        reset() {
            this.worldBible = null;
            this.finalizedWorldBible = null;
            this.isLocked = false;
            this.worldConfirmed = false;
            this.isReady = false;
            this.worldConfig = {
                is_illustrated: false,
                enable_advanced_tasks: false,
                world_confirmed: false,
                roster_confirmed: false,
                quest_confirmed: false
            };
            console.log('[WorldStore] State reset');
        }
    },
});

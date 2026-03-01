import { defineStore } from 'pinia';
import genesisApi, { WorldBible, NPC, Quest, setApiProvider } from '../api/genesis';
import { useWorldStore } from './genesis/world';
import { useNpcStore } from './genesis/npc';
import { useQuestStore } from './genesis/quest';

export const PRESETS = {
    default: "Japanese manga style, anime art style, vibrant colors, detailed character design, high quality illustration",
    realistic: "Cinematic lighting, photorealistic, 8k resolution, movie still, realistic texture, highly detailed face, depth of field",
    disney: "Disney style, 3D animation, Pixar art style, cute features, expressive eyes, vibrant colors, soft lighting, 3d render",
    game: "Unreal Engine 5 render, 3A game character, highly detailed, concept art, fantasy style, digital painting, sharp focus"
};

export interface ChatChoice {
    label: string;
    action: string;
    style?: 'primary' | 'secondary' | 'danger';
    data?: any;
}

export interface ChatMessage {
    role: 'user' | 'assistant';
    content: string;
    choices?: ChatChoice[];
}

export const useGenesisStore = defineStore('genesis', {
    state: () => ({
        sessionId: '' as string,
        messages: [] as ChatMessage[],

        currentStep: 'world' as 'world' | 'npc' | 'quest' | 'launch',

        isLoading: false,
        isPlaying: false,
        currentModel: 'claude', // Default model

        // Image Generation Flow
        isWaitingForStyle: false,

        // API Configuration
        currentApiConfig: 'azure' as 'azure',
        currentApiModel: 'claude-sonnet-4-5',

        // Launch Progress
        launchProgress: null as any | null,
        isPollingLaunch: false,
    }),

    getters: {
        // ✨ Proxies to WorldStore
        worldBible: () => useWorldStore().worldBible,
        finalizedWorldBible: () => useWorldStore().finalizedWorldBible,
        isLocked: () => useWorldStore().isLocked,
        worldConfig: () => useWorldStore().worldConfig,
        isReady: () => useWorldStore().isReady,
        isIllustratedMode: () => useWorldStore().worldConfig.is_illustrated,

        // ✨ Proxies to NpcStore
        npcs: () => useNpcStore().npcs,
        generatingNpcIds: () => useNpcStore().generatingNpcIds,
        queuedNpcIds: () => useNpcStore().queuedNpcIds,
        showNpcConfirmModal: () => useNpcStore().showNpcConfirmModal,
        pendingNpcRequest: () => useNpcStore().pendingNpcRequest,

        // ✨ Proxies to QuestStore
        quests: () => useQuestStore().quests,
        items: () => useQuestStore().items,
        locations: () => useQuestStore().locations,
        timeConfig: () => useQuestStore().timeConfig,
        schedules: () => useQuestStore().schedules,
        loadingMainQuest: () => useQuestStore().loadingMainQuest,
        loadingSideQuests: () => useQuestStore().loadingSideQuests,
        loadingItems: () => useQuestStore().loadingItems,
        loadingLocations: () => useQuestStore().loadingLocations,
    },

    actions: {
        async updateWorldTitle(title: string) {
            const worldStore = useWorldStore();
            await worldStore.updateWorldTitle(title);
        },

        enterRuntime() {
            this.isPlaying = true;
        },

        setModel(model: string) {
            this.currentModel = model;
            setApiProvider(model);
        },

        async setApiConfig(config: 'azure', model: string) {
            try {
                // Call backend to switch
                const response = await fetch('http://localhost:25999/config/switch', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ config, model })
                });

                if (response.ok) {
                    this.currentApiConfig = config;
                    this.currentApiModel = model;
                    console.log(`API Config switched to ${config} with model ${model}`);
                } else {
                    console.error('Failed to switch API config');
                }
            } catch (e) {
                console.error('Error switching API config', e);
            }
        },

        async fetchApiConfig() {
            try {
                const response = await fetch('http://localhost:25999/config');
                if (response.ok) {
                    const data = await response.json();
                    if (data.active_config) {
                        this.currentApiConfig = data.active_config;
                    }
                    if (data.model) {
                        this.currentApiModel = data.model;
                    }
                }
            } catch (e) {
                console.error('Error fetching API config', e);
            }
        },

        async initSession(silent: boolean = false) {
            this.fetchApiConfig();
            this.isLoading = true;
            try {
                const data = await genesisApi.startSession();
                this.sessionId = data.session_id;
                if (!silent) {
                    this.messages.push({ role: 'assistant', content: data.message });
                }
            } finally {
                this.isLoading = false;
            }
        },

        async sendMessage(content: string) {
            if (!this.sessionId) return;

            const worldStore = useWorldStore();
            const npcStore = useNpcStore();

            // Clear historical buttons
            this.messages.forEach(msg => {
                if (msg.choices) delete msg.choices;
            });

            this.messages.push({ role: 'user', content });
            this.persistChat();
            this.isLoading = true;

            // Intercept for Style Modification
            if (this.isWaitingForStyle) {
                this.isWaitingForStyle = false;
                worldStore.worldConfig.image_style = content;

                // Update config backend (optimistic)
                if (this.finalizedWorldBible?.world_id) {
                    try {
                        const worldApi = (await import('../api/world')).default;
                        await worldApi.updateConfig(this.finalizedWorldBible.world_id, worldStore.worldConfig);
                    } catch (e) {
                        console.error("Failed to update config", e);
                    }
                }

                this.messages.push({ role: 'assistant', content: `明白，画风已更新为：“${content}”。` });

                // Ask for regeneration
                this.messages.push({
                    role: 'assistant',
                    content: '画风已保存。是否使用新画风重新生成所有角色的立绘？',
                    choices: [
                        { label: '重新生成全部 (Regenerate All)', action: 'confirm_regenerate_all', style: 'primary' },
                        { label: '取消 (Cancel)', action: 'cancel_image_gen', style: 'secondary' }
                    ]
                });

                this.persistChat();
                this.isLoading = false;
                return;
            }

            // Map currentStep to Phase
            let phase = 'world';
            if (this.currentStep === 'npc') phase = 'npc';
            if (this.currentStep === 'quest') phase = 'quest';
            if (this.currentStep === 'launch') phase = 'quest';

            try {
                const data = await genesisApi.chat(
                    this.sessionId,
                    content,
                    this.worldBible,
                    phase
                );
                this.messages.push({ role: 'assistant', content: data.response });
                this.persistChat();

                // Refresh world state
                if (this.finalizedWorldBible?.world_id) {
                    await this.refreshWorld();
                }

                // Update World Store
                if (data.suggested_world_setting) {
                    worldStore.updateWorldBible(data.suggested_world_setting);
                }

                if (data.is_ready_to_generate && data.suggested_world_setting) {
                    worldStore.setReady(true);

                    const lastMsgIdx = this.messages.length - 1;
                    if (lastMsgIdx >= 0) {
                        this.messages[lastMsgIdx].choices = [
                            { label: '确认世界之书定稿 (Confirm World)', action: 'confirm_world', style: 'primary' },
                            { label: '再构思一下 (Reconsider)', action: 'reconsider', style: 'secondary' }
                        ];
                    }
                }

                // Handle NPC Generation Trigger from Chat
                if (data.is_ready_for_npc) {
                    console.log("[Chat] Sower suggests generating NPCs:", data.npc_requirements, data.npc_count);

                    // Combine summary with full text to ensure Shaper gets all details
                    // The Shaper prompt treats this as "User Additional Requirements"
                    const fullRequirements = (data.npc_requirements || '') + '\n\n**Detailed Context from Chat**:\n' + data.response;

                    npcStore.requestGenerateNPCs(fullRequirements, data.npc_count || 3);

                    const lastMsgIdx = this.messages.length - 1;
                    if (lastMsgIdx >= 0) {
                        this.messages[lastMsgIdx].choices = [
                            { label: '生成居民 (Generate NPCs)', action: 'confirm_generate_npcs', style: 'primary' },
                            { label: '自定义 (Customize)', action: 'customize_npcs', style: 'secondary' }
                        ];
                    }
                }

                // Handle Quest Generation Trigger from Chat (Phase 3)
                if (data.is_ready_for_quest) {
                    console.log("[Chat] Sower suggests generating Quests:", data.quest_requirements);

                    const requirements = data.quest_requirements || '';

                    const lastMsgIdx = this.messages.length - 1;
                    if (lastMsgIdx >= 0) {
                        this.messages[lastMsgIdx].choices = [
                            {
                                label: '生成任务蓝图 (Generate Blueprint)',
                                action: 'confirm_generate_quests_with_reqs',
                                style: 'primary',
                                data: { requirements }
                            },
                            { label: '再构思一下 (Reconsider)', action: 'reconsider', style: 'secondary' }
                        ];
                    }
                }

                // Handle Pending Actions
                if (data.pending_actions && data.pending_actions.length > 0) {
                    const lastMsgIdx = this.messages.length - 1;
                    if (lastMsgIdx >= 0) {
                        const existing = this.messages[lastMsgIdx].choices || [];

                        const regenActions = data.pending_actions.filter((a: any) => a.type === 'regenerate_npc');
                        const otherActions = data.pending_actions.filter((a: any) => a.type !== 'regenerate_npc');

                        const newChoices: ChatChoice[] = [];

                        // 1. Batch Regenerate (Always use queue for regenerate_npc)
                        if (regenActions.length > 0) {
                            let label = `⚡ 批量执行修改 (${regenActions.length}个角色)`;
                            // If single, use the specific label but keep queue behavior
                            if (regenActions.length === 1) {
                                label = regenActions[0].label;
                            }

                            newChoices.push({
                                label: label,
                                action: 'execute_all_pending_actions',
                                style: 'primary',
                                data: regenActions
                            });
                        }

                        // 2. Others (Enable, Cancel, etc.) - Always individual
                        otherActions.forEach((a: any) => {
                            newChoices.push({
                                label: a.label,
                                action: `execute_pending_action_${a.type}`, // Make action unique
                                style: a.style as any,
                                data: a
                            });
                        });

                        this.messages[lastMsgIdx].choices = [...existing, ...newChoices];
                    }
                }

            } catch (error) {
                console.error("Chat API Error:", error);
                this.messages.push({
                    role: 'assistant',
                    content: "抱歉，与思维核心的连接似乎断开了（LLM服务响应异常）。请稍后重试。",
                    choices: [
                        { label: '重试 (Retry)', action: 'retry_last_message', style: 'danger' }
                    ]
                });
            } finally {
                this.isLoading = false;
            }
        },

        async handleChatAction(action: string, msgIndex?: number) {
            let msgWithChoices: ChatMessage | undefined;
            if (msgIndex !== undefined && this.messages[msgIndex]) {
                msgWithChoices = this.messages[msgIndex];
            } else {
                msgWithChoices = this.messages.find(m => m.choices && m.choices.length > 0);
            }

            const clearChoices = () => {
                if (msgWithChoices) delete msgWithChoices.choices;
            };

            const choice = msgWithChoices?.choices?.find(c => c.action === action && (msgIndex === undefined || true));
            const worldStore = useWorldStore();
            const npcStore = useNpcStore();
            const questStore = useQuestStore();

            // Handle dynamic actions (e.g. execute_pending_action_cancel)
            let baseAction = action;
            if (action.startsWith('execute_pending_action_')) {
                baseAction = 'execute_pending_action';
            }

            switch (baseAction) {
                case 'execute_all_pending_actions':
                    if (choice && choice.data && Array.isArray(choice.data)) {
                        clearChoices();
                        const actions = choice.data;
                        this.messages.push({ role: 'user', content: `确认全部修改 (${actions.length}个操作)` });

                        this.isLoading = true;

                        // 1. Initialize Status Message
                        const statusMsgIndex = this.messages.length;
                        // Filter out 'cancel' actions for the checklist
                        const tasks = actions.filter(a => a.type !== 'cancel');

                        // Initialize with image status pending if illustrated mode is on
                        const isIllustrated = worldStore.worldConfig.is_illustrated;
                        let checklist = tasks.map(a => ({
                            ...a,
                            status: 'pending',
                            imageStatus: isIllustrated ? 'pending' : null
                        }));

                        const renderChecklist = () => {
                            let md = "### 📋 执行队列 (Execution Queue)\n\n";
                            checklist.forEach((item, idx) => {
                                let statusIcon = '⏳';
                                let statusText = 'Waiting...';

                                if (item.status === 'running') { statusIcon = '🔄'; statusText = 'Processing...'; }
                                if (item.status === 'done') { statusIcon = '✅'; statusText = 'Done'; }

                                md += `> ${statusIcon} **${item.label}**\n`;

                                // Sub-step for image
                                if (item.imageStatus) {
                                    let imgIcon = '⏳';
                                    let imgText = 'Pending...';

                                    if (item.imageStatus === 'pending') { imgIcon = '⏳'; imgText = '等待生图...'; }
                                    if (item.imageStatus === 'running') { imgIcon = '🎨'; imgText = '正在绘制...'; }
                                    if (item.imageStatus === 'done') { imgIcon = '🖼️'; imgText = '立绘更新完成'; }

                                    md += `>   * ${imgIcon} ${imgText}\n`;
                                } else {
                                    md += `>   * ${statusText}\n`;
                                }
                                md += `>\n`; // Spacer
                            });
                            return md;
                        };

                        this.messages.push({
                            role: 'assistant',
                            content: renderChecklist()
                        });
                        await this.persistChat();

                        try {
                            for (let i = 0; i < tasks.length; i++) {
                                const pAction = tasks[i];

                                // Update Status: Running
                                checklist[i].status = 'running';
                                this.messages[statusMsgIndex].content = renderChecklist();

                                try {
                                    // Execute Core Action
                                    if (pAction.type === 'regenerate_npc') {
                                        await genesisApi.executeRegenerateNPC(
                                            pAction.data.world_id,
                                            pAction.data.target_name,
                                            pAction.data.instruction
                                        );

                                        await this.refreshWorld();

                                        // Auto-Image Generation Logic
                                        if (worldStore.worldConfig.is_illustrated) {
                                            checklist[i].imageStatus = 'running';
                                            this.messages[statusMsgIndex].content = renderChecklist();

                                            // Find NPC ID by name (Name is unique in roster context usually)
                                            const targetNpc = npcStore.npcs.find(n => n.profile.name === pAction.data.target_name);
                                            if (targetNpc) {
                                                try {
                                                    // Call Frontend Logic (shows spinner on card)
                                                    await npcStore.generateNPCImage(targetNpc.id);
                                                } catch (imgErr) {
                                                    console.error("Image gen failed", imgErr);
                                                }
                                            }
                                            checklist[i].imageStatus = 'done';
                                        }
                                    }
                                    else if (pAction.type === 'manage_images') {
                                        await genesisApi.executeManageImages(
                                            pAction.data.world_id,
                                            pAction.data.action,
                                            pAction.data.target_name
                                        );
                                        await this.refreshWorld();
                                    }
                                    else if (pAction.type === 'add_npc') {
                                        await genesisApi.executeAddNPC(
                                            pAction.data.world_id,
                                            pAction.data.count,
                                            pAction.data.requirements
                                        );
                                        await this.refreshWorld();

                                        // Auto-Image for added NPC
                                        if (worldStore.worldConfig.is_illustrated) {
                                            checklist[i].imageStatus = 'running';
                                            this.messages[statusMsgIndex].content = renderChecklist();
                                            await npcStore.enableIllustratedMode(false);
                                            checklist[i].imageStatus = 'done';
                                        }
                                    }

                                    // Update Status: Done
                                    checklist[i].status = 'done';
                                    this.messages[statusMsgIndex].content = renderChecklist();
                                } catch (taskErr) {
                                    console.error("Task failed", taskErr);
                                }
                            }

                            // Final Completion
                            this.messages.push({
                                role: 'assistant',
                                content: `所有修改已完成！是否确认定稿？`,
                                choices: [
                                    { label: '确认居民名册定稿 (Confirm Roster)', action: 'confirm_generate_quests', style: 'primary' },
                                    { label: '再构思一下 (Reconsider)', action: 'reconsider', style: 'secondary' }
                                ]
                            });

                        } catch (e) {
                            console.error("Failed to execute batch actions", e);
                            this.messages.push({ role: 'assistant', content: `执行过程中遇到错误: ${e}` });
                        } finally {
                            this.isLoading = false;
                        }
                    }
                    break;

                case 'execute_pending_action':
                    if (choice && choice.data) {
                        clearChoices();
                        const pAction = choice.data;
                        this.messages.push({ role: 'user', content: `确认：${pAction.label}` });

                        try {
                            this.isLoading = true;
                            if (pAction.type === 'add_npc') {
                                this.messages.push({ role: 'assistant', content: '好的，正在为您安排...' });
                                await genesisApi.executeAddNPC(
                                    pAction.data.world_id,
                                    pAction.data.count,
                                    pAction.data.requirements
                                );
                                await this.refreshWorld();
                                this.messages.push({ role: 'assistant', content: '新居民已入住。' });
                            }
                            else if (pAction.type === 'regenerate_npc') {
                                this.messages.push({ role: 'assistant', content: '好的，正在进行调整...' });
                                await genesisApi.executeRegenerateNPC(
                                    pAction.data.world_id,
                                    pAction.data.target_name,
                                    pAction.data.instruction
                                );
                                await this.refreshWorld();
                                this.messages.push({
                                    role: 'assistant',
                                    content: '修改完毕，是否满意？',
                                    choices: [
                                        { label: '确认居民名册定稿 (Confirm Roster)', action: 'confirm_generate_quests', style: 'primary' },
                                        { label: '再构思一下 (Reconsider)', action: 'reconsider', style: 'secondary' }
                                    ]
                                });
                            }
                            else if (pAction.type === 'manage_images') {
                                const action = pAction.data.action;
                                const isDisable = action === 'disable';

                                if (isDisable) {
                                    this.messages.push({ role: 'user', content: '关闭立绘' });
                                    await this.toggleIllustratedMode(false);
                                    this.messages.push({ role: 'assistant', content: '好的，即将关闭立绘显示（回到纯文本模式）。' });
                                } else {
                                    // Enable / Generate Logic (Redirect to Interactive Flow)
                                    this.messages.push({ role: 'user', content: '开启立绘' });

                                    // 1. Force Enable UI
                                    await this.toggleIllustratedMode(true);

                                    // 2. Check Data State
                                    const total = npcStore.npcs.length;
                                    const withImg = npcStore.npcs.filter(n => n.profile.avatar_url).length;

                                    if (withImg === 0) {
                                        // Scenario 1: No images - First Time Flow
                                        this.messages.push({
                                            role: 'assistant',
                                            content: `已开启立绘。监测到当前没有立绘，请选择画风进行生成：\n\n默认画风：${PRESETS.default}`,
                                            choices: [
                                                { label: '日式漫画（默认）', action: 'confirm_image_style_default', style: 'primary' },
                                                { label: '写实电影风 (Realistic)', action: 'set_image_style_preset_realistic', style: 'secondary' },
                                                { label: '迪斯尼3D (Disney)', action: 'set_image_style_preset_disney', style: 'secondary' },
                                                { label: '3A游戏风 (Game Art)', action: 'set_image_style_preset_game', style: 'secondary' },
                                                { label: '自定义 (Custom)', action: 'ask_custom_image_style', style: 'secondary' },
                                                { label: '取消 (Cancel)', action: 'cancel_image_gen', style: 'danger' }
                                            ]
                                        });
                                    } else if (withImg < total) {
                                        // Scenario 2: Partial images
                                        this.messages.push({
                                            role: 'assistant',
                                            content: `已开启立绘。监测到 ${withImg}/${total} 个角色已有立绘。`,
                                            choices: [
                                                { label: '仅补全缺失 (Fill Missing)', action: 'confirm_image_fill_missing', style: 'primary' },
                                                { label: '修改画风 (Change Style)', action: 'modify_image_style', style: 'secondary' },
                                                { label: '取消 (Cancel)', action: 'cancel_image_gen', style: 'secondary' }
                                            ]
                                        });
                                    } else {
                                        // Scenario 3: All images exist
                                        this.messages.push({
                                            role: 'assistant',
                                            content: '已开启立绘。监测到所有角色均已有立绘。是否需要修改画风？',
                                            choices: [
                                                { label: '修改画风 (Change Style)', action: 'modify_image_style', style: 'primary' },
                                                { label: '取消 (Cancel)', action: 'cancel_image_gen', style: 'secondary' }
                                            ]
                                        });
                                    }
                                }
                            }
                            else if (pAction.type === 'enter_quest_phase') {
                                if (this.finalizedWorldBible?.world_id) {
                                    this.messages.push({ role: 'assistant', content: '好的，正在归档居民名册，随后进入任务蓝图阶段。' });
                                    await genesisApi.executeConfirmRoster(this.finalizedWorldBible.world_id);
                                    await this.refreshWorld();
                                    this.currentStep = 'quest';

                                    // Removed automatic generateQuests. Now we wait for user requirements via Chat (Phase 3).
                                }
                            }
                            else if (pAction.type === 'cancel_enter_quest') {
                                this.messages.push({ role: 'assistant', content: '没问题，我们继续调整。请告诉我您想修改什么？' });
                            }
                        } catch (e) {
                            console.error("Failed to execute action", e);
                            this.messages.push({ role: 'assistant', content: `执行遇到问题: ${e}` });
                        } finally {
                            this.isLoading = false;
                        }
                    }
                    break;

                case 'confirm_world':
                    if (this.finalizedWorldBible) {
                        console.warn('[confirm_world] World already confirmed, ignoring action');
                        clearChoices();
                        return;
                    }

                    try {
                        const { useUIStore } = await import('./ui');
                        const uiStore = useUIStore();
                        const confirmed = await uiStore.openModal(
                            '确认世界设定',
                            '确认以此设定创建世界吗？创建后核心设定将不可更改。确认后将进入第二阶段：居民生成 (NPC Roster)。',
                            'confirm'
                        );

                        if (confirmed) {
                            clearChoices();
                            this.messages.push({ role: 'user', content: '确认定稿。' });
                            await this.confirmWorld();
                        }
                    } catch (e) {
                        console.error("Confirmation flow failed", e);
                    }
                    break;

                case 'reconsider':
                    clearChoices();
                    this.messages.push({ role: 'user', content: '我还需要再构思一下。' });
                    this.messages.push({ role: 'assistant', content: '好的，请告诉我您想调整哪些部分？' });
                    break;

                case 'confirm_generate_npcs':
                    clearChoices();
                    this.messages.push({ role: 'user', content: '开始生成居民。' });
                    await this.confirmGenerateNPCs();
                    break;

                case 'customize_npcs':
                    clearChoices();
                    this.messages.push({ role: 'user', content: '我想调整一下NPC生成的具体要求。' });
                    this.messages.push({ role: 'assistant', content: '没问题，请告诉我您对居民有什么特殊要求？（例如：职业、性格、种族等）' });
                    npcStore.pendingNpcRequest = null;
                    break;

                case 'confirm_generate_quests':
                    if (worldStore.worldConfig.roster_confirmed) {
                        console.warn('[confirm_generate_quests] Roster already confirmed, ignoring action');
                        clearChoices();
                        return;
                    }

                    clearChoices();
                    this.messages.push({ role: 'user', content: '进入任务蓝图阶段。' });

                    if (this.finalizedWorldBible?.world_id) {
                        await genesisApi.executeConfirmRoster(this.finalizedWorldBible.world_id);
                        await this.refreshWorld();

                        worldStore.worldConfig.roster_confirmed = true;
                        const worldApi = (await import('../api/world')).default;
                        await worldApi.updateConfig(this.finalizedWorldBible.world_id, worldStore.worldConfig);
                    }

                    this.currentStep = 'quest';
                    break;

                case 'execute_pending_action_confirm_generate_quests_with_reqs':
                case 'confirm_generate_quests_with_reqs':
                    clearChoices();
                    this.messages.push({ role: 'user', content: '开始生成任务蓝图。' });
                    this.messages.push({ role: 'assistant', content: '收到。正在为您编织命运的丝线（生成任务蓝图）...' });

                    const reqs = choice?.data?.requirements;
                    await questStore.generateQuests(async (msg) => {
                        // Sync with backend to get Summary/Transition messages before appending our own
                        await this.refreshWorld();

                        this.messages.push({ role: 'assistant', content: msg });

                        // Add chips after generation
                        const lastMsgIdx = this.messages.length - 1;
                        if (lastMsgIdx >= 0) {
                            this.messages[lastMsgIdx].choices = [
                                { label: '确认任务蓝图 (Confirm Blueprint)', action: 'confirm_quest_blueprint', style: 'primary' },
                                { label: '重新生成 (Regenerate)', action: 'ask_regenerate_quest', style: 'secondary' }
                            ];
                        }
                        this.persistChat();
                    }, reqs);
                    break;

                case 'ask_regenerate_quest':
                    clearChoices();
                    this.messages.push({ role: 'user', content: '我想重新生成。' });
                    this.messages.push({ role: 'assistant', content: '没问题。请告诉我您希望如何调整主线剧情？（例如：换个风格，或者强调某种冲突）' });
                    break;

                case 'execute_pending_action_confirm_quest_blueprint':
                case 'confirm_quest_blueprint':
                    try {
                        const { useUIStore } = await import('./ui');
                        const uiStore = useUIStore();
                        const confirmed = await uiStore.openModal(
                            '确认任务蓝图',
                            '确认以此蓝图启动世界吗？此操作将锁定任务设定，并开始生成世界开场、任务细节和居民日程。',
                            'confirm'
                        );

                        if (confirmed) {
                            clearChoices();
                            this.messages.push({ role: 'user', content: '确认任务蓝图。' });

                            this.isLoading = true;
                            if (this.finalizedWorldBible?.world_id) {
                                // 1. Update config (bible.json)
                                await questStore.confirmQuests();
                                // 2. Trigger backend initialization process
                                await genesisApi.executeConfirmQuestBlueprint(this.finalizedWorldBible.world_id);
                                // 3. Refresh state (will switch to launch tab)
                                await this.refreshWorld();
                                this.messages.push({ role: 'assistant', content: '任务蓝图已定稿。世界已准备就绪！' });
                            }
                        }
                    } catch (e) {
                        console.error("Failed to confirm quest blueprint", e);
                        this.messages.push({ role: 'assistant', content: '确认失败，请重试。' });
                    } finally {
                        this.isLoading = false;
                    }
                    break;

                case 'continue_editing':
                    clearChoices();
                    this.messages.push({ role: 'user', content: '先不进入，我还要继续调整。' });
                    break;

                case 'modify_npcs':
                    clearChoices();
                    this.messages.push({ role: 'user', content: '我想调整一下居民。' });
                    this.messages.push({ role: 'assistant', content: '没问题，您可以直接在右侧列表中点击“重随”或修改特定居民，也可以告诉我您的修改意见。' });
                    break;

                case 'retry_last_message':
                    clearChoices();
                    const lastUserMsg = [...this.messages].reverse().find(m => m.role === 'user');
                    if (lastUserMsg) {
                        await this.sendMessage(lastUserMsg.content);
                    }
                    break;

                case 'ask_image_style':
                    clearChoices();
                    const currentStyle = worldStore.worldConfig.image_style || PRESETS.default;
                    this.messages.push({ role: 'user', content: '我想生成立绘。' });
                    this.messages.push({
                        role: 'assistant',
                        content: `好的。当前的默认画风提示词是：\n\n\`${currentStyle}\`\n\n请选择画风进行生成：`,
                        choices: [
                            { label: '日式漫画（默认）', action: 'confirm_image_style_default', style: 'primary' },
                            { label: '写实电影风 (Realistic)', action: 'set_image_style_preset_realistic', style: 'secondary' },
                            { label: '迪斯尼3D (Disney)', action: 'set_image_style_preset_disney', style: 'secondary' },
                            { label: '3A游戏风 (Game Art)', action: 'set_image_style_preset_game', style: 'secondary' },
                            { label: '自定义 (Custom)', action: 'ask_custom_image_style', style: 'secondary' },
                            { label: '取消 (Cancel)', action: 'cancel_image_gen', style: 'danger' }
                        ]
                    });
                    break;

                case 'skip_images':
                    clearChoices();
                    this.messages.push({ role: 'user', content: '暂不需要立绘。' });
                    await this.toggleIllustratedMode(false);
                    this.messages.push({
                        role: 'assistant',
                        content: "如果不需要立绘，你现在需要进入下一个阶段吗？",
                        choices: [
                            { label: '确认居民名册定稿 (Confirm Roster)', action: 'confirm_generate_quests', style: 'primary' },
                            { label: '再构思一下 (Reconsider)', action: 'reconsider', style: 'secondary' }
                        ]
                    });
                    break;

                case 'confirm_image_style_default':
                    clearChoices();
                    this.messages.push({ role: 'user', content: '使用默认画风。' });
                    this.messages.push({ role: 'assistant', content: '明白。正在为您生成立绘，请稍候...' });
                    await this.enableIllustratedMode(true);

                    this.messages.push({
                        role: 'assistant',
                        content: "立绘生成任务已提交后台。您对这份居民名单满意吗？如果满意，我们可以进入下一步：规划任务蓝图。",
                        choices: [
                            { label: '确认居民名册定稿 (Confirm Roster)', action: 'confirm_generate_quests', style: 'primary' },
                            { label: '再构思一下 (Reconsider)', action: 'reconsider', style: 'secondary' }
                        ]
                    });
                    break;

                case 'modify_image_style':
                    clearChoices();
                    this.messages.push({ role: 'user', content: '修改画风。' });
                    this.messages.push({
                        role: 'assistant',
                        content: '请选择新的画风预设，或选择自定义：',
                        choices: [
                            { label: '日式漫画 (默认)', action: 'set_image_style_preset_default', style: 'secondary' },
                            { label: '写实电影风 (Realistic)', action: 'set_image_style_preset_realistic', style: 'secondary' },
                            { label: '迪斯尼3D (Disney)', action: 'set_image_style_preset_disney', style: 'secondary' },
                            { label: '3A游戏风 (Game Art)', action: 'set_image_style_preset_game', style: 'secondary' },
                            { label: '自定义 (Custom)', action: 'ask_custom_image_style', style: 'secondary' },
                            { label: '取消 (Cancel)', action: 'cancel_image_gen', style: 'danger' }
                        ]
                    });
                    break;

                case 'set_image_style_preset_default':
                case 'set_image_style_preset_realistic':
                case 'set_image_style_preset_disney':
                case 'set_image_style_preset_game':
                    clearChoices();

                    // Map action to style and label
                    let style = PRESETS.default;
                    let label = '日式漫画';

                    if (action === 'set_image_style_preset_realistic') {
                        style = PRESETS.realistic;
                        label = '写实电影风';
                    } else if (action === 'set_image_style_preset_disney') {
                        style = PRESETS.disney;
                        label = '迪斯尼3D';
                    } else if (action === 'set_image_style_preset_game') {
                        style = PRESETS.game;
                        label = '3A游戏风';
                    }

                    this.messages.push({ role: 'user', content: `使用画风：${label}` });

                    worldStore.worldConfig.image_style = style;

                    // Update config backend (optimistic)
                    if (this.finalizedWorldBible?.world_id) {
                        try {
                            const worldApi = (await import('../api/world')).default;
                            await worldApi.updateConfig(this.finalizedWorldBible.world_id, worldStore.worldConfig);
                        } catch (e) {
                            console.error("Failed to update config", e);
                        }
                    }

                    this.messages.push({
                        role: 'assistant',
                        content: `画风已更新为"${label}"。是否使用新画风重新生成所有立绘？`,
                        choices: [
                            { label: '重新生成全部 (Regenerate All)', action: 'confirm_regenerate_all', style: 'primary' },
                            { label: '取消 (Cancel)', action: 'cancel_image_gen', style: 'secondary' }
                        ]
                    });
                    this.persistChat();
                    break;

                case 'confirm_regenerate_all':
                    clearChoices();
                    this.messages.push({ role: 'user', content: '重新生成全部。' });
                    this.messages.push({ role: 'assistant', content: '好的，正在重新生成所有角色的立绘...' });
                    await this.enableIllustratedMode(true); // force=true triggers regen all

                    this.messages.push({
                        role: 'assistant',
                        content: '生成任务已提交。',
                        choices: [
                            { label: '确认居民名册定稿 (Confirm Roster)', action: 'confirm_generate_quests', style: 'primary' },
                            { label: '再构思一下 (Reconsider)', action: 'reconsider', style: 'secondary' }
                        ]
                    });
                    this.persistChat();
                    break;

                case 'ask_custom_image_style':
                    clearChoices();
                    this.messages.push({ role: 'user', content: '我自己定。' });
                    this.messages.push({ role: 'assistant', content: '好的，你接下来的输入将成为画风提示词。' });
                    this.isWaitingForStyle = true;
                    break;

                case 'cancel_image_gen':
                    clearChoices();
                    this.messages.push({ role: 'user', content: '取消生成。' });
                    this.messages.push({ role: 'assistant', content: '好的，已取消生成任务。' });
                    this.messages.push({
                        role: 'assistant',
                        content: "如果不生成立绘，您现在需要进入下一个阶段吗？",
                        choices: [
                            { label: '确认居民名册定稿 (Confirm Roster)', action: 'confirm_generate_quests', style: 'primary' },
                            { label: '再构思一下 (Reconsider)', action: 'reconsider', style: 'secondary' }
                        ]
                    });
                    break;

                case 'confirm_image_fill_missing':
                    clearChoices();
                    this.messages.push({ role: 'user', content: '仅补全缺失。' });
                    this.messages.push({ role: 'assistant', content: '好的，正在为缺失立绘的居民生成图片，请稍候...' });
                    await this.enableIllustratedMode(false); // false = only missing

                    this.messages.push({
                        role: 'assistant',
                        content: "补全任务已提交。是否对现在的效果满意？",
                        choices: [
                            { label: '确认居民名册定稿 (Confirm Roster)', action: 'confirm_generate_quests', style: 'primary' },
                            { label: '再构思一下 (Reconsider)', action: 'reconsider', style: 'secondary' }
                        ]
                    });
                    break;
            }
        },

        async confirmGenerateNPCs() {
            const npcStore = useNpcStore();
            if (!npcStore.pendingNpcRequest) return;

            npcStore.showNpcConfirmModal = false;
            const { requirements, count } = npcStore.pendingNpcRequest;

            // Lock handled by WorldStore/UI?
            // Just proceed.
            this.currentStep = 'npc';

            this.messages.push({ role: 'assistant', content: `明白。正在为您生成 ${count} 位居民，请稍候...` });

            // Delegate to NpcStore but also handle feedback?
            // Actually NpcStore.confirmGenerateNPCs calls NpcStore.generateNPCs.
            // But we need the chat feedback.
            // So we call generateNPCs wrapper in GenesisStore.
            // Manually clear request in NpcStore?
            npcStore.pendingNpcRequest = null;

            await this.generateNPCs(requirements, count);
        },

        cancelGenerateNPCs() {
            const npcStore = useNpcStore();
            npcStore.cancelGenerateNPCs();
            this.messages.push({ role: 'assistant', content: "好的，我们可以继续完善世界设定，或者稍后再生成。" });
        },

        async confirmWorld() {
            if (!this.sessionId || !this.worldBible) return;
            this.isLoading = true;
            const worldStore = useWorldStore();

            try {
                await worldStore.confirmWorld(this.sessionId, this.messages);

                this.currentStep = 'npc';
                await this.refreshWorld();

            } finally {
                this.isLoading = false;
            }
        },

        editWorld() {
            const worldStore = useWorldStore();
            const npcStore = useNpcStore();
            worldStore.editWorld();
            npcStore.setNpcs([]);
        },

        async generateNPCs(requirements?: string, count: number = 3) {
            const npcStore = useNpcStore();
            if (!this.finalizedWorldBible) return;
            this.isLoading = true;

            try {
                // Delegate to NpcStore
                await npcStore.generateNPCs(requirements, count);

                this.messages.push({
                    role: 'assistant',
                    content: "居民已生成完毕。您需要为他们生成立绘吗？（开启立绘后，游戏运行时会启用‘漫画书’功能，在世界流逝时同步为您生成漫画风格的角色形象）",
                    choices: [
                        { label: '生成立绘 (Generate Images)', action: 'ask_image_style', style: 'primary' },
                        { label: '暂不需要 (No)', action: 'skip_images', style: 'secondary' }
                    ]
                });
                this.persistChat();

            } finally {
                this.isLoading = false;
            }
        },

        async toggleIllustratedMode(value: boolean) {
            const worldStore = useWorldStore();
            if (!this.finalizedWorldBible?.world_id) {
                worldStore.worldConfig.is_illustrated = value;
                return;
            }

            const oldVal = worldStore.worldConfig.is_illustrated;
            worldStore.worldConfig.is_illustrated = value;

            try {
                const worldApi = (await import('../api/world')).default;
                await worldApi.updateConfig(this.finalizedWorldBible.world_id, worldStore.worldConfig);
            } catch (e) {
                console.error("Failed to update config", e);
                worldStore.worldConfig.is_illustrated = oldVal;
            }
        },

        async toggleAdvancedTasks(value: boolean) {
            const worldStore = useWorldStore();
            if (!this.finalizedWorldBible?.world_id) {
                worldStore.worldConfig.enable_advanced_tasks = value;
                return;
            }

            const oldVal = worldStore.worldConfig.enable_advanced_tasks;
            worldStore.worldConfig.enable_advanced_tasks = value;

            try {
                const worldApi = (await import('../api/world')).default;
                await worldApi.updateConfig(this.finalizedWorldBible.world_id, worldStore.worldConfig);
            } catch (e) {
                console.error("Failed to update config", e);
                worldStore.worldConfig.enable_advanced_tasks = oldVal;
            }
        },

        async enableIllustratedMode(force: boolean = false) {
            const npcStore = useNpcStore();
            this.isLoading = true;
            try {
                await npcStore.enableIllustratedMode(force);
            } finally {
                this.isLoading = false;
            }
        },

        async persistChat() {
            if (!this.finalizedWorldBible?.world_id) return;
            try {
                await genesisApi.saveChat(this.finalizedWorldBible.world_id, this.messages);
            } catch (e) {
                console.error("Failed to persist chat", e);
            }
        },

        async generateQuests(callback?: (msg: string) => void, requirements?: string) {
            console.log('[GenesisStore] generateQuests triggered, clearing UI options...');
            // Clear choices from messages to sync state with UI
            // Use assignment to undefined for better reactivity guarantee than delete
            this.messages.forEach(msg => {
                if (msg.choices) msg.choices = undefined;
            });

            const questStore = useQuestStore();
            await questStore.generateQuests(callback, requirements);

            // Sync with backend to ensure UI shows Summary/Transition messages generated by backend
            await this.refreshWorld();
        },

        async retryMainQuest() {
            const questStore = useQuestStore();
            await questStore.retryMainQuest();
        },

        async retrySideQuest(npcId: string) {
            const questStore = useQuestStore();
            await questStore.retrySideQuest(npcId);
        },

        async confirmQuests() {
            console.log('[GenesisStore] confirmQuests triggered, clearing UI options...');
            // Clear choices from messages to sync state with UI
            this.messages.forEach(msg => {
                if (msg.choices) msg.choices = undefined;
            });

            const questStore = useQuestStore();
            await questStore.confirmQuests();
        },

        async updateQuest(questId: string, title: string, description: string) {
            const questStore = useQuestStore();
            await questStore.updateQuest(questId, title, description);
        },

        async pollLaunchStatus() {
            if (!this.finalizedWorldBible?.world_id || this.isPollingLaunch) return;

            this.isPollingLaunch = true;
            try {
                const status = await genesisApi.checkStatus(this.finalizedWorldBible.world_id);
                this.launchProgress = status;

                // If ready, stop polling (or let UI handle it)
                if (status.current_phase === 'ready') {
                    // Launch complete
                }
            } catch (e) {
                console.error("Failed to poll launch status", e);
            } finally {
                this.isPollingLaunch = false;
            }
        },

        async refreshWorld() {
            if (!this.finalizedWorldBible?.world_id) return;

            const worldStore = useWorldStore();
            const npcStore = useNpcStore();
            const questStore = useQuestStore();

            try {
                const worldApi = (await import('../api/world')).default;
                const data = await worldApi.loadWorld(this.finalizedWorldBible.world_id);

                // Update NpcStore
                npcStore.setNpcs(data.npcs);

                // Update QuestStore
                questStore.setQuests(data.quests || []);
                questStore.setItems(data.items || []);
                questStore.setLocations(data.locations || []);
                questStore.setTimeConfig(data.time_config || null);
                questStore.setSchedules(data.schedules || {});

                if (data.chat_history && data.chat_history.length > 0) {
                    this.messages = data.chat_history;
                }

                // Update World Store
                worldStore.updateWorldBible(data.world_bible);
                worldStore.finalizedWorldBible = data.world_bible;
                worldStore.isLocked = data.is_locked === undefined ? false : data.is_locked;
                if (data.config) {
                    worldStore.updateConfig(data.config);
                }

                console.log("World Data Refreshed");

                // Determine Step
                let nextStep: 'world' | 'npc' | 'quest' | 'launch' = 'world';

                // Robust Config Check: Check both explicit config and raw bible config
                // This prevents issues where one object might be missing or stale
                const rawConfig = (data.world_bible as any)?.config || {};
                const apiConfig = data.config || {};

                // Loose check to handle potential string 'true' vs boolean true (though should be boolean)
                const isRosterConfirmed = (apiConfig.roster_confirmed === true) || (rawConfig.roster_confirmed === true);
                const isQuestConfirmed = (apiConfig.quest_confirmed === true) || (rawConfig.quest_confirmed === true);

                console.log('[refreshWorld] Roster Confirmed Check:', {
                    api: apiConfig.roster_confirmed,
                    raw: rawConfig.roster_confirmed,
                    final: isRosterConfirmed
                });

                if (this.finalizedWorldBible) {
                    nextStep = 'npc';
                    if (isRosterConfirmed) {
                        nextStep = 'quest';
                        if (isQuestConfirmed || worldStore.isLocked) {
                            nextStep = 'launch';
                        }
                    }
                }

                this.currentStep = nextStep;
                console.log('[refreshWorld] Determined step:', nextStep);

            } catch (e) {
                console.error("Failed to refresh world", e);
            }
        },

    },
});

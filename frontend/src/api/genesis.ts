import axios from 'axios';

// Create axios instance with base URL
const api = axios.create({
    baseURL: '/api/genesis',
    headers: {
        'Content-Type': 'application/json',
    },
});

export const setApiProvider = (provider: string) => {
    api.defaults.headers.common['X-Model-Provider'] = provider;
};

export interface WorldBackground {
    era: string;
    rules: string[];
    society: string;
}

export interface GameScene {
    name: string;
    description: string;
    key_objects: string[];
    locations?: string[];
}

export interface TimeConfig {
    start_datetime: string;
    display_year?: string;
    day_length_real_sec: number;
}

export interface WorldBible {
    world_id: string;
    title?: string;
    player_objective?: string;
    background: WorldBackground;
    scene: GameScene;
    time_config: TimeConfig;
}

export interface GenesisChatResponse {
    response: string;
    is_ready_to_generate: boolean;
    suggested_world_setting?: {
        title?: string;
        background: WorldBackground;
        scene: GameScene;
    };
    is_ready_for_npc?: boolean;
    npc_requirements?: string;
    npc_count?: number;
    is_ready_for_quest?: boolean;
    quest_requirements?: string;
    quest_count?: number;
    pending_actions?: PendingAction[];
}

export interface PendingAction {
    type: string;
    data: any;
    label: string;
    style: string;
}

export interface NPC {
    id: string;
    profile: {
        name: string;
        age: number;
        gender: string;
        race: string;
        avatar_desc: string;
        occupation: string;
        avatar_url?: string;
    };
    dynamic: {
        personality_desc: string;
        values: string[];
        mood: string;
        current_location: string;
        current_action?: string;
    };
    quest_role?: {
        role: string;
        clue: string;
        motivation: string;
        attitude: string;
    };
    goals: {
        id: string;
        description: string;
        type: string;
        status: string;
        trigger_condition?: string;
    }[];
    skills: {
        name: string;
        description: string;
        level: number;
    }[];
    relationships: Record<string, any>;
    _incomplete?: boolean;  // 标记 NPC 生成失败
    _error?: string;  // 错误信息
    _imageError?: boolean; // 图片生成失败
}

export interface QuestCondition {
    type: 'affinity' | 'item' | 'location' | 'time' | 'state' | 'dialogue';
    params: Record<string, any>;
}

export interface QuestNode {
    id: string;
    description: string;
    target_npc_id: string;
    required_affinity: number;
    status: 'pending' | 'active' | 'completed' | 'locked' | 'failed';
    conditions?: QuestCondition[];
    type?: 'dialogue' | 'collect' | 'investigate' | 'wait' | 'choice';
}

export interface Quest {
    id: string;
    title: string;
    type: 'main' | 'side';
    description: string;
    nodes: QuestNode[];
    status: 'active' | 'completed' | 'failed';
    target_npc_id?: string;
}

export default {
    async startSession() {
        const response = await api.post<{ session_id: string; message: string }>('/start');
        return response.data;
    },

    async chat(sessionId: string, content: string, currentBible?: any, phase: string = 'world') {
        const response = await api.post<GenesisChatResponse>('/chat', {
            session_id: sessionId,
            content,
            current_bible: currentBible,
            phase
        });
        return response.data;
    },

    async confirmWorld(sessionId: string, worldSetting: any, chatHistory?: any[]) {
        const response = await api.post<{ status: string; world_bible: WorldBible; is_locked: boolean }>('/confirm_world', {
            session_id: sessionId,
            world_setting: worldSetting,
            chat_history: chatHistory
        });
        return response.data;
    },

    async generateNPCs(worldBible: WorldBible, count: number = 3, requirements?: string) {
        const response = await api.post<{ npcs: NPC[] }>('/generate_npcs', {
            world_bible: worldBible,
            count,
            requirements
        });
        return response.data;
    },

    async generateRoster(worldBible: WorldBible, count: number = 3, requirements?: string) {
        const response = await api.post<{ skeletons: NPC[]; new_locations: string[] }>('/generate_roster', {
            world_bible: worldBible,
            count,
            requirements
        });
        return response.data;
    },

    async generateQuests(worldBible: WorldBible, npcs: NPC[]) {
        const response = await api.post<{ quests: Quest[] }>('/generate_quests', {
            world_bible: worldBible,
            npcs
        });
        return response.data;
    },

    async enrichAssets(worldBible: WorldBible) {
        const response = await api.post<{ items: any[]; locations: any[] }>('/enrich_assets', {
            world_bible: worldBible
        });
        return response.data;
    },

    async generateMainQuest(worldBible: WorldBible, npcs: NPC[], skipEnrichment: boolean = false, requirements?: string) {
        const response = await api.post<{ quests: Quest[]; items?: any[]; locations?: any[] }>('/generate_main_quest', {
            world_bible: worldBible,
            npcs,
            skip_enrichment: skipEnrichment,
            requirements
        });
        return response.data;
    },

    async generateSideQuest(targetNpc: NPC, worldBible: WorldBible) {
        const response = await api.post<{ quests: Quest[]; items?: any[]; locations?: any[] }>('/generate_side_quest', {
            target_npc: targetNpc,
            world_bible: worldBible
        });
        return response.data;
    },

    async generateNPCDetails(skeleton: any, worldBible: WorldBible, rosterNames: string, requirements?: string) {
        const response = await api.post<NPC>('/generate_npc_details', {
            skeleton,
            world_bible: worldBible,
            roster_names: rosterNames,
            requirements
        });
        return response.data;
    },

    async regenerateNPC(npcId: string, worldId: string, requirements?: string) {
        const response = await api.post<{ status: string; npc: NPC }>(`/regenerate_npc/${npcId}`, {
            world_id: worldId,
            requirements
        });
        return response.data;
    },

    async generateNPCImage(npcId: string, worldId: string, stylePrompt?: string) {
        const response = await api.post<NPC>('/generate_npc_image', {
            world_id: worldId,
            npc_id: npcId,
            style_prompt: stylePrompt
        });
        return response.data;
    },

    async saveChat(worldId: string, messages: any[]) {
        const response = await api.post<{ status: string }>('/save_chat', {
            world_id: worldId,
            messages
        });
        return response.data;
    },

    async updateNPCProfile(worldId: string, npcId: string, avatarDesc: string) {
        const response = await api.post<NPC>('/update_npc_profile', {
            world_id: worldId,
            npc_id: npcId,
            avatar_desc: avatarDesc
        });
        return response.data;
    },

    async uploadAvatar(worldId: string, npcId: string, file: File) {
        const formData = new FormData();
        formData.append('world_id', worldId);
        formData.append('npc_id', npcId);
        formData.append('file', file);

        const response = await api.post<NPC>('/upload_avatar', formData, {
            headers: {
                'Content-Type': 'multipart/form-data'
            }
        });
        return response.data;
    },

    async executeAddNPC(worldId: string, count: number, requirements?: string) {
        const response = await api.post<{ status: string }>('/execute_add_npc', {
            world_id: worldId,
            count,
            requirements
        });
        return response.data;
    },

    async executeRegenerateNPC(worldId: string, targetName: string, instruction: string) {
        const response = await api.post<{ status: string }>('/execute_regenerate_npc', {
            world_id: worldId,
            target_name: targetName,
            instruction
        });
        return response.data;
    },

    async executeManageImages(worldId: string, action: string, targetName?: string) {
        const response = await api.post<{ status: string }>('/execute_manage_images', {
            world_id: worldId,
            action,
            target_name: targetName
        });
        return response.data;
    },

    async executeConfirmRoster(worldId: string) {
        const response = await api.post<{ status: string }>('/execute_confirm_roster', {
            world_id: worldId
        });
        return response.data;
    },

    async updateQuest(worldId: string, questId: string, title: string, description: string) {
        const response = await api.post('/update_quest', {
            world_id: worldId,
            quest_id: questId,
            title,
            description
        });
        return response.data;
    },

    async checkStatus(worldId: string) {
        const response = await api.post<{
            world_id: string;
            is_locked: boolean;
            current_phase: string;
            progress: Record<string, any>;
            message: string;
        }>('/check_status', {
            world_id: worldId
        });
        return response.data;
    },

    async executeConfirmQuestBlueprint(worldId: string) {
        const response = await api.post<{ status: string }>('/execute_confirm_quest_blueprint', {
            world_id: worldId
        });
        return response.data;
    },

    // ✅ 新增直接获取 intro 的接口
    async getIntro(worldId: string) {
        const response = await axios.get<{ intro: string }>(`/api/worlds/${worldId}/intro`);
        return response.data;
    }
};

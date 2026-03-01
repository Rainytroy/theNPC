import axios from 'axios';
import { WorldBible, NPC, Quest } from './genesis';

const api = axios.create({
    baseURL: '/api/worlds',
    headers: {
        'Content-Type': 'application/json',
    },
});

export interface WorldMeta {
    world_id: string;
    title?: string;
    name: string;
    era: string;
    created_at: string;
    npc_count: number;
    preview: string;
}

export interface WorldConfig {
    is_illustrated: boolean;
    enable_advanced_tasks: boolean;
    image_style?: string;
    manga_page_size?: number;
    world_confirmed?: boolean;
    roster_confirmed?: boolean;
    quest_confirmed?: boolean;
}

export interface LoadWorldResponse {
    status: string;
    world_bible: WorldBible;
    npcs: NPC[];
    items?: any[];
    locations?: any[];
    time_config?: any;
    quests?: Quest[];
    chat_history: any[];
    schedules?: Record<string, any[]>;
    is_locked?: boolean;
    config: WorldConfig;
}

export default {
    async listWorlds() {
        const response = await api.get<{ worlds: WorldMeta[] }>('/');
        return response.data;
    },

    async loadWorld(worldId: string) {
        // Add cache busting timestamp
        const response = await api.get<LoadWorldResponse>(`/${worldId}?t=${Date.now()}`);
        return response.data;
    },

    async updateConfig(worldId: string, config: WorldConfig) {
        const response = await api.patch(`/${worldId}/config`, { config });
        return response.data;
    },

    async updateTitle(worldId: string, title: string) {
        const response = await api.patch<{ status: string; title: string }>(`/${worldId}/title`, { title });
        return response.data;
    },

    async deleteWorld(worldId: string) {
        const response = await api.delete(`/${worldId}`);
        return response.data;
    },
};

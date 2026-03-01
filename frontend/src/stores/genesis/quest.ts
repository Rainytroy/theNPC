import { defineStore } from 'pinia';
import genesisApi, { Quest, WorldBible, NPC } from '../../api/genesis';
import { useWorldStore } from './world';
import { useNpcStore } from './npc';

export const useQuestStore = defineStore('genesis-quest', {
    state: () => ({
        quests: [] as Quest[],
        items: [] as any[],
        locations: [] as any[],
        timeConfig: null as any,
        schedules: {} as Record<string, any[]>,

        // Granular Loading State
        loadingMainQuest: false,
        loadingSideQuests: {} as Record<string, boolean>,
        loadingItems: false,
        loadingLocations: false,
        isLoading: false, // General loading for quest operations
    }),

    getters: {
        hasQuests: (state) => state.quests.length > 0,
        mainQuest: (state) => state.quests.find(q => q.type === 'main'),
        sideQuests: (state) => state.quests.filter(q => q.type === 'side'),
    },

    actions: {
        setQuests(quests: Quest[]) {
            this.quests = quests;
        },

        setItems(items: any[]) {
            this.items = items;
        },

        setLocations(locations: any[]) {
            this.locations = locations;
        },

        setTimeConfig(config: any) {
            this.timeConfig = config;
        },

        setSchedules(schedules: Record<string, any[]>) {
            this.schedules = schedules;
        },

        async generateQuests(chatCallback?: (msg: string) => void | Promise<void>, requirements?: string) {
            const worldStore = useWorldStore();
            const npcStore = useNpcStore();
            const bible = worldStore.finalizedWorldBible;
            const npcs = npcStore.npcs;

            if (!bible || npcs.length === 0) return;

            // Loading State
            this.isLoading = true;
            this.loadingMainQuest = true;
            this.loadingSideQuests = {};
            npcs.forEach(n => this.loadingSideQuests[n.id] = true);
            this.loadingItems = true;
            this.loadingLocations = true;

            // Clear Data
            this.quests = [];

            try {
                console.log("Phase 3.1: Enriching Assets (Step 1&2)...");
                // 1. Enrich Assets
                const assetsRes = await genesisApi.enrichAssets(bible);

                if (assetsRes.items) {
                    console.log(`Phase 3.1.1: Assets enriched (${assetsRes.items.length} items)`);
                    this.items = assetsRes.items;
                    this.loadingItems = false;
                }
                if (assetsRes.locations) {
                    console.log(`Phase 3.1.2: Assets enriched (${assetsRes.locations.length} locations)`);
                    this.locations = assetsRes.locations;
                    this.loadingLocations = false;
                }

                console.log("Phase 3.2: Generating Main Quest (Step 3)...");
                // 2. Main Quest
                const mainRes = await genesisApi.generateMainQuest(bible, npcs, true, requirements);

                this.quests = this.quests.filter(q => q.type !== 'main');
                this.quests.push(...mainRes.quests);
                this.loadingMainQuest = false;

                // Merge Items/Locations
                // Fix: Overwrite items directly as backend returns the full authoritative list from items.json
                if (mainRes.items) {
                    this.items = mainRes.items;
                }
                if (mainRes.locations) {
                    this.locations = mainRes.locations;
                }

                // Refresh World (to sync backend file state)
                // Note: We might need to expose a refresh method or call it from main store
                // For now, let's assume main store handles refresh or we import logic?
                // Circular dependency risk if we import GenesisStore. 
                // Better to just rely on local state updates for now, or move refreshWorld logic here?
                // actually refreshWorld updates ALL stores. It belongs in a central place or WorldStore.
                // Let's leave refresh logic to the caller (GenesisStore) or emit an event?
                // Or just don't call refreshWorld here, relying on the return data.

                // 3. Side Quests (Parallel execution - don't update items during concurrent execution)
                console.log("Phase 3.4: Generating Side Quests...");
                const sidePromises = npcs.map(async (npc) => {
                    try {
                        const sideRes = await genesisApi.generateSideQuest(npc, bible);
                        const newIds = new Set(sideRes.quests.map(q => q.id));

                        // Update quests only
                        const currentQuests = [...this.quests];
                        const filtered = currentQuests.filter(q => !newIds.has(q.id));
                        filtered.push(...sideRes.quests);
                        this.quests = filtered;

                        // Don't update items/locations here - will do full reload after all side quests complete
                    } catch (e) {
                        console.error(`Failed side quest for ${npc.profile.name}`, e);
                    } finally {
                        this.loadingSideQuests[npc.id] = false;
                    }
                });

                await Promise.all(sidePromises);

                // 4. After ALL side quests complete, do a full reload of items/locations (3rd full update)
                console.log("Phase 3.5: Final full reload of items/locations...");
                if (bible.world_id) {
                    try {
                        const worldApi = (await import('../../api/world')).default;
                        const worldData = await worldApi.loadWorld(bible.world_id);

                        // 3rd full update - includes all World Bible items + Main Quest updates + Side Quest new items
                        if (worldData.items) {
                            this.items = worldData.items;
                        }
                        if (worldData.locations) {
                            this.locations = worldData.locations;
                        }

                        console.log(`✓ Final reload complete: ${this.items.length} items, ${this.locations.length} locations`);
                    } catch (e) {
                        console.error("Failed to reload items/locations after side quests", e);
                    }
                }

                if (chatCallback) {
                    await chatCallback(`任务蓝图已生成！共包含 ${this.quests.length} 个任务链。您可以查看详情，并在确认无误后点击底部的确认按钮。`);
                }

            } catch (e) {
                console.error("Failed to generate quests", e);
                if (chatCallback) {
                    await chatCallback("生成任务时遇到了一些问题，请重试。");
                }
            } finally {
                this.isLoading = false;
                this.loadingMainQuest = false;
                this.loadingSideQuests = {};
                this.loadingItems = false;
                this.loadingLocations = false;
            }
        },

        async retryMainQuest() {
            const worldStore = useWorldStore();
            const npcStore = useNpcStore();
            const bible = worldStore.finalizedWorldBible;

            if (!bible) return;

            this.loadingMainQuest = true;
            try {
                const mainRes = await genesisApi.generateMainQuest(bible, npcStore.npcs, true); // Should we skip enrichment on retry? Probably yes if assets are fine.
                this.quests = this.quests.filter(q => q.type !== 'main');
                this.quests.push(...mainRes.quests);
            } catch (e) {
                console.error("Retry Main Quest Failed", e);
            } finally {
                this.loadingMainQuest = false;
            }
        },

        async retrySideQuest(npcId: string) {
            const worldStore = useWorldStore();
            const npcStore = useNpcStore();
            const bible = worldStore.finalizedWorldBible;
            const npc = npcStore.npcs.find(n => n.id === npcId);

            if (!bible || !npc) return;

            this.loadingSideQuests[npcId] = true;
            try {
                const sideRes = await genesisApi.generateSideQuest(npc, bible);

                this.quests = this.quests.filter(q => {
                    if (q.type === 'side') {
                        return (q as any).target_npc_id !== npcId;
                    }
                    return true;
                });

                this.quests.push(...sideRes.quests);
            } catch (e) {
                console.error(`Retry Side Quest ${npc.profile.name} Failed`, e);
            } finally {
                this.loadingSideQuests[npcId] = false;
            }
        },

        async confirmQuests() {
            const worldStore = useWorldStore();
            const bible = worldStore.finalizedWorldBible;
            if (!bible?.world_id) return;

            this.isLoading = true;
            try {
                worldStore.worldConfig.quest_confirmed = true;
                const worldApi = (await import('../../api/world')).default;
                await worldApi.updateConfig(bible.world_id, worldStore.worldConfig);
            } catch (e) {
                console.error("Failed to confirm quests", e);
                throw e;
            } finally {
                this.isLoading = false;
            }
        },

        async updateQuest(questId: string, title: string, description: string) {
            const worldStore = useWorldStore();
            const bible = worldStore.finalizedWorldBible;
            if (!bible?.world_id) return;

            try {
                await genesisApi.updateQuest(bible.world_id, questId, title, description);
                const quest = this.quests.find(q => q.id === questId);
                if (quest) {
                    quest.title = title;
                    quest.description = description;
                }
            } catch (e) {
                console.error("Failed to update quest", e);
                throw e;
            }
        }
    }
});

import { defineStore } from 'pinia';
import genesisApi, { NPC } from '../../api/genesis';
import { useWorldStore } from './world';

export const useNpcStore = defineStore('npc', {
    state: () => ({
        npcs: [] as NPC[],
        generatingNpcIds: [] as string[], // Track active generation
        queuedNpcIds: [] as string[], // Track waiting queue

        // NPC Confirmation State
        showNpcConfirmModal: false,
        pendingNpcRequest: null as { requirements: string, count: number } | null,
    }),

    getters: {
        // Count failed NPCs
        failedCount: (state) => state.npcs.filter(npc => npc._incomplete).length,
    },

    actions: {
        setNpcs(npcs: NPC[]) {
            this.npcs = npcs;
        },

        async generateNPCs(requirements?: string, count: number = 3) {
            const worldStore = useWorldStore();
            if (!worldStore.finalizedWorldBible) return;

            // Clear previous NPCs if generating fresh batch? 
            // In genesis.ts it was: this.npcs = [];
            this.npcs = [];

            try {
                console.log(`[NpcStore] Phase 1: Generating Roster (${count} NPCs)...`);
                const rosterData = await genesisApi.generateRoster(worldStore.finalizedWorldBible, count, requirements);

                // Update Locations in WorldStore if new ones generated
                if (rosterData.new_locations && rosterData.new_locations.length > 0) {
                    const scene = worldStore.finalizedWorldBible.scene as any;
                    const currentLocs = scene.locations || [];
                    const mergedLocs = Array.from(new Set([...currentLocs, ...rosterData.new_locations]));

                    // We need to update worldBible in WorldStore
                    // This modifies the object reference in WorldStore which is reactive.
                    scene.locations = mergedLocs;
                }

                // Show Skeletons immediately
                this.npcs = rosterData.skeletons;
                const rosterNames = this.npcs.map(n => n.profile.name).join(", ");

                console.log("[NpcStore] Phase 2: Generating Details (Sequential)...");

                for (let i = 0; i < this.npcs.length; i++) {
                    const skeleton = this.npcs[i];
                    try {
                        console.log(`[NpcStore] Generating details for NPC ${i + 1}/${this.npcs.length}: ${skeleton.profile.name}`);

                        const fullNPC = await genesisApi.generateNPCDetails(
                            skeleton,
                            worldStore.finalizedWorldBible!,
                            rosterNames,
                            requirements
                        );

                        // Reactively update
                        this.npcs.splice(i, 1, fullNPC);

                        // Add a small delay
                        await new Promise(resolve => setTimeout(resolve, 1000));

                    } catch (e) {
                        console.error(`[NpcStore] Failed to generate details for NPC ${i}`, e);
                    }
                }

                // Reload world bible to sync locations (if backend updated it)
                if (worldStore.finalizedWorldBible.world_id) {
                    try {
                        await worldStore.refreshFromBackend(worldStore.finalizedWorldBible.world_id);
                    } catch (e) {
                        console.warn("[NpcStore] Failed to reload world bible:", e);
                    }
                }

                return this.npcs;
            } catch (e) {
                console.error("[NpcStore] Error generating NPCs:", e);
                throw e;
            }
        },

        async regenerateNPC(npcId: string) {
            const worldStore = useWorldStore();
            if (!worldStore.finalizedWorldBible) return;

            const npcIndex = this.npcs.findIndex(n => n.id === npcId);
            if (npcIndex === -1) return;

            try {
                const result = await genesisApi.regenerateNPC(
                    npcId,
                    worldStore.finalizedWorldBible.world_id
                );
                this.npcs.splice(npcIndex, 1, result.npc);
                return result.npc;
            } catch (error) {
                console.error(`[NpcStore] Failed to regenerate NPC:`, error);
                throw error;
            }
        },

        async generateNPCImage(npcId: string) {
            const worldStore = useWorldStore();
            if (!worldStore.finalizedWorldBible) return;

            try {
                const npcIndex = this.npcs.findIndex(n => n.id === npcId);
                if (npcIndex === -1) return;

                // Move from queue to generating
                this.queuedNpcIds = this.queuedNpcIds.filter(id => id !== npcId);
                if (!this.generatingNpcIds.includes(npcId)) {
                    this.generatingNpcIds.push(npcId);
                }

                console.log(`[NpcStore] Generating image for NPC: ${this.npcs[npcIndex].profile.name}`);

                const updatedNPC = await genesisApi.generateNPCImage(
                    npcId,
                    worldStore.finalizedWorldBible.world_id,
                    worldStore.worldConfig.image_style // Use config from WorldStore
                );

                this.npcs.splice(npcIndex, 1, updatedNPC);
                return updatedNPC;
            } catch (e) {
                console.error(`[NpcStore] Failed to generate image for NPC ${npcId}`, e);
                const npcIndex = this.npcs.findIndex(n => n.id === npcId);
                if (npcIndex !== -1) {
                    const npc = this.npcs[npcIndex];
                    const updatedNPC = { ...npc, _imageError: true };
                    this.npcs.splice(npcIndex, 1, updatedNPC);
                }
                throw e;
            } finally {
                this.generatingNpcIds = this.generatingNpcIds.filter(id => id !== npcId);
                this.queuedNpcIds = this.queuedNpcIds.filter(id => id !== npcId);
            }
        },

        async updateNPCProfile(npcId: string, avatarDesc: string) {
            const worldStore = useWorldStore();
            if (!worldStore.finalizedWorldBible) return;
            const npcIndex = this.npcs.findIndex(n => n.id === npcId);
            if (npcIndex === -1) return;

            try {
                const updatedNPC = await genesisApi.updateNPCProfile(
                    worldStore.finalizedWorldBible.world_id,
                    npcId,
                    avatarDesc
                );
                this.npcs.splice(npcIndex, 1, updatedNPC);
                return updatedNPC;
            } catch (e) {
                console.error("[NpcStore] Failed to update NPC profile", e);
                throw e;
            }
        },

        async uploadAvatar(npcId: string, file: File) {
            const worldStore = useWorldStore();
            if (!worldStore.finalizedWorldBible) return;
            const npcIndex = this.npcs.findIndex(n => n.id === npcId);
            if (npcIndex === -1) return;

            try {
                const updatedNPC = await genesisApi.uploadAvatar(
                    worldStore.finalizedWorldBible.world_id,
                    npcId,
                    file
                );
                this.npcs.splice(npcIndex, 1, updatedNPC);
                return updatedNPC;
            } catch (e) {
                console.error("[NpcStore] Failed to upload avatar", e);
                throw e;
            }
        },

        async enableIllustratedMode(force: boolean = false) {
            const worldStore = useWorldStore();
            if (!worldStore.finalizedWorldBible) return;

            // Ensure switch is on in World Config
            if (!worldStore.worldConfig.is_illustrated) {
                // Update config logic is in WorldStore/GenesisStore?
                // NpcStore can call API to update config if needed, or assume caller handled it.
                // Better: Update WorldStore config locally and save.
                // But this logic was in toggleIllustratedMode.

                // Let's assume enabling illustrated mode here implies turning it on.
                // But we need to save it.
                // For now, let's assume the caller handles the config toggle persistence if this is just an action.
                // OR we just do it here.

                worldStore.worldConfig.is_illustrated = true;
                if (worldStore.finalizedWorldBible.world_id) {
                    const worldApi = (await import('../../api/world')).default;
                    await worldApi.updateConfig(worldStore.finalizedWorldBible.world_id, worldStore.worldConfig);
                }
            }

            const targetNpcIds: string[] = [];
            for (const npc of this.npcs) {
                if (force === true || !npc.profile.avatar_url) {
                    targetNpcIds.push(npc.id);
                }
            }

            this.queuedNpcIds = [...new Set([...this.queuedNpcIds, ...targetNpcIds])];

            try {
                console.log(`[NpcStore] Enabling Illustrated Mode: Batch generating images for ${targetNpcIds.length} NPCs...`);
                for (const npcId of targetNpcIds) {
                    await this.generateNPCImage(npcId);
                    await new Promise(r => setTimeout(r, 500));
                }
            } finally {
                // We don't have isLoading here? We should add it or rely on generatingNpcIds length.
                // GenesisStore has a global isLoading. 
                // NpcStore could have its own isLoading for batch ops.
                this.queuedNpcIds = [];
            }
        },

        requestGenerateNPCs(requirements: string, count: number) {
            this.pendingNpcRequest = { requirements, count };
            this.showNpcConfirmModal = true;
        },

        cancelGenerateNPCs() {
            this.showNpcConfirmModal = false;
            this.pendingNpcRequest = null;
        },

        // Use this when user confirms via Modal
        async confirmGenerateNPCs() {
            if (!this.pendingNpcRequest) return;

            this.showNpcConfirmModal = false;
            const { requirements, count } = this.pendingNpcRequest;
            this.pendingNpcRequest = null;

            await this.generateNPCs(requirements, count);
        },

        reset() {
            this.npcs = [];
            this.generatingNpcIds = [];
            this.queuedNpcIds = [];
            this.showNpcConfirmModal = false;
            this.pendingNpcRequest = null;
        }
    }
});

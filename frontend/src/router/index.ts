import { createRouter, createWebHistory } from 'vue-router';
import GenesisView from '../views/GenesisView.vue';
import RuntimeView from '../views/RuntimeView.vue';
import SettingsView from '../views/SettingsView.vue';

const routes = [
    {
        path: '/',
        name: 'genesis',
        component: GenesisView
    },
    {
        path: '/settings',
        name: 'settings',
        component: SettingsView
    },
    {
        path: '/world/:id',
        name: 'runtime',
        component: RuntimeView,
        props: true
    }
];

const router = createRouter({
    history: createWebHistory(),
    routes
});

export default router;

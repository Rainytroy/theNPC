<script setup lang="ts">
import GlobalNavbar from './components/GlobalNavbar.vue';
import BaseModal from './components/BaseModal.vue';
</script>

<template>
  <div class="flex flex-col h-screen overflow-hidden">
    <GlobalNavbar />
    <div class="flex-1 overflow-hidden">
      <router-view></router-view>
    </div>
    <BaseModal />
  </div>
</template>

<style>
/* Global overrides if needed */
</style>

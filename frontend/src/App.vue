<script setup lang="ts">
import LoginNoticeDialog from '@/components/LoginNoticeDialog.vue'
</script>

<template>
  <router-view />
  <LoginNoticeDialog />
</template>

<style>
#app {
  height: 100%;
  width: 100%;
}
</style>

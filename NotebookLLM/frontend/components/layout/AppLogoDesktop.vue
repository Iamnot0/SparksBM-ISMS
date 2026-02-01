<template>
  <div class="logo-container" v-bind="$attrs">
    <img 
      src="/logo.png" 
      alt="SparksBM Logo" 
      class="logo-image"
    />
    <svg viewBox="0 0 200 50" version="1.1" xmlns="http://www.w3.org/2000/svg" class="logo-text">
      <text
        x="0"
        y="50%"
        font-family="Arial, sans-serif"
        font-size="36"
        font-weight="bold"
        fill="#C81517"
        text-anchor="start"
        dominant-baseline="middle"
      >
        SparksBM
      </text>
    </svg>
  </div>
</template>

<script setup lang="ts">
</script>

<style scoped>
.logo-container {
  display: flex;
  align-items: center;
  height: 100%;
  gap: 0;
  background: transparent;
}

.logo-image {
  height: 32px;
  width: auto;
  object-fit: contain;
  background: transparent;
  background-color: transparent;
}

.logo-text {
  height: 32px;
  width: auto;
  background: transparent;
}
</style>
